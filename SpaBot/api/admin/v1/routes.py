import os
import traceback
from dotenv import load_dotenv
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Header

from log.logger_config import setup_logging
from database.connection import supabase_client
from repository.async_repo import AsyncCustomerRepo
from schemas.resquest import ControlRequest, SendMessageRequest

load_dotenv()
logger = setup_logging(__name__)
async_customer_repo = AsyncCustomerRepo()

SECRET_ADMIN_KEY = os.getenv("SECRET_ADMIN_KEY")

async def verify_admin_key(api_key: str = Header(..., description="Admin API Key")):
    if api_key != SECRET_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin API Key")
    return True

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_key)]
)

@router.post("/conversations/takeover", status_code=200)
async def takeover_conversation(request: ControlRequest):
    """
    Admin tiếp quản, đồng thời ghi lại thời gian tiếp quản.
    """
    try:
        # [THAY ĐỔI] Thêm mode_switched_at với thời gian UTC hiện tại
        update_payload = {
            "control_mode": "ADMIN",
            "mode_switched_at": datetime.now(timezone.utc).isoformat()
        }
        
        response = async_customer_repo.update_customer(
            chat_id=request.chat_id,
            payload=update_payload
        )
        
        if not response:
            raise HTTPException(
                status_code=404, 
                detail="Chat ID not found"
            )

        logger.info(f"Admin đã tiếp quản chat_id: {request.chat_id}")
        return {
            "status": "success", 
            "message": f"Conversation {request.chat_id} is now under ADMIN control."
        }
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Lỗi khi tiếp quản hội thoại: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/conversations/release", status_code=200)
async def release_conversation(request: ControlRequest):
    """
    Admin bàn giao lại, đồng thời xóa dấu thời gian.
    """
    try:
        # Set mode_switched_at về NULL khi bàn giao lại
        update_payload = {
            "control_mode": "BOT",
            "mode_switched_at": None
        }
        response = async_customer_repo.update_customer(
            chat_id=request.chat_id,
            payload=update_payload
        )
        
        if not response:
            raise HTTPException(
                status_code=404, 
                detail="Chat ID not found"
            )

        logger.info(f"Admin đã bàn giao lại chat_id: {request.chat_id} cho Bot.")
        return {
            "status": "success", 
            "message": f"Conversation {request.chat_id} has been released back to BOT control."
        }
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Lỗi khi bàn giao lại hội thoại: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        raise HTTPException(status_code=500, detail=str(e))
    
# @router.post("/conversations/send_message", status_code=200)
# async def send_message(request: SendMessageRequest):
#     """
#     "Smart Dispatcher": Tự động nhận diện nền tảng từ chat_id và gửi tin nhắn.
#     """
#     chat_id = request.chat_id
#     text = request.text
    
#     logger.info(f"Smart Dispatcher: Gửi tin nhắn tới {chat_id}")
    
#     try:
#         # Quy tắc 1: Nếu chat_id bắt đầu bằng 'web-', đó là WebSocket
#         platform = await handle_send_message_platforms(
#             chat_id=chat_id, 
#             text=text
#         )
        
#         logger.success(f"Đã gửi tin nhắn thành công qua nền tảng: {platform}")
#         return {"status": "success", "message": f"Tin nhắn đã được gửi qua {platform}."}

#     except Exception as e:
#         error_details = traceback.format_exc()
#         logger.error(f"Exception: {e}")
#         logger.error(f"Chi tiết lỗi: \n{error_details}")
        
#         # Ném lại lỗi để FastAPI có thể xử lý
#         if isinstance(e, HTTPException):
#             raise e
#         raise HTTPException(status_code=500, detail=str(e))