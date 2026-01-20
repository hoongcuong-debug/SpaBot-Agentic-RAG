from typing import Literal
from pydantic import BaseModel

class NormalChatRequest(BaseModel):
    chat_id: str
    user_input: str
    
class WebhookChatRequest(BaseModel):
    chat_id: str
    user_input: str
    message_spans: list[dict]    

class ControlRequest(BaseModel):
    chat_id: str
    
class SendMessageRequest(BaseModel):
    chat_id: str
    text: str
    