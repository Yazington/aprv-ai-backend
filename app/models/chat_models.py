from pydantic import BaseModel


# Represents a chat message request from the user
# Contains:
# - message: The text content of the user's message
class ChatRequest(BaseModel):
    message: str


# Represents a chat message response to the user
# Contains:
# - message: The text content of the response message
class ChatResponse(BaseModel):
    message: str
