import base64
import json
from typing import Annotated, AsyncGenerator, Dict, List, Union

import openai
from fastapi import Depends
from tenacity import RetryError, retry, stop_after_attempt, wait_random_exponential

from app.config.logging_config import logger
from app.config.settings import settings
from app.models.llm_ready_page import BrandGuidelineReviewResource
from app.utils.llm_tools import LLMToolsService, get_llm_tools_service

MODEL = "gpt-4o"
MARKDOWN_POSTFIX_PROMPT = """
Please give the answer with Markdown format if you really need to
"""


class OpenAIClient:
    def __init__(self, llm_tools_service: LLMToolsService):
        if settings and settings:
            self.async_client = openai.AsyncClient(api_key=settings.openai_api_key)
        self.llm_tools_service = llm_tools_service

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def stream_openai_llm_response(
        self,
        messages: List[Dict[str, str]],
        conversation_id: str,
        model: str = MODEL,
    ) -> AsyncGenerator[str, None]:
        stream = await self.async_client.chat.completions.create(  # type: ignore
            model=model,
            messages=messages,
            tools=LLMToolsService.AVAILABLE_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            stream=True,
        )

        tool_call_arguments_from_llm = []
        has_tool_call = False
        function_name = None

        async for chunk in stream:
            is_openai_response_tool_call = (
                chunk.choices[0].delta.tool_calls
                and len(chunk.choices[0].delta.tool_calls) > 0
            )
            if is_openai_response_tool_call:
                has_tool_call = True
                tool_call_arguments_from_llm.append(
                    chunk.choices[0].delta.tool_calls[0].function.arguments
                )
                if chunk.choices[0].delta.tool_calls[0].function.name:
                    function_name = chunk.choices[0].delta.tool_calls[0].function.name
                    yield "\n\n[TOOL_USAGE_APRV_AI]:" + function_name.replace("_", " ")
                continue
            else:
                content = chunk.choices[0].delta.content or ""
                yield content

        allowed_function_names: List[str] = [
            tool["function"]["name"] for tool in self.llm_tools_service.AVAILABLE_TOOLS
        ]

        if has_tool_call and function_name:
            try:
                arguments = json.loads("".join(tool_call_arguments_from_llm))

                # Validate the function name
                if function_name not in allowed_function_names:
                    raise ValueError(f"Unauthorized or invalid method call: {function_name}")

                logger.info(f"Complete Tool call arguments: {arguments}")
                logger.info("llm tool prompt: " + arguments.get("prompt", ""))

                # Dynamically get the method using reflection
                method_to_call = getattr(self.llm_tools_service, function_name, None)


                if function_name == "get_current_conversation_id":
                    tool_result = "conversation_id: " + conversation_id

                elif method_to_call and callable(method_to_call):
                    # Call the method with unpacked arguments
                    tool_result = await method_to_call(**arguments)
                else:
                    raise AttributeError(
                        f"Method '{function_name}' not found or not callable in llm_tools_service"
                    )
                # if isinstance(tool_result, str):
                #     if len(tool_result) > 100:
                #         log_tool_result = tool_result[:40] + "..." + tool_result[-40:]
                #     else:
                #         log_tool_result = tool_result
                # else:
                #     log_tool_result = str(tool_result)  # Ensure it's stringified
                # logger.info(f"tool_result: {log_tool_result}")

                new_messages = messages + [
                    {"role": "user", "content": f"'calling this tool:{function_name}' gave us: {tool_result}"}
                ]
                yield "\n\n[TOOL_USAGE_APRV_AI_DONE]:" + " ".join(function_name.split("_")) + "\n\n"

                nested_generator = self.stream_openai_llm_response(
                    new_messages, conversation_id, model
                )
                async for content in nested_generator:
                    yield content
            except Exception as e:
                logger.error(f"Error during tool call execution: {str(e)}")
                raise



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


def get_openai_client(llm_tools_service: Annotated[LLMToolsService, Depends(get_llm_tools_service)]):
    return OpenAIClient(llm_tools_service)
