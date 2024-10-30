import base64
import json
from typing import Annotated, AsyncGenerator, Dict, List, Union

import openai
from fastapi import Depends
from odmantic import ObjectId
from tenacity import RetryError, retry, stop_after_attempt, wait_random_exponential

from app.config.logging_config import logger
from app.config.settings import settings
from app.models.llm_ready_page import BrandGuidelineReviewResource
from app.services.rag_service import RagService, get_rag_service

MODEL = "gpt-4o-mini"
MARKDOWN_POSTFIX_PROMPT = """
Please give the answer with Markdown format if you really need to
"""


class OpenAIClient:
    def __init__(self, rag_service: RagService):
        if settings and settings:
            self.async_client = openai.AsyncClient(api_key=settings.openai_api_key)
            # self.async_swarm = Swarm(client=self.async_client)
            self.rag_service = rag_service

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def stream_openai_llm_response(
        self,
        messages: List[Dict[str, str]],
        conversation_id: str,
        model: str = MODEL,
    ) -> AsyncGenerator[str, None]:

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_text_and_documents",
                    "description": """Document Uploads, Guidelines and all file related that have text are already
                    uploaded using this function.Retrieve relevant segments from documents based on a user query.""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": """The prompt or query text for which RAG results are needed.
                                If user needs to know what is in it, summarize it""",
                            },
                        },
                        "required": ["prompt"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        stream = await self.async_client.chat.completions.create(  # type: ignore
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
                logger.info("llm tool prompt: " + arguments["prompt"])
                # Execute the RAG function with extracted arguments
                rag_result = await self.rag_service.search_text_and_documents(arguments["prompt"], ObjectId(conversation_id))
                # print("rag results: ", rag_result)
                # Prepare a message with the RAG result to send back to the LLM
                new_messages = messages + [{"role": "system", "content": f"RAG result: {rag_result}"}]

                # Restart the stream with updated messages including the RAG result
                stream = await self.async_client.chat.completions.create(
                    model=model,
                    messages=new_messages,  # type: ignore
                    stream=True,
                )

                # Yield content from the new stream
                async for chunk in stream:
                    content = chunk.choices[0].delta.content or ""

                    yield content

            except json.JSONDecodeError:
                print("Failed to decode JSON arguments.")

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def get_openai_multi_images_response(
        self, system_prompt: str, prompt: str, design_image: bytes, non_design_images: List[bytes]
    ) -> Union[BrandGuidelineReviewResource, None]:
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
            llm_response = await self.async_client.beta.chat.completions.parse(
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
                        "content": [design_url_obj, *non_design_images_objects, {"type": "text", "text": prompt}],  # type: ignore
                    },
                ],
                response_format=BrandGuidelineReviewResource,
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


def get_openai_client(
    rag_service: Annotated[RagService, Depends(get_rag_service)],
):
    return OpenAIClient(rag_service)
