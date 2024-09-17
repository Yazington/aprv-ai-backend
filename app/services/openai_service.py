# import os
from typing import Generator

import openai
from fastapi import HTTPException

from app.config.settings import Settings

# openai_api_key = os.getenv("OPENAI_API_KEY")


# class Settings(BaseSettings):
#     openai_api_key: str

#     class Config:
#         env_file = ".env"


settings = Settings()  # type: ignore

client = openai.OpenAI(api_key=settings.openai_api_key)


def stream_openai_response(prompt: str, model: str = "gpt-4o") -> Generator[str, None, None]:
    """
    Streams tokens for a given query from OpenAI API
    """
    try:
        # The response should be typed as a synchronous generator
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
    except openai._exceptions.OpenAIError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    partial_message = ""
    try:
        for chunk in response:
            # Print the entire chunk to debug
            # print(f"Received chunk: {chunk}")

            delta = chunk.choices[0].delta

            if delta is not None and delta.content is not None:
                # Accumulate the partial message
                partial_message += delta.content
                yield delta.content

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# def main():
#     """
#     Test the stream_openai_response function by sending a prompt
#     and printing the streamed response in real-time.
#     """
#     prompt = "Hi, how are you?"
#     # response = stream_openai_response(prompt)
#     # print(json(response))
#     try:
#         for content in stream_openai_response(prompt):
#             print(content, end="", flush=True)
#     except HTTPException as e:
#         print(f"Error: {e.detail}")


# if __name__ == "__main__":
#     main()
