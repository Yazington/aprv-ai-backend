# aprv-ai-backend/app/api/chat.py
"""
This module handles all chat-related API endpoints for the APR-V AI backend.
It manages prompt creation, response generation, and streaming of AI responses.
"""

import json
from typing import Annotated, AsyncGenerator, List
from openai.types.chat import ChatCompletionMessageParam

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from odmantic import ObjectId

from app.config.logging_config import logger
from app.models.create_prompt_request import CreatePromptRequest
from app.models.message import Message
from app.models.conversation import Conversation
from app.services.conversation_service import ConversationService, get_conversation_service
from app.services.message_service import MessageService, get_message_service
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.openai_service import OpenAIClient, get_openai_client
from app.services.rag_service import RagService, get_rag_service
from app.utils.tiktoken import truncate_all

# Create FastAPI router for chat endpoints
router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/create_prompt")
async def create_prompt(
    create_prompt_request: CreatePromptRequest,
    request: Request,
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    message_service: Annotated[MessageService, Depends(get_message_service)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
):
    """
    Creates a new chat prompt and associates it with a conversation.

    Args:
        create_prompt_request: Contains the prompt text and conversation ID
        request: FastAPI request object containing user information
        mongo_service: MongoDB service for data persistence
        message_service: Service for managing chat messages
        conversation_service: Service for managing conversations

    Returns:
        JSON response containing the created prompt details
    """

    # Get user ID from request
    user_id = request.state.user_id  # Already a string from auth middleware

    try:
        logger.info(f"Creating prompt with conversation_id: {create_prompt_request.conversation_id}")
        
        conversation = None
        conversation_id = create_prompt_request.conversation_id

        if conversation_id is None or not conversation_id.strip():
            try:
                # Create new conversation first
                logger.info("Creating new conversation")
                conversation = Conversation(
                    all_messages_ids=[],
                    user_id=ObjectId(user_id),
                    thumbnail_text=create_prompt_request.prompt[:40]
                )
                await mongo_service.engine.save(conversation)
                conversation_id = str(conversation.id)
                logger.info(f"Created new conversation with ID: {conversation_id}")

                # Create message with new conversation ID
                logger.info(f"Creating message with new conversation ID: {conversation_id}")
                message = await message_service.create_message(
                    create_prompt_request.prompt,
                    conversation_id,
                    user_id
                )
                logger.info(f"Created message with ID: {message.id}")

                # Update conversation with message ID
                conversation.all_messages_ids = [message.id]  # Already an ObjectId
                conversation.thumbnail_text = message.content[:40]
                await mongo_service.engine.save(conversation)
                logger.info("Updated conversation with message ID")
            except Exception as e:
                logger.error(f"Error creating new conversation: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to create conversation")
        else:
            # Handle existing conversation
            logger.info(f"Using existing conversation: {conversation_id}")
            conversation = await conversation_service.get_conversation_by_conversation_id(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Create message with existing conversation ID
            logger.info(f"Creating message with existing conversation ID: {conversation_id}")
            message = await message_service.create_message(
                create_prompt_request.prompt,
                conversation_id,
                user_id
            )

            # Update existing conversation
            conversation.all_messages_ids.append(message.id)  # Already an ObjectId
            conversation.thumbnail_text = message.content[:40]
            await mongo_service.engine.save(conversation)
            logger.info("Updated existing conversation with message")
        
        logger.info(f"Message created successfully with ID: {message.id}")
        logger.info("Successfully created prompt and message")
        return {"prompt": message.content, "message_id": str(message.id), "conversation_id": str(message.conversation_id)}
    except Exception as e:
        logger.error(f"Error in create_prompt: {str(e)}")
        raise


@router.get("/generate/{message_id}")
async def get_prompt_model_response(
    message_id: str,
    request: Request,
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    openai_client: Annotated[OpenAIClient, Depends(get_openai_client)],
    message_service: Annotated[MessageService, Depends(get_message_service)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
):
    """
    Generates an AI response to a given prompt message and streams it back to the client.

    Args:
        message_id: ID of the message to generate response for
        request: FastAPI request object containing user information
        mongo_service: MongoDB service for data persistence
        openai_client: OpenAI service for generating responses
        message_service: Service for managing chat messages
        conversation_service: Service for managing conversations

    Returns:
        StreamingResponse that sends chunks of the AI response as they're generated
    """
    # Get user ID and retrieve the original prompt message
    user_id = request.state.user_id
    try:
        # Log the message ID we're trying to find
        logger.info(f"Attempting to retrieve message with ID: {message_id}")
        
        # Try to convert string ID to ObjectId and log the result
        try:
            object_id = ObjectId(message_id)
            logger.info(f"Successfully converted to ObjectId: {object_id}")
        except Exception as e:
            logger.error(f"Failed to convert message_id to ObjectId: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid message ID format: {message_id}"
            )
        
        # Try to find message by ID
        prompt_message = await mongo_service.engine.find_one(Message, Message.id == object_id)
        
        # Log the result of the database query
        if prompt_message is None:
            logger.error(f"Message not found in database with ID: {message_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Message not found in database: {message_id}"
            )
        
        logger.info(f"Successfully found message: {prompt_message.id}, content: {prompt_message.content[:50]}...")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving message: {str(e)}"
        )

    # Process user prompt and calculate token count
    user_prompt = prompt_message.content
    user_prompt_tokens = message_service.get_tokenized_message_count(user_prompt)

    # Validate conversation exists
    if not prompt_message.conversation_id:
        logger.warning("Failed to retrieve message history: conversation id doesnt exist on prompt")
        return HTTPException(status_code=403, detail="Failed to retrieve message history")

    # Retrieve conversation history and calculate tokens
    history_text = await message_service.retrieve_message_history(str(prompt_message.conversation_id), str(prompt_message.id))
    history_tokens = message_service.get_tokenized_message_count(history_text)

    # Truncate text if necessary to fit token limits
    user_prompt, history_text = truncate_all(user_prompt, user_prompt_tokens, history_tokens, history_text)

    # Get relevant context from RAG
    relevant_context = await rag_service.search_similar(user_prompt, str(prompt_message.conversation_id))
    context_text = "\n".join(relevant_context) if relevant_context else ""

    # Prepare messages for OpenAI API
    messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": user_prompt}]
    if history_text or context_text:
        # Add system message with conversation context
        messages.extend(
            [
                {
                    "role": "system",
                    "content": f"""
You are a brand guideline licensee/licensor assistant. To help the licensee/licensor, you are talking to them inside a conversation.
In the conversation, the licensee/licensor can upload one design file (image), multiple guidelines (pdfs concatenated) and, most importantly,
can review the design against a guideline.

Here is relevant context from the uploaded guidelines:
{context_text}

In order to get context about the conversation, you can use tools!
If the licensee/licensor asks about design files, guidelines and brand licensing, ensure that the necessary files for the task exist.
If the necessary file isnt uploaded, ask the licensee/licensor to do so.

CONVERSATION_ID: {str(prompt_message.conversation_id)}
""",
                }
            ]
        )
        # Insert history as system message
        if history_text:
            messages.insert(1, {"role": "system", "content": history_text})

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        Generator function that streams OpenAI responses back to the client.

        Yields:
            JSON-encoded chunks of the AI response as they're generated
        """
        full_response = ""
        # Create message object to store the final response
        try:
            full_response_message = Message(
                content=full_response,
                is_from_human=False,
                user_id=str(user_id),
                conversation_id=ObjectId(prompt_message.conversation_id),
            )

            # Stream response from OpenAI
            async for chunk in openai_client.stream_openai_llm_response(messages, str(prompt_message.conversation_id)):
                if chunk:
                    full_response += chunk
                    # Yield each chunk as it's received
                    yield f"data: {json.dumps({'content': chunk})}\n\n"

            # Save final response to database
            full_response_message.content = full_response
            message = await mongo_service.engine.save(full_response_message)
            logger.info(f"Saved response message with ID: {message.id}")

            # Update conversation with final response
            await conversation_service.update_conversation(str(prompt_message.conversation_id), message)

            # Signal end of streaming
            yield f"data: {json.dumps({'content': '[DONE-STREAMING-APRV-AI]'})}\n\n"
        except Exception as e:
            logger.error(f"Error in event_generator: {str(e)}")
            # Signal error to client
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            raise

    # Return streaming response with text/event-stream content type
    return StreamingResponse(event_generator(), media_type="text/event-stream")
