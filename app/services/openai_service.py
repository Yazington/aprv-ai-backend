# OpenAI Service Implementation
# This module provides an interface to OpenAI's API with additional functionality for:
# - Streaming LLM responses with tool integration
# - Handling multi-image inputs for design review
# - Automatic retry logic for API calls

import asyncio
import base64
import json
from typing import Annotated, AsyncGenerator, List, Union

import openai
from fastapi import Depends
from openai.types.chat import ChatCompletionMessageParam
from tenacity import RetryError, retry, stop_after_attempt, wait_random_exponential

from app.config.logging_config import logger
from app.config.settings import settings
from app.models.llm_ready_page import BrandGuidelineReviewResource
from app.utils.llm_tools import LLMToolsService, get_llm_tools_service

# Default model to use for OpenAI API calls
MODEL = "gpt-4"
# Prompt suffix to encourage Markdown formatting in responses
MARKDOWN_POSTFIX_PROMPT = """
Please give the answer with Markdown format if you really need to
"""


class OpenAIClient:
    """Main client class for interacting with OpenAI API with additional features:
    - Tool integration for extended functionality
    - Streaming responses with tool call handling
    - Multi-image processing capabilities
    """

    def __init__(self, llm_tools_service: LLMToolsService):
        """Initialize the OpenAI client with required services.

        Args:
            llm_tools_service: Service providing additional LLM tool functionality
        """
        if settings and settings:
            self.async_client = openai.AsyncClient(api_key=settings.openai_api_key)
        self.llm_tools_service = llm_tools_service

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def _handle_tool_call(
        self,
        function_name: str,
        tool_call_arguments: List[str],
        messages: List[ChatCompletionMessageParam],
        conversation_id: str,
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Handle tool calls and their responses."""
        allowed_function_names: List[str] = [tool["function"]["name"] for tool in self.llm_tools_service.AVAILABLE_TOOLS]

        try:
            arguments = json.loads("".join(tool_call_arguments))
            if function_name not in allowed_function_names:
                raise ValueError(f"Unauthorized or invalid method call: {function_name}")

            logger.info(f"Complete Tool call arguments: {arguments}")
            logger.info("llm tool prompt: " + arguments.get("prompt", ""))

            method_to_call = getattr(self.llm_tools_service, function_name, None)
            # print("function name: ", function_name)
            # print("all messages: ", messages)

            if function_name == "get_current_conversation_id":
                tool_result = "conversation_id: " + conversation_id
            elif method_to_call and callable(method_to_call):
                if asyncio.iscoroutinefunction(method_to_call):
                    tool_result = await method_to_call(**arguments)
                else:
                    tool_result = method_to_call(**arguments)
            else:
                raise AttributeError(f"Method '{function_name}' not found or not callable in llm_tools_service")

            print("tool_result: ", tool_result)
            new_messages = messages + [{"role": "user", "content": f"'calling this tool:{function_name}' gave us: {tool_result}"}]
            print("all messages: ", new_messages)

            yield "\n\n[TOOL_USAGE_APRV_AI_DONE]:" + " ".join(function_name.split("_")) + "\n\n"

            nested_generator = self.stream_openai_llm_response(new_messages, conversation_id, model)
            async for content in nested_generator:
                yield content
        except Exception as e:
            logger.error(f"Error during tool call execution: {str(e)}")
            raise

    async def stream_openai_llm_response(
        self,
        messages: List[ChatCompletionMessageParam],
        conversation_id: str,
        model: str = MODEL,
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI LLM responses with tool integration.

        Args:
            messages: List of message dictionaries with role/content pairs
            conversation_id: Unique identifier for the conversation
            model: OpenAI model to use (defaults to gpt-4o)

        Yields:
            str: Streamed response content or tool call indicators
        """
        stream = await self.async_client.chat.completions.create(  # type: ignore
            model=model,
            messages=messages,
            tools=LLMToolsService.AVAILABLE_TOOLS,
            tool_choice="auto",
            stream=True,
        )

        tool_call_arguments_from_llm = []
        has_tool_call = False
        function_name = None

        async for chunk in stream:
            is_openai_response_tool_call = chunk.choices[0].delta.tool_calls and len(chunk.choices[0].delta.tool_calls) > 0

            if is_openai_response_tool_call and chunk.choices[0].delta.tool_calls:
                has_tool_call = True
                tool_call = chunk.choices[0].delta.tool_calls[0]
                if tool_call and tool_call.function and tool_call.function.arguments:
                    tool_call_arguments_from_llm.append(tool_call.function.arguments)

                if tool_call and tool_call.function and tool_call.function.name:
                    function_name = tool_call.function.name
                    yield "\n\n[TOOL_USAGE_APRV_AI]:" + function_name.replace("_", " ")
                continue
            else:
                content = chunk.choices[0].delta.content or ""
                yield content

        if has_tool_call and function_name:
            async for content in self._handle_tool_call(function_name, tool_call_arguments_from_llm, messages, conversation_id, model):
                yield content

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def get_openai_multi_images_response(
        self, system_prompt: str, prompt: str, design_image: bytes, non_design_images: List[bytes]
    ) -> Union[BrandGuidelineReviewResource, None]:
        """Process multiple images through OpenAI API for design review.

        Args:
            system_prompt: System-level instructions for the model
            prompt: User-provided prompt/query
            design_image: Primary design image bytes
            non_design_images: List of reference image bytes

        Returns:
            BrandGuidelineReviewResource: Parsed response from OpenAI
            None: If no valid response was received

        Note:
            - First image is always treated as the design
            - Implements exponential backoff retry logic
            - Handles base64 encoding of images
            - Validates response format
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

            # Make the API call with combined image and text content
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

            # Validate response contains parsed content
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


def get_openai_client(llm_tools_service: Annotated[LLMToolsService, Depends(get_llm_tools_service)]):
    """Dependency injection factory for OpenAIClient.

    Args:
        llm_tools_service: Injected LLM tools service

    Returns:
        OpenAIClient: Configured OpenAI client instance
    """
    return OpenAIClient(llm_tools_service)
