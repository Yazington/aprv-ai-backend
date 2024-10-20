import base64
from typing import AsyncGenerator, List, Union

import openai
from config.settings import settings
from fastapi import Depends
from models.llm_ready_page import BrandGuideline
from swarm import Swarm  # type:ignore
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

MODEL = "gpt-4o-mini"
MARKDOWN_POSTFIX_PROMPT = """
Please give the answer with Markdown format if you really need to
"""


class OpenAIClient:
    def __init__(self):
        if settings and settings.openai_api_key:
            self.async_client = openai.AsyncClient(api_key=settings.openai_api_key)
            self.client = openai.OpenAI(api_key=settings.aprv_ai_api_key)
            self.async_swarm = Swarm(client=self.async_client)
            self.swarm = Swarm(client=self.client)

    async def stream_openai_llm_response(self, prompt: str, model: str = MODEL) -> AsyncGenerator[str, None]:
        """
        Streams tokens for a given query from OpenAI API using the SDK.
        """
        stream = await self.async_client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": f"{ prompt}"}], stream=True
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content

    async def stream_openai_vision_response(self, prompt: str, image: bytes) -> AsyncGenerator[str, None]:
        """
        Streams tokens for a given query from OpenAI API using the SDK with an image.
        """
        # Convert image to base64 encoded string
        image_base64 = base64.b64encode(image).decode("utf-8")

        stream = await self.async_client.chat.completions.create(
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

        stream = await self.async_client.chat.completions.create(
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

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def get_openai_multi_images_response(
        self, system_prompt: str, prompt: str, design_image: bytes, non_design_images: List[bytes]
    ) -> Union[BrandGuideline, None]:
        """
        Get tokens for a given query from OpenAI API using multiple images.
        first image should always be the design
        """
        design_base64 = base64.b64encode(design_image).decode("utf-8")

        non_design_images_objects = []
        for non_design_image in non_design_images:
            non_design_base64 = base64.b64encode(non_design_image).decode("utf-8")
            non_design_url_obj = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{non_design_base64}"}}
            non_design_images_objects.append(non_design_url_obj)

        design_url_obj = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{design_base64}"}}

        llm_response = self.client.beta.chat.completions.parse(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system_prompt,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [design_url_obj, *non_design_images_objects, {"type": "text", "text": prompt}],
                },
            ],
            response_format=BrandGuideline,
        )
        if not llm_response.choices[0].message.parsed:
            return None
        return llm_response.choices[0].message.parsed


def get_openai_client():
    return OpenAIClient()


openai_client: OpenAIClient = Depends(get_openai_client)
