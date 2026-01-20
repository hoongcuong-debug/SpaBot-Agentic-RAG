from typing import Literal
from typing import TypedDict
from pydantic import BaseModel

class ChatResponse(BaseModel):
    status: Literal["ok", "error"]
    reply: str
    
class ResponseModel(TypedDict):
    content: str | None
    error: str | None   