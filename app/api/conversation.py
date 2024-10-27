from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from models.conversation import Conversation
from models.message import Message
from models.review import Review
from models.task import Task, TaskStatus
from odmantic import ObjectId
from services.document_and_inference_service import background_process_design
from services.mongo_service import MongoService, mongo_service
from services.openai_service import OpenAIClient, openai_client

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation"],
)


@router.get("")
async def get_conversations(user_id: str = Query(None), mongo_service: MongoService = mongo_service):
    if not user_id:
        return None
    return await mongo_service.engine.find(Conversation, Conversation.user_id == ObjectId(user_id))


@router.get("/conversation")
async def get_conversations_by_conversation_id(conversation_id: str = Query(None), mongo_service: MongoService = mongo_service):
    if not conversation_id:
        return None
    return await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))


@router.get("/conversation-messages")
async def get_conversations_messages(conversation_id: str = Query(None), mongo_service: MongoService = mongo_service):
    if not conversation_id:
        return None
    return await mongo_service.engine.find(Message, Message.conversation_id == ObjectId(conversation_id))


@router.get("/process-design")
async def process_design(
    background_tasks: BackgroundTasks,
    conversation_id: str = Query(None),
    mongo_service: MongoService = mongo_service,
    openai_client: OpenAIClient = openai_client,
):
    if not conversation_id:
        return {"error": "conversation_id is required"}

    # Start the background task
    background_tasks.add_task(background_process_design, conversation_id, mongo_service, openai_client)

    # Return immediate response with status code 200
    return {"message": "Process started", "conversation_id": conversation_id}


# Polling endpoint to check if task is done


@router.get("/process-status")
async def process_status(conversation_id: str = Query(None), mongo_service: MongoService = mongo_service):
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
async def get_process_result(task_id: str = Query(None), mongo_service: MongoService = mongo_service):
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
async def get_conversation_reviews(conversation_id: str = Query(None), mongo_service: MongoService = mongo_service):
    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    task = None
    if conversation.design_process_task_id:
        task = await mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)
    if not task or task.status == TaskStatus.COMPLETE:
        return JSONResponse("Task Incomplete", status_code=400)
    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", status_code=400)
    return await mongo_service.engine.find(Review, Review.conversation_id == ObjectId(conversation_id))
