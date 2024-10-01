from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from models.message import Message
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service
from services.openai_service import stream_openai_response

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/create_prompt")
async def create_prompt(prompt: str = Body(..., embed=True), mongo_service: MongoService = mongo_service):
    message = Message(is_from_human=True, content=prompt)
    await mongo_service.engine.save(message)
    return {"prompt": message}


@router.get("/generate/{message_id}")
async def get_prompt_model_response(message_id: str, mongo_service: MongoService = mongo_service):
    prompt_message = await mongo_service.engine.find_one(Message, Message.id == ObjectId(message_id))

    if prompt_message is None:
        raise HTTPException(status_code=404, detail=f"Failed to generate response as initial prompt was not found : {message_id}")

    async def event_generator() -> AsyncGenerator[str, Optional[str]]:
        full_response = ""
        full_response_message = Message(content=full_response, is_from_human=False)
        # yield f"data: message_id{str(full_response_message.id)} \n\n"

        async for chunk in stream_openai_response(prompt_message.content):
            full_response += chunk
            yield f"data: {chunk} \n\n"

        yield "data: [DONE]\n\n"
        full_response_message.content = full_response
        await mongo_service.engine.save(full_response_message)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
