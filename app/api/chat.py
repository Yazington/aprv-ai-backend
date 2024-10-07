import json
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.conversation import Conversation
from models.create_prompt_request import CreatePromptRequest
from models.message import Message
from odmantic import ObjectId
from odmantic.query import asc
from services.mongo_service import MongoService, mongo_service
from services.openai_service import OpenAIClient, openai_client

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/create_prompt")
async def create_prompt(request: CreatePromptRequest, mongo_service: MongoService = mongo_service):
    message = Message(conversation_id=request.conversation_id, content=request.prompt, is_from_human=True)
    # Save the message first to get its ID
    message = await mongo_service.engine.save(message)

    if not request.conversation_id:
        # Create a new Conversation and append the message ID
        conversation = Conversation(all_messages_ids=[message.id])
        conversation = await mongo_service.engine.save(conversation)
        message.conversation_id = conversation.id
    else:
        # Find or create the conversation
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(request.conversation_id))
        if not conversation:
            raise ValueError("Conversation not found")

        # Append the message ID to the existing conversation
        conversation.all_messages_ids.append(message.id)
        conversation = await mongo_service.engine.save(conversation)
        message.conversation_id = conversation.id
    message = await mongo_service.engine.save(message)
    return {"prompt": message.content, "message_id": str(message.id), "conversation_id": str(conversation.id)}


@router.get("/generate/{message_id}")
async def get_prompt_model_response(
    message_id: str, mongo_service: MongoService = mongo_service, openai_client: OpenAIClient = openai_client
):
    prompt_message = await mongo_service.engine.find_one(Message, Message.id == ObjectId(message_id))
    if prompt_message is None:
        raise HTTPException(status_code=404, detail=f"Failed to generate response as initial prompt was not found: {message_id}")

    full_prompt = prompt_message.content  # Start with the current message content
    # print(prompt_message.conversation_id)
    if prompt_message.conversation_id:
        # Fetch past messages from the existing conversation
        past_messages = await mongo_service.engine.find(
            Message,
            Message.conversation_id == prompt_message.conversation_id,
            sort=asc(Message.created_at),  # Ensure messages are sorted by time
            # limit=10,  # Limit the number of past messages to avoid overloading the prompt
        )
        # Concatenate past messages to the current prompt
        history = "\n".join(msg.content for msg in past_messages)
        full_prompt = f"{history}\n\n{full_prompt}"  # Add history before the current message
        # print(full_prompt)

    async def event_generator() -> AsyncGenerator[str, Optional[str]]:
        full_response = ""
        full_response_message = Message(content=full_response, is_from_human=False)

        # Await the streaming operation
        async for chunk in openai_client.stream_openai_llm_response(full_prompt):
            if chunk:
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"

        full_response_message.content = full_response
        full_response_message.conversation_id = prompt_message.conversation_id
        message = await mongo_service.engine.save(full_response_message)
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(prompt_message.conversation_id))
        conversation.all_messages_ids.append(message.id)
        await mongo_service.engine.save(conversation)
        yield f"data: {json.dumps({'content': '[DONE-STREAMING-APRV-AI]'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
