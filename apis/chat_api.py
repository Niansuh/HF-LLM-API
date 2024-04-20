import argparse
import markdown2
import os
import sys
import uvicorn

from pathlib import Path
from typing import Union

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from tclogger import logger

from constants.models import AVAILABLE_MODELS_DICTS, PRO_MODELS
from constants.envs import CONFIG, SECRETS
from networks.exceptions import HfApiException, INVALID_API_KEY_ERROR

from messagers.message_composer import MessageComposer
from mocks.stream_chat_mocker import stream_chat_mock

from networks.huggingface_streamer import HuggingfaceStreamer
from networks.huggingchat_streamer import HuggingchatStreamer
from networks.openai_streamer import OpenaiStreamer


class ChatAPIApp:
    def __init__(self):
        self.app = FastAPI(
            docs_url="/",
            title=CONFIG["app_name"],
            swagger_ui_parameters={"defaultModelsExpandDepth": -1},
            version=CONFIG["version"],
        )
        self.setup_routes()

    def get_available_models(self):
        return {"object": "list", "data": AVAILABLE_MODELS_DICTS}

    def extract_api_key(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    ):
        api_key = None
        if credentials:
            api_key = credentials.credentials
        env_api_key = SECRETS["HF_LLM_API_KEY"]
        return api_key

    def auth_api_key(self, api_key: str):
        env_api_key = SECRETS["HF_LLM_API_KEY"]

        # require no api_key
        if not env_api_key:
            return None
        # user provides HF_TOKEN
        if api_key and api_key.startswith("hf_"):
            return api_key
        # user provides correct API_KEY
        if str(api_key) == str(env_api_key):
            return None

        raise INVALID_API_KEY_ERROR

    class ChatCompletionsPostItem(BaseModel):

        model: str = Field(
            default="nous-mixtral-8x7b",
            description="(str) `nous-mixtral-8x7b`",
        )
        messages: list = Field(
            default=[{"role": "user", "content": "Hello, who are you?"}],
            description="(list) Messages",
        )
        temperature: Union[float, None] = Field(
            default=0.5,
            description="(float) Temperature",
        )
        top_p: Union[float, None] = Field(
            default=0.95,
            description="(float) top p",
        )
        max_tokens: Union[int, None] = Field(
            default=-1,
            description="(int) Max tokens",
        )
        use_cache: bool = Field(
            default=False,
            description="(bool) Use cache",
        )
        stream: bool = Field(
            default=True,
            description="(bool) Stream",
        )

    def chat_completions(
        self, item: ChatCompletionsPostItem, api_key: str = Depends(extract_api_key)
    ):
        try:
            api_key = self.auth_api_key(api_key)

            if item.model == "gpt-3.5-turbo":
                streamer = OpenaiStreamer()
                stream_response = streamer.chat_response(messages=item.messages)
            elif item.model in PRO_MODELS:
                streamer = HuggingchatStreamer(model=item.model)
                stream_response = streamer.chat_response(
                    messages=item.messages,
                )
            else:
                streamer = HuggingfaceStreamer(model=item.model)
                composer = MessageComposer(model=item.model)
                composer.merge(messages=item.messages)
                stream_response = streamer.chat_response(
                    prompt=composer.merged_str,
                    temperature=item.temperature,
                    top_p=item.top_p,
                    max_new_tokens=item.max_tokens,
                    api_key=api_key,
                    use_cache=item.use_cache,
                )

            if item.stream:
                event_source_response = EventSourceResponse(
                    streamer.chat_return_generator(stream_response),
                    media_type="text/event-stream",
                    ping=2000,
                    ping_message_factory=lambda: ServerSentEvent(**{"comment": ""}),
                )
                return event_source_response
            else:
                data_response = streamer.chat_return_dict(stream_response)
                return data_response
        except HfApiException as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def get_readme(self):
        readme_path = Path(__file__).parents[1] / "README.md"
        with open(readme_path, "r", encoding="utf-8") as rf:
            readme_str = rf.read()
        readme_html = markdown2.markdown(
            readme_str, extras=["table", "fenced-code-blocks", "highlightjs-lang"]
        )
        return readme_html

    def setup_routes(self):
        for prefix in ["", "/v1", "/api", "/api/v1"]:
            if prefix in ["/api/v1"]:
                include_in_schema = True
            else:
                include_in_schema = False

            self.app.get(
                prefix + "/models",
                summary="Get available models",
                include_in_schema=include_in_schema,
            )(self.get_available_models)

            self.app.post(
                prefix + "/chat/completions",
                summary="Chat completions in conversation session",
                include_in_schema=include_in_schema,
            )(self.chat_completions)
        self.app.get(
            "/readme",
            summary="README of HF LLM API",
            response_class=HTMLResponse,
            include_in_schema=False,
        )(self.get_readme)


class ArgParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(ArgParser, self).__init__(*args, **kwargs)

        self.add_argument(
            "-s",
            "--host",
            type=str,
            default=CONFIG["host"],
            help=f"Host for {CONFIG['app_name']}",
        )
        self.add_argument(
            "-p",
            "--port",
            type=int,
            default=CONFIG["port"],
            help=f"Port for {CONFIG['app_name']}",
        )

        self.add_argument(
            "-d",
            "--dev",
            default=False,
            action="store_true",
            help="Run in dev mode",
        )

        self.args = self.parse_args(sys.argv[1:])


app = ChatAPIApp().app

if __name__ == "__main__":
    args = ArgParser().args
    if args.dev:
        uvicorn.run("__main__:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run("__main__:app", host=args.host, port=args.port, reload=False)

    # python -m apis.chat_api      # [Docker] on product mode
    # python -m apis.chat_api -d   # [Dev]    on develop mode
