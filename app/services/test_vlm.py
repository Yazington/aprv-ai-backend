# import asyncio
# import sys
# from pathlib import Path


# # Add the parent directories to the system path
# sys.path.append(str(Path(__file__).parent.parent))
# print(sys.path)

# from services.openai_service import OpenAIClient
# from fastapi import UploadFile
# from lm.vlm import VLMService


# def main():
#     # Read the image file from the current directory
#     with open("./lm/Design #2.png", "rb") as f:
#         file = UploadFile(f)

#         # Create an instance of VisionLanguageModelService
#         vlm_service = VLMService()

#         # Call the method and print the output
#         asyncio.run(_test_infer_image_with_gpt(vlm_service, file))


# async def _test_infer_image_with_gpt(vlm_service: VLMService, file):
#     async for content in vlm_service.infer_image_with_gpt(file, openai_client=OpenAIClient()):
#         print(content, end="")


# if __name__ == "__main__":
#     main()
