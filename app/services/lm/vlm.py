from io import BytesIO

import torch
from fastapi import Depends, UploadFile
from PIL import Image
from services.openai_service import OpenAIClient, openai_client
from transformers import AutoProcessor, MllamaForConditionalGeneration


class VLMService:
    def __init__(self):
        self.model_id = "meta-llama/Llama-3.2-11B-Vision-Instruct"
        self.model = MllamaForConditionalGeneration.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.processor = AutoProcessor.from_pretrained(self.model_id)

    async def infer_image_with_llama(self, file: UploadFile, prompt: str = "Describe in a lot of details what you see in the image"):
        # Load the image from the uploaded file
        image = Image.open(BytesIO(await file.read()))

        # Prepare the input for the model
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        input_text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(image, input_text, add_special_tokens=False, return_tensors="pt").to(self.model.device)

        # Generate output from the model
        output = self.model.generate(**inputs, max_new_tokens=30)
        description = self.processor.decode(output[0])

        return {"description": description}

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


def get_vlm_service():
    return VLMService()


vlm_service: VLMService = Depends(get_vlm_service)
