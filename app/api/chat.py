from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat_models import ChatRequest
from app.services.openai_service import stream_openai_response

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/stream")
async def chat_stream(chat_request: ChatRequest):
    """
    Endpoint to stream chat responses from OpenAI.
    """

    async def event_generator():
        async for chunk in stream_openai_response(chat_request.message):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/plain")
