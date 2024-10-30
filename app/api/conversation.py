from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from odmantic import ObjectId

from app.models.conversation import Conversation
from app.models.review import Review
from app.models.task import Task, TaskStatus
from app.services.approval_service import ApprovalService, get_approval_service
from app.services.conversation_service import ConversationService, get_conversation_service
from app.services.message_service import MessageService, get_message_service
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.openai_service import OpenAIClient, get_openai_client

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation"],
)


@router.get("")
async def get_conversations_by_user_id(
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)], user_id: str = Query(None)
):
    return await conversation_service.get_conversations_by_user_id(user_id)


@router.get("/conversation")
async def get_conversation_by_conversation_id(
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)], conversation_id: str = Query(None)
):
    return await conversation_service.get_conversation_by_conversation_id(conversation_id)


@router.get("/conversation-messages")
async def get_conversations_messages(
    message_service: Annotated[MessageService, Depends(get_message_service)], conversation_id: str = Query(None)
):
    return await message_service.get_conversations_messages(conversation_id)


@router.get("/process-design")
async def process_design(
    background_tasks: BackgroundTasks,
    doc_and_infer_service: Annotated[ApprovalService, Depends(get_approval_service)],
    conversation_id: str = Query(None),
):

    if not conversation_id:
        return {"error": "conversation_id is required"}

    # Start the background task
    background_tasks.add_task(doc_and_infer_service.background_process_design, conversation_id)

    # Return immediate response with status code 200
    return {"message": "Process started", "conversation_id": conversation_id}


@router.get("/process-status")
async def process_status(mongo_service: Annotated[MongoService, Depends(get_mongo_service)], conversation_id: str = Query(None)):

    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", status_code=400)

    conversation_of_task = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))

    if not conversation_of_task.design_process_task_id:
        return JSONResponse("conversation doesn't have a task", status_code=400)

    task_of_conversation = await mongo_service.engine.find_one(Task, Task.id == conversation_of_task.design_process_task_id)
    if task_of_conversation.status == TaskStatus.IN_PROGRESS.name:
        return JSONResponse(jsonable_encoder({"task_id": str(task_of_conversation.id)}), status_code=202)
    if task_of_conversation.status == TaskStatus.COMPLETE.name:
        return JSONResponse(jsonable_encoder({"task_id": str(task_of_conversation.id)}), status_code=200)


@router.get("/process-result")
async def get_process_result(mongo_service: Annotated[MongoService, Depends(get_mongo_service)], task_id: str = Query(None)):

    if not task_id:
        return JSONResponse("Please provide a task_id", status_code=400)

    task_of_conversation = await mongo_service.engine.find_one(Task, Task.id == ObjectId(task_id))
    if not task_of_conversation.generated_txt_id:
        return JSONResponse(
            jsonable_encoder(
                {"task_id": None, "error": "there was an issue with the given task. It was probably never created or in progress"}
            ),
            status_code=500,
        )
    return await mongo_service.engine.find(Review, Review.conversation_id == task_of_conversation.conversation_id)


@router.get("/conversation-reviews")
async def get_conversation_reviews(mongo_service: Annotated[MongoService, Depends(get_mongo_service)], conversation_id: str = Query(None)):

    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    task = None
    if conversation.design_process_task_id:
        task = await mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)
    if not task or task.status == TaskStatus.COMPLETE:
        return JSONResponse("Task Incomplete", status_code=400)
    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", status_code=400)
    return await mongo_service.engine.find(Review, Review.conversation_id == ObjectId(conversation_id))
