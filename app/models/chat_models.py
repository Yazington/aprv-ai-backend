from odmantic import Model
from pydantic import BaseModel


# Represents a chat message request from the user
# Contains:
# - message: The text content of the user's message
class ChatRequest(Model):
    message: str


# Represents a chat message response to the user
# Contains:
# - message: The text content of the response message
class ChatResponse(Model):
    message: str
