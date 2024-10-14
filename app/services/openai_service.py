import base64
from typing import AsyncGenerator, List

import openai
from config.settings import settings
from fastapi import Depends
from main import MODEL


class OpenAIClient:
    def __init__(self):
        if settings and settings.openai_api_key:
            self.client = openai.AsyncClient(api_key=settings.openai_api_key)

    async def stream_openai_llm_response(self, prompt: str, model: str = MODEL) -> AsyncGenerator[str, None]:
        """
        Streams tokens for a given query from OpenAI API using the SDK.
        """
        stream = await self.client.chat.completions.create(model=model, messages=[{"role": "user", "content": f"{prompt}"}], stream=True)

        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content

    async def stream_openai_vision_response(self, prompt: str, image: bytes) -> AsyncGenerator[str, None]:
        """
        Streams tokens for a given query from OpenAI API using the SDK with an image.
        """
        # Convert image to base64 encoded string
        image_base64 = base64.b64encode(image).decode("utf-8")

        stream = await self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            stream=True,
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content

    async def stream_openai_multi_images_response(self, prompt: str, design: bytes, non_design: bytes) -> AsyncGenerator[str, None]:
        """
        Streams tokens for a given query from OpenAI API using multiple images.
        first image should always be the design
        """
        design_base64 = base64.b64encode(design).decode("utf-8")
        non_design_base64 = base64.b64encode(non_design).decode("utf-8")

        design_url_obj = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{design_base64}"}}
        non_design_url_obj = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{non_design_base64}"}}

        stream = await self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [design_url_obj, non_design_url_obj, {"type": "text", "text": prompt}],
                }
            ],
            stream=True,
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content


def get_openai_client():
    return OpenAIClient()


openai_client: OpenAIClient = Depends(get_openai_client)
