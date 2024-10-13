from typing import Dict

from fastapi import APIRouter, BackgroundTasks, Query, status
from models.conversation import Conversation
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation"],
)


@router.get("")
async def get_conversations(user_id: str = Query(...), mongo_service: MongoService = mongo_service):
    if not user_id:
        return None
    return await mongo_service.engine.find(Conversation, Conversation.user_id == ObjectId(user_id))
    # print(conversations)
    # return None


# Dictionary to store task status (in-memory for simplicity, you could replace this with MongoDB)
task_status: Dict[str, str] = {}


# Simulated background task function
async def background_process_design(conversation_id: str, mongo_service: MongoService):
    # Mark task as "in progress"
    task_status[conversation_id] = "in progress"

    # Simulate a long-running task (e.g., some processing)
    # await mongo_service.process_conversation_design(conversation_id)
    pass
    # Mark task as "done" when completed
    task_status[conversation_id] = "done"


@router.get("/process-design")
async def process_design(background_tasks: BackgroundTasks, conversation_id: str = Query(...), mongo_service: MongoService = mongo_service):
    if not conversation_id:
        return {"error": "conversation_id is required"}

    # Start the background task
    background_tasks.add_task(background_process_design, conversation_id, mongo_service)

    # Return immediate response with status code 200
    return {"message": "Process started", "conversation_id": conversation_id}


# Polling endpoint to check if task is done
@router.get("/process-status")
async def process_status(conversation_id: str = Query(...), mongo_service: MongoService = mongo_service):
    # Check if the task exists in our status tracker
    if conversation_id not in task_status:
        return {"error": "No task found for the given conversation_id"}

    status = task_status[conversation_id]

    if status == "done":
        # Fetch the result if task is done (e.g., retrieve data from MongoDB or another source)
        result = await mongo_service.get_design_result(conversation_id)
        return {"status": "done", "conversation_id": conversation_id, "result": result}

    return {"status": status, "conversation_id": conversation_id}
