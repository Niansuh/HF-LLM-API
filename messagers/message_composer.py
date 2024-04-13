import re
from pprint import pprint

from transformers import AutoTokenizer

from constants.models import AVAILABLE_MODELS, MODEL_MAP
from tclogger import logger


class MessageComposer:
    def __init__(self, model: str = None):
        if model in AVAILABLE_MODELS:
            self.model = model
        else:
            self.model = "mixtral-8x7b"
        self.model_fullname = MODEL_MAP[self.model]
        self.system_roles = ["system"]
        self.inst_roles = ["user", "system", "inst"]
        self.answer_roles = ["assistant", "bot", "answer", "model"]
        self.default_role = "user"

    def concat_messages_by_role(self, messages):
        def is_same_role(role1, role2):
            if (
                (role1 == role2)
                or (role1 in self.inst_roles and role2 in self.inst_roles)
                or (role1 in self.answer_roles and role2 in self.answer_roles)
            ):
                return True
            else:
                return False

        concat_messages = []
        for message in messages:
            role = message["role"]
            content = message["content"]
            if concat_messages and is_same_role(role, concat_messages[-1]["role"]):
                concat_messages[-1]["content"] += "\n" + content
            else:
                if role in self.inst_roles:
                    message["role"] = "inst"
                elif role in self.answer_roles:
                    message["role"] = "answer"
                else:
                    message["role"] = "inst"
                concat_messages.append(message)
        return concat_messages

    def merge(self, messages) -> str:
        # Templates for Chat Models
        #   - https://huggingface.co/docs/transformers/main/en/chat_templating
        #   - https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1#instruction-format
        #   - https://huggingface.co/NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO#prompt-format
        #   - https://huggingface.co/HuggingFaceH4/zephyr-orpo-141b-A35b-v0.1
        #   - https://huggingface.co/google/gemma-1.1-7b-it#chat-template

        # Mistral and Mixtral:
        #   <s> [INST] Instruction [/INST] Model answer </s> [INST] Follow-up instruction [/INST]

        # Nous Mixtral:
        #   <|im_start|>system
        #   You are "Hermes 2".<|im_end|>
        #   <|im_start|>user
        #   Hello, who are you?<|im_end|>
        #   <|im_start|>assistant

        # HuggingFaceH4:
        #   zephyr-orpo-141b Correct User: Hello<|end_of_turn|>zephyr-orpo-141b Correct Assistant: Hi<|end_of_turn|>zephyr-orpo-141b Correct User: How are you today?<|end_of_turn|>zephyr-orpo-141b Correct Assistant:

        # Google Gemma-it
        # <start_of_turn>user
        # How does the brain work?<end_of_turn>
        # <start_of_turn>model

        self.messages = messages
        self.merged_str = ""

        # https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1#instruction-format
        if self.model in ["mixtral-8x7b", "mistral-7b"]:
            self.messages = self.concat_messages_by_role(messages)
            self.cached_str = ""
            for message in self.messages:
                role = message["role"]
                content = message["content"]
                if role in self.inst_roles:
                    self.cached_str = f"[INST] {content} [/INST]"
                elif role in self.answer_roles:
                    self.merged_str += f"<s> {self.cached_str} {content} </s>\n"
                    self.cached_str = ""
                else:
                    self.cached_str = f"[INST] {content} [/INST]"
            if self.cached_str:
                self.merged_str += f"{self.cached_str}"
        # https://huggingface.co/NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO#prompt-format
        elif self.model in ["nous-mixtral-8x7b"]:
            self.merged_str_list = []
            for message in self.messages:
                role = message["role"]
                content = message["content"]
                if role not in ["system", "user", "assistant"]:
                    role = self.default_role
                message_line = f"<|im_start|>{role}\n{content}<|im_end|>"
                self.merged_str_list.append(message_line)
            self.merged_str_list.append("<|im_start|>assistant")
            self.merged_str = "\n".join(self.merged_str_list)
        # https://huggingface.co/HuggingFaceH4/zephyr-orpo-141b-A35b-v0.1
        elif self.model in ["zephyr-orpo-141b"]:
            self.messages = self.concat_messages_by_role(messages)
            self.merged_str_list = []
            self.end_of_turn = "<|end_of_turn|>"
            for message in self.messages:
                role = message["role"]
                content = message["content"]
                if role in self.inst_roles:
                    self.merged_str_list.append(
                        f"zephyr-orpo-141b Correct User:\n{content}{self.end_of_turn}"
                    )
                elif role in self.answer_roles:
                    self.merged_str_list.append(
                        f"zephyr-orpo-141b Correct Assistant:\n{content}{self.end_of_turn}"
                    )
                else:
                    self.merged_str_list.append(
                        f"zephyr-orpo-141b Correct User: {content}{self.end_of_turn}"
                    )
            self.merged_str_list.append(f"zephyr-orpo-141b Correct Assistant:\n")
            self.merged_str = "\n".join(self.merged_str_list)
        # https://huggingface.co/google/gemma-1.1-7b-it#chat-template
        elif self.model in ["gemma-1.1-7b"]:
            self.messages = self.concat_messages_by_role(messages)
            self.merged_str_list = []
            self.end_of_turn = "<end_of_turn>"
            self.start_of_turn = "<start_of_turn>"
            for message in self.messages:
                role = message["role"]
                content = message["content"]
                if role in self.inst_roles:
                    self.merged_str_list.append(
                        f"{self.start_of_turn}user\n{content}{self.end_of_turn}"
                    )
                elif role in self.answer_roles:
                    self.merged_str_list.append(
                        f"{self.start_of_turn}model\n{content}{self.end_of_turn}"
                    )
                else:
                    self.merged_str_list.append(
                        f"{self.start_of_turn}user\n{content}{self.end_of_turn}"
                    )
            self.merged_str_list.append(f"{self.start_of_turn}model\n")
            self.merged_str = "\n".join(self.merged_str_list)
        # https://huggingface.co/NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO#prompt-format
        # https://huggingface.co/HuggingFaceH4/zephyr-orpo-141b
        # elif self.model in ["zephyr-orpo-141b", "nous-mixtral-8x7b"]:
        elif self.model in ["zephyr-orpo-141b", "command-r-plus"]:
            tokenizer = AutoTokenizer.from_pretrained(self.model_fullname)
            self.merged_str = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            self.merged_str = "\n\n".join(
                [f"{message['role']}: {message['content']}" for message in messages]
            )

        return self.merged_str


if __name__ == "__main__":
    # model = "mixtral-8x7b"
    # model = "nous-mixtral-8x7b"
    # model = "gemma-1.1-7b"
    # model = "zephyr-orpo-141b"
    model = "command-r-plus"
    composer = MessageComposer(model)
    messages = [
        {
            "role": "system",
            "content": "You are Zephyr, an assistant developed by KAIST AI, Argilla, and Hugging Face. You should give concise responses to very simple questions, but provide thorough responses to more complex and open-ended questions. You are happy to help with writing, analysis, question answering, math, coding, and all sorts of other tasks.",
        },
        {"role": "user", "content": "Hello, who are you?"},
        {"role": "assistant", "content": "I am a bot."},
        {"role": "user", "content": "What is your name?"},
        # {"role": "assistant", "content": "My name is Bing."},
        # {"role": "user", "content": "Tell me a joke."},
        # {"role": "assistant", "content": "What is a robot's favorite type of music?"},
        # {
        #     "role": "user",
        #     "content": "How many questions have I asked? Please list them.",
        # },
    ]
    logger.note(f"model: {composer.model}")
    merged_str = composer.merge(messages)
    logger.note("merged_str:")
    logger.mesg(merged_str)

    # python -m messagers.message_composer
