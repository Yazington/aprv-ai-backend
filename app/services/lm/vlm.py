import os
from io import BytesIO
from typing import List

import motor
import pymongo
import torch
from fastapi import Depends, UploadFile
from gridfs import GridFS
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridOut
from odmantic import AIOEngine, ObjectId
from PIL import Image
from services.openai_service import OpenAIClient, openai_client
from transformers import AutoProcessor, MllamaForConditionalGeneration


class VLMService:
    def __init__(self):
        self.model_id = "meta-llama/Llama-3.2-11B-Vision-Instruct"
        # self.model = MllamaForConditionalGeneration.from_pretrained(
        #     self.model_id,
        #     torch_dtype=torch.bfloat16,
        #     device_map="auto",
        # )
        # self.processor = AutoProcessor.from_pretrained(self.model_id)

    # async def infer_image_with_llama(self, file: UploadFile, prompt: str = "Describe in a lot of details what you see in the image"):
    #     # Load the image from the uploaded file
    #     image = Image.open(BytesIO(await file.read()))

    #     # Prepare the input for the model
    #     messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    #     input_text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
    #     inputs = self.processor(image, input_text, add_special_tokens=False, return_tensors="pt").to(self.model.device)

    #     # Generate output from the model
    #     output = self.model.generate(**inputs, max_new_tokens=30)
    #     description = self.processor.decode(output[0])

    #     return {"description": description}

    async def infer_image_with_gpt(
        self,
        file: UploadFile,
        prompt: str = "Describe in a lot of details what you see in the image",
        openai_client: OpenAIClient = openai_client,
    ):
        # Load the image from the uploaded file
        image = Image.open(BytesIO(await file.read()))

        # Convert image to bytes (if necessary)
        byte_stream = BytesIO()
        image.save(byte_stream, format="PNG")
        byte_array = byte_stream.getvalue()

        async for content in openai_client.stream_openai_vision_response(prompt=prompt, image=byte_array):
            yield content

    async def infer_images_with_gpt_from_gridfs_stream(
        self,
        grid_out_contract: AsyncIOMotorGridOut,  # pdf
        grid_out_design: AsyncIOMotorGridOut,  # design_image
        prompt: str = "Describe in a lot of details what you see in the images",
        openai_client: OpenAIClient = openai_client,
    ):
        """
        Takes GridFS file streams (grid_out objects), converts them to bytes, and streams responses from GPT with multi-image input.
        """
        images: List[bytes] = []
        contract_file_data = await grid_out_contract.read()
        design_file_data = await grid_out_design.read()
        design_image = Image.open(BytesIO(design_file_data))
        byte_stream = BytesIO()
        design_image.save(byte_stream, format="PNG")  # Save it in PNG format or another suitable format
        images.append(byte_stream.getvalue())  # Append byte array to the list

        # Use the method to stream multi-image responses
        async for content in openai_client.stream_openai_multi_images_response(
            system_prompt="You are a brand licensing professional reviewing designs against brand licensing guidelines",
            prompt=prompt,
            images=images,
        ):
            yield content


# async def main(file_ids: List[str]):
#     from dotenv import load_dotenv

#     load_dotenv()


#     db_url = "mongodb://root:example@localhost:27017/"
#     # Use AsyncIOMotorClient for asynchronous operations
#     client = AsyncIOMotorClient(db_url)
#     database_name = "aprv-ai"
#     db_async = client[database_name]
#     engine = AIOEngine(client=client, database=database_name)

#     # Use pymongo.MongoClient for GridFS
#     client_sync = pymongo.MongoClient(db_url)
#     db_sync = client_sync[database_name]
#     fs = GridFS(db_sync)

#     # List to store the grid_out objects
#     contract_id = ObjectId("670beef6f012d80d1543b937")
#     design_id = ObjectId("670beef9f012d80d1543b948")

#     contract_file = fs.find_one({"_id", contract_id})
#     design_file = fs.find_one({"_id", design_id})

#     vlm_service = VLMService()
#     openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))
#     vlm_service.infer_images_with_gpt_from_gridfs_stream()
#     # Fetch the files from GridFS using the provided file IDs
#     for file_id in file_ids:
#         # Retrieve each file using the file_id
#         grid_out = await your_instance.fs.open_download_stream(file_id)
#         grid_out_files.append(grid_out)

#     # Execute the infer_images_with_gpt_from_gridfs_stream method
#     async for content in your_instance.infer_images_with_gpt_from_gridfs_stream(
#         grid_out_files=grid_out_files,
#         prompt="Describe in detail what you see in the images",
#         openai_client=openai_client,
#     ):
#         print(content)


# if __name__ == "__main__":
#     # Replace these with actual file IDs from your GridFS
#     file_ids = ["603dca7d0f1e4b6c4e9c87e1", "603dca7d0f1e4b6c4e9c87e2"]  # Example file IDs
#     run(main(file_ids))


def get_vlm_service():
    return VLMService()


vlm_service: VLMService = Depends(get_vlm_service)
