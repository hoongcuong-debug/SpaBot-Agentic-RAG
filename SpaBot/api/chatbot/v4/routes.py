import traceback
from typing import Literal

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from services.utils import get_or_create_customer
from core.graph.build_graph import create_main_graph
from services.v4.process_chat import (
    handle_delete_me, 
    handle_normal_chat, 
    handle_new_chat,
    send_to_webhook
)

from log.logger_config import setup_logging

logger = setup_logging(__name__)

router = APIRouter()
graph = create_main_graph()

class ChatRequest(BaseModel):
    chat_id: str
    user_input: str

class ChatResponse(BaseModel):
    status: Literal["ok", "error"]
    reply: str

@router.post("/chat/invoke", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse | HTTPException:
    """
    Xử lý yêu cầu chat dạng streaming (v2) có kiểm soát luồng nghiệp vụ.

    Args:
        request (ChatRequest): Dữ liệu gồm `chat_id`, `user_input`.

    Returns:
        HTTPException | ChatResponse: Trả về lỗi hoặc trạng thái xử lý.
    """
    chat_id = request.chat_id
    user_input = request.user_input
    
    try:    
        customer = await get_or_create_customer(chat_id=chat_id)
        
        logger.info(f"Lấy hoặc tạo mới khách: {customer}")
        logger.info(f"Tin nhắn của khách: {user_input}")

        if any(cmd in user_input for cmd in ["/start", "/restart"]):
            messages = await handle_new_chat(chat_id=chat_id)
            
            if messages["error"]:
                return ChatResponse(
                    status="error", 
                    reply="Có lỗi xảy ra khi khởi tạo chat mới"
                )
            return ChatResponse(
                status="ok", 
                reply=messages["content"]
            )
        
        if user_input == "/delete_me":
            messages = await handle_delete_me(chat_id=chat_id)
            
            if messages["error"]:
                return ChatResponse(
                    status="error", 
                    reply="Có lỗi xảy ra khi xóa dữ liệu"
                )
            return ChatResponse(
                status="ok", 
                reply=messages["content"]
            )

        messages = await handle_normal_chat(
            user_input=user_input,
            chat_id=chat_id,
            customer=customer,
            graph=graph
        )
        
        if messages["error"]:
            return ChatResponse(
                status="error", 
                reply="Có lỗi xảy ra khi xử lý chat"
            )
        return ChatResponse(
            status="ok", 
            reply=messages["content"]
        )
            
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Error: {str(e)}"
        )