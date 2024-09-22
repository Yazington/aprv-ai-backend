# import asyncio
# import json
from typing import AsyncGenerator

# import aiohttp
import openai
from config.settings import settings

# from fastapi import HTTPException

# settings = Settings()  # type: ignore
# print("here: ", settings.openai_api_key)
# client = openai.OpenAI(api_key=settings.openai_api_key)


# from dotenv import load_dotenv

# load_dotenv()
# from pydantic_settings import BaseSettings
# openai_api_key = os.getenv("OPENAI_API_KEY")


# if openai_api_key is None:
#     exit(1)

client = openai.OpenAI(api_key=settings.openai_api_key)


async def stream_openai_response(prompt: str, model: str = "gpt-3.5-turbo") -> AsyncGenerator[str, None]:
    """
    Streams tokens for a given query from OpenAI API using the SDK.
    """
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": f"{prompt}"}],
        stream=True,
    )
    for chunk in stream:
        yield chunk.choices[0].delta.content or ""


# async def main():
#     prompt = "What is the capital of France?"
#     async for token in stream_openai_response(prompt):
#         print(token, end="")


# # Run the test script using asyncio
# if __name__ == "__main__":
#     asyncio.run(main())
