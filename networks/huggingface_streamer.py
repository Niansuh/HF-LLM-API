import json
import re
import requests

from tclogger import logger
from constants.models import MODEL_MAP, STOP_SEQUENCES_MAP
from constants.envs import PROXIES
from messagers.message_outputer import OpenaiStreamOutputer
from messagers.token_checker import TokenChecker


class HuggingfaceStreamer:
    def __init__(self, model: str):
        if model in MODEL_MAP.keys():
            self.model = model
        else:
            self.model = "nous-mixtral-8x7b"
        self.model_fullname = MODEL_MAP[self.model]
        self.message_outputer = OpenaiStreamOutputer(model=self.model)

    def parse_line(self, line):
        line = line.decode("utf-8")
        line = re.sub(r"data:\s*", "", line)
        data = json.loads(line)
        content = ""
        try:
            content = data["token"]["text"]
        except:
            logger.err(data)
        return content

    def chat_response(
        self,
        prompt: str = None,
        temperature: float = 0.5,
        top_p: float = 0.95,
        max_new_tokens: int = None,
        api_key: str = None,
        use_cache: bool = False,
    ):
        # https://huggingface.co/docs/api-inference/detailed_parameters?code=curl
        # curl --proxy http://<server>:<port> https://api-inference.huggingface.co/models/<org>/<model_name> -X POST -d '{"inputs":"who are you?","parameters":{"max_new_token":64}}' -H 'Content-Type: application/json' -H 'Authorization: Bearer <HF_TOKEN>'
        self.request_url = (
            f"https://api-inference.huggingface.co/models/{self.model_fullname}"
        )
        self.request_headers = {
            "Content-Type": "application/json",
        }

        if api_key:
            logger.note(
                f"Using API Key: {api_key[:3]}{(len(api_key)-7)*'*'}{api_key[-4:]}"
            )
            self.request_headers["Authorization"] = f"Bearer {api_key}"

        if temperature is None or temperature < 0:
            temperature = 0.0
        # temperature must  0 < and < 1 for HF LLM models
        temperature = max(temperature, 0.01)
        temperature = min(temperature, 0.99)
        top_p = max(top_p, 0.01)
        top_p = min(top_p, 0.99)

        checker = TokenChecker(input_str=prompt, model=self.model)

        if max_new_tokens is None or max_new_tokens <= 0:
            max_new_tokens = checker.get_token_redundancy()
        else:
            max_new_tokens = min(max_new_tokens, checker.get_token_redundancy())

        # References:
        #   huggingface_hub/inference/_client.py:
        #     class InferenceClient > def text_generation()
        #   huggingface_hub/inference/_text_generation.py:
        #     class TextGenerationRequest > param `stream`
        # https://huggingface.co/docs/text-generation-inference/conceptual/streaming#streaming-with-curl
        # https://huggingface.co/docs/api-inference/detailed_parameters#text-generation-task
        self.request_body = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
                "top_p": top_p,
                "max_new_tokens": max_new_tokens,
                "return_full_text": False,
            },
            "options": {
                "use_cache": use_cache,
            },
            "stream": True,
        }

        if self.model in STOP_SEQUENCES_MAP.keys():
            self.stop_sequences = STOP_SEQUENCES_MAP[self.model]
        #     self.request_body["parameters"]["stop_sequences"] = [
        #         self.STOP_SEQUENCES[self.model]
        #     ]

        logger.back(self.request_url)
        stream_response = requests.post(
            self.request_url,
            headers=self.request_headers,
            json=self.request_body,
            proxies=PROXIES,
            stream=True,
        )
        status_code = stream_response.status_code
        if status_code == 200:
            logger.success(status_code)
        else:
            logger.err(status_code)

        return stream_response

    def chat_return_dict(self, stream_response):
        # https://platform.openai.com/docs/guides/text-generation/chat-completions-response-format
        final_output = self.message_outputer.default_data.copy()
        final_output["choices"] = [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "",
                },
            }
        ]
        logger.back(final_output)

        final_content = ""
        for line in stream_response.iter_lines():
            if not line:
                continue
            content = self.parse_line(line)

            if content.strip() == self.stop_sequences:
                logger.success("\n[Finished]")
                break
            else:
                logger.back(content, end="")
                final_content += content

        if self.model in STOP_SEQUENCES_MAP.keys():
            final_content = final_content.replace(self.stop_sequences, "")

        final_content = final_content.strip()
        final_output["choices"][0]["message"]["content"] = final_content
        return final_output

    def chat_return_generator(self, stream_response):
        is_finished = False
        line_count = 0
        for line in stream_response.iter_lines():
            if line:
                line_count += 1
            else:
                continue

            content = self.parse_line(line)

            if content.strip() == self.stop_sequences:
                content_type = "Finished"
                logger.success("\n[Finished]")
                is_finished = True
            else:
                content_type = "Completions"
                if line_count == 1:
                    content = content.lstrip()
                logger.back(content, end="")

            output = self.message_outputer.output(
                content=content, content_type=content_type
            )
            yield output

        if not is_finished:
            yield self.message_outputer.output(content="", content_type="Finished")
