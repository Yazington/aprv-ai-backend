import json
from typing import AsyncGenerator, Optional

import tiktoken
from config.logging_config import logger
from exceptions.bad_conversation_files import DesignOrGuidelineNotFoundError
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from models.conversation import Conversation
from models.create_prompt_request import CreatePromptRequest
from models.message import Message
from odmantic import ObjectId
from odmantic.query import asc
from services.mongo_service import MongoService, mongo_service
from services.openai_service import OpenAIClient, openai_client
from services.rag_service import get_rag_results

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("/create_prompt")
async def create_prompt(create_prompt_request: CreatePromptRequest, request: Request, mongo_service: MongoService = mongo_service):
    message = Message(
        id=ObjectId(),
        conversation_id=ObjectId(create_prompt_request.conversation_id),
        content=create_prompt_request.prompt,
        is_from_human=True,
        user_id=ObjectId(request.state.user_id),
    )
    # Save the message first to get its ID
    message = await mongo_service.engine.save(message)

    if not create_prompt_request.conversation_id:
        # Create a new Conversation and append the message ID
        conversation = Conversation(
            id=ObjectId(), all_messages_ids=[message.id], user_id=ObjectId(request.state.user_id), thumbnail_text=message.content[0:40]
        )
        conversation = await mongo_service.engine.save(conversation)
        message.conversation_id = conversation.id
    else:
        # Find or create the conversation
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(create_prompt_request.conversation_id))
        if not conversation:
            raise ValueError("Conversation not found")
        conversation.thumbnail_text = message.content[0:40]
        # Append the message ID to the existing conversation
        conversation.all_messages_ids.append(message.id)
        conversation = await mongo_service.engine.save(conversation)
        message.conversation_id = conversation.id
    message = await mongo_service.engine.save(message)
    return {"prompt": message.content, "message_id": str(message.id), "conversation_id": str(conversation.id)}


# @router.get("/generate/{message_id}")
# async def get_prompt_model_response(
#     message_id: str,
#     user_id: str = Query(...),  # User ID as a query parameter
#     mongo_service: MongoService = mongo_service,
#     openai_client: OpenAIClient = openai_client,
# ):
#     # get user prompt and concatenate past messages to the current prompt
#     prompt_message = await mongo_service.engine.find_one(Message, Message.id == ObjectId(message_id))
#     if prompt_message is None:
#         raise HTTPException(status_code=404, detail=f"Failed to generate response as initial prompt was not found: {message_id}")

#     full_prompt = prompt_message.content  # Start with the current message content

#     rag_results = get_rag_results(full_prompt)

#     if prompt_message.conversation_id:
#         past_messages = await mongo_service.engine.find(
#             Message,
#             Message.conversation_id == prompt_message.conversation_id,
#             sort=asc(Message.created_at),  # Ensure messages are sorted by time
#             # limit=10,  # Limit the number of past messages to avoid overloading the prompt
#         )
#         history = "\n".join(msg.content for msg in past_messages)
#         full_prompt = f"{history}\n\n{full_prompt}"  # Add history before the current message

#     # create LLM response from user prompt and all previous messages
#     async def event_generator() -> AsyncGenerator[str, Optional[str]]:
#         full_response = ""
#         full_response_message = Message(id=ObjectId(), content=full_response, is_from_human=False, user_id=ObjectId(user_id))

#         # Await the streaming operation
#         async for chunk in openai_client.stream_openai_llm_response(full_prompt): # TODO: reread documentation to use not all content in one shot but by role adding truncation strategy
#             if chunk:
#                 full_response += chunk
#                 yield f"data: {json.dumps({'content': chunk})}\n\n"

#         full_response_message.content = full_response
#         full_response_message.conversation_id = prompt_message.conversation_id
#         message = await mongo_service.engine.save(full_response_message)
#         conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(prompt_message.conversation_id))
#         conversation.all_messages_ids.append(message.id)
#         await mongo_service.engine.save(conversation)
#         yield f"data: {json.dumps({'content': '[DONE-STREAMING-APRV-AI]'})}\n\n"

#     return StreamingResponse(event_generator(), media_type="text/event-stream")

MAX_TOKENS = 128000  # Max tokens for the model's context window
RESPONSE_TOKENS = 16384  # Tokens reserved for the response
PROMPT_TOKENS = MAX_TOKENS - RESPONSE_TOKENS  # Tokens available for the prompt


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def truncate_text(text: str, max_tokens: int, model: str = "gpt-3.5-turbo") -> str:
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    else:
        truncated_tokens = tokens[-max_tokens:]  # Keep the last tokens
        return encoding.decode(truncated_tokens)


@router.get("/generate/{message_id}")
async def get_prompt_model_response(
    message_id: str,
    user_id: str = Query(...),  # User ID as a query parameter
    mongo_service: MongoService = mongo_service,
    openai_client: OpenAIClient = openai_client,
):
    # Retrieve the user prompt
    prompt_message = await mongo_service.engine.find_one(Message, Message.id == ObjectId(message_id))
    if prompt_message is None:
        raise HTTPException(status_code=404, detail=f"Failed to generate response as initial prompt was not found: {message_id}")

    user_prompt = prompt_message.content
    user_prompt_tokens = count_tokens(user_prompt)

    try:
        rag_results = await get_rag_results(
            user_prompt, prompt_message.conversation_id, mongo_service
        )  # TODO: change this to be tool call instead
    except Exception as e:
        logger.error(e)
        if type(e) is DesignOrGuidelineNotFoundError:
            return JSONResponse("Design or Guideline not found", 404)
        return JSONResponse("Failed to get rag results", 500)

    # print("results: ", rag_results)
    rag_results_text = rag_results
    rag_results_tokens = count_tokens(rag_results_text)

    # Retrieve and tokenize message history
    history_tokens, history_text = await retrieve_and_tokenize_message_history(mongo_service, prompt_message)

    # Calculate total tokens and apply truncation if necessary
    user_prompt, rag_results_text, history_text = truncate_all(
        user_prompt, user_prompt_tokens, rag_results_text, rag_results_tokens, history_tokens, history_text
    )

    # Construct the final prompt
    full_prompt = ""
    if history_text:
        full_prompt += f"{history_text}\n\n"
    if rag_results_text:
        full_prompt += f"{rag_results_text}\n\n"
    full_prompt += user_prompt  # User prompt at the end
    print(full_prompt, sep="")

    # Generate the LLM response
    async def event_generator() -> AsyncGenerator[str, Optional[str]]:
        full_response = ""
        full_response_message = Message(id=ObjectId(), content=full_response, is_from_human=False, user_id=ObjectId(user_id))

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


def truncate_all(user_prompt, user_prompt_tokens, rag_results_text, rag_results_tokens, history_tokens, history_text):
    total_prompt_tokens = user_prompt_tokens + rag_results_tokens + history_tokens
    tokens_needed = total_prompt_tokens - PROMPT_TOKENS

    if tokens_needed > 0:
        # Truncate history first
        if history_tokens > 0:
            tokens_to_remove = min(tokens_needed, history_tokens)
            history_text = truncate_text(history_text, history_tokens - tokens_to_remove)
            history_tokens = count_tokens(history_text)
            tokens_needed = total_prompt_tokens - (user_prompt_tokens + rag_results_tokens + history_tokens)
        # Truncate RAG results next
        if tokens_needed > 0 and rag_results_tokens > 0:
            tokens_to_remove = min(tokens_needed, rag_results_tokens)
            rag_results_text = truncate_text(rag_results_text, rag_results_tokens - tokens_to_remove)
            rag_results_tokens = count_tokens(rag_results_text)
            tokens_needed = total_prompt_tokens - (user_prompt_tokens + rag_results_tokens + history_tokens)
        # Truncate user prompt as a last resort
        if tokens_needed > 0:
            tokens_to_remove = min(tokens_needed, user_prompt_tokens - 1)  # Keep at least 1 token
            user_prompt = truncate_text(user_prompt, user_prompt_tokens - tokens_to_remove)
            user_prompt_tokens = count_tokens(user_prompt)
    return user_prompt, rag_results_text, history_text


async def retrieve_and_tokenize_message_history(mongo_service, prompt_message):
    history_tokens = 0
    history_text = ""
    if prompt_message.conversation_id:
        past_messages = await mongo_service.engine.find(
            Message,
            Message.conversation_id == prompt_message.conversation_id,
            sort=asc(Message.created_at),
        )
        past_messages = [msg for msg in past_messages if msg.id != prompt_message.id]
        history_text = "\n".join(msg.content for msg in past_messages)
        history_tokens = count_tokens(history_text)
    return history_tokens, history_text
