import base64
import json
from typing import AsyncGenerator, Dict, List, Union

import httpx
import openai
from config.logging_config import logger
from config.settings import settings
from fastapi import Depends
from models.llm_ready_page import BrandGuideline
from odmantic import ObjectId
from services.mongo_service import MongoService
from services.rag_service import search_text_and_documents
from swarm import Swarm  # type:ignore
from tenacity import (
    RetryError,
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

    async def stream_openai_llm_response(
        self, messages: List[Dict[str, str]], mongo_service: MongoService, conversation_id: str, model: str = MODEL
    ) -> AsyncGenerator[str, None]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_text_and_documents",
                    "description": "Document Uploads, Guidelines and all file related that have text are already uploaded using this function. Retrieve relevant segments from documents based on a user query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "The prompt or query text for which RAG results are needed.",
                            },
                        },
                        "required": ["prompt"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        stream = await self.async_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=True,
        )

        cumulative_arguments = ""

        is_calling_function = False
        async for chunk in stream:
            tool_call_info = None
            if chunk.choices[0].delta.tool_calls:
                tool_call_info = chunk.choices[0].delta.tool_calls[0]

            if tool_call_info and tool_call_info.function.name == "search_text_and_documents" or is_calling_function:
                # Accumulate JSON arguments
                is_calling_function = True
                if tool_call_info:
                    cumulative_arguments += tool_call_info.function.arguments
                # print(cumulative_arguments)

                # Check if the JSON is complete
                if cumulative_arguments.startswith("{") and cumulative_arguments.endswith("}"):
                    break  # Exit the loop after accumulating complete JSON
            else:
                content = chunk.choices[0].delta.content or ""
                yield content

        # After exiting the loop, process the complete JSON
        if cumulative_arguments:
            try:
                arguments = json.loads(cumulative_arguments)
                # print(arguments)
                cumulative_arguments = ""  # Reset for future usage
                # print(f"Complete Tool call arguments: {arguments}")

                # Execute the RAG function with extracted arguments
                rag_result = await search_text_and_documents(arguments["prompt"], conversation_id, mongo_service)
                # print("rag results: ", rag_result)
                # Prepare a message with the RAG result to send back to the LLM
                new_messages = messages + [{"role": "system", "content": f"RAG result: {rag_result}"}]

                # Restart the stream with updated messages including the RAG result
                stream = await self.async_client.chat.completions.create(
                    model=model,
                    messages=new_messages,
                    stream=True,
                )

                # Yield content from the new stream
                async for chunk in stream:
                    content = chunk.choices[0].delta.content or ""

                    yield content

            except json.JSONDecodeError:
                print("Failed to decode JSON arguments.")

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

        try:
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
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} {e.response.text}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def get_openai_multi_images_response(
        self, system_prompt: str, prompt: str, design_image: bytes, non_design_images: List[bytes]
    ) -> Union[BrandGuideline, None]:
        """
        Get tokens for a given query from OpenAI API using multiple images.
        first image should always be the design.
        """
        try:
            # Convert design image to base64
            design_base64 = base64.b64encode(design_image).decode("utf-8")
            design_url_obj = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{design_base64}"}}

            # Convert non-design images to base64
            non_design_images_objects = []
            for non_design_image in non_design_images:
                non_design_base64 = base64.b64encode(non_design_image).decode("utf-8")
                non_design_url_obj = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{non_design_base64}"}}
                non_design_images_objects.append(non_design_url_obj)

            # Make the API call
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

            # Check if the response contains parsed content
            if not llm_response.choices[0].message.parsed:
                logger.warning("OpenAI API response has no parsed content.")
                return None

            return llm_response.choices[0].message.parsed

        except RetryError as e:
            logger.error(f"Task failed after retries: {e}")
            raise
        except Exception as e:
            logger.error(f"Error occurred during OpenAI API call: {str(e)}. Prompt: {prompt}, System Prompt: {system_prompt}")
            raise


def get_openai_client():
    return OpenAIClient()


openai_client: OpenAIClient = Depends(get_openai_client)
