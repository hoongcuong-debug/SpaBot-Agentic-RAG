import os
import uuid
import aiohttp
import traceback
from typing import Any, TypedDict
from langgraph.graph import StateGraph

from core.graph.state import init_state
from services.utils import delete_customer, get_uuid, update_uuid

from log.logger_config import setup_logging
from dotenv import load_dotenv

load_dotenv()
logger = setup_logging(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

class ResponseModel(TypedDict):
    content: str | None
    error: str | None   

async def _get_or_create_uuid(chat_id: str) -> str:
    """
    Lấy `uuid` hiện tại của khách theo `chat_id`, nếu chưa tồn tại thì tạo mới và lưu.

    Args:
        chat_id (str): Định danh cuộc hội thoại/khách hàng.

    Returns:
        str: UUID hiện có hoặc mới tạo.
    """
    current_uuid = await get_uuid(chat_id=chat_id)
    
    if not current_uuid:
        new_uuid = str(uuid.uuid4())
        await update_uuid(chat_id=chat_id, new_uuid=new_uuid)
        return new_uuid

    return current_uuid

async def handle_normal_chat(
    user_input: str,
    chat_id: str,
    customer: dict,
    graph: StateGraph
) -> ResponseModel:
    """
    Xử lý luồng chat thông thường: nạp state, cập nhật thông tin khách, gọi graph và trả về `events`.

    Args:
        user_input (str): Nội dung người dùng nhập.
        chat_id (str): Mã cuộc hội thoại.
        customer (dict): Thông tin khách hàng lấy từ DB.
        graph (StateGraph): Đồ thị tác vụ chính để suy luận.

    Returns:
        tuple[Any, str] | tuple[None, None]: Cặp (events, thread_id) hoặc (None, None) nếu lỗi.
    """
    try:
        thread_id = await _get_or_create_uuid(chat_id=chat_id)

        if not thread_id:
            logger.error("Lỗi ở cấp DB -> không lấy được uuid")
            return ResponseModel(
                content=None, 
                error="Lỗi không thể lấy uuid"
            )

        logger.info(f"Lấy được uuid của khách: {chat_id} là {thread_id}")

        config = {"configurable": {"thread_id": thread_id}}

        state = (graph.get_state(config).values 
                 if graph.get_state(config).values 
                 else init_state())

        state["user_input"] = user_input
        state["chat_id"] = chat_id
        
        state["customer_id"] = customer["id"]
        state["name"] = customer["name"]
        state["phone"] = customer["phone"]
        state["email"] = customer["email"]

        result = graph.invoke(state, config=config)
        data = result["messages"][-1].content

        return ResponseModel(
            content=data, 
            error=None
        )
    
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        return ResponseModel(
            content=None,
            error=str(e)
        )
        
async def handle_new_chat(
    chat_id: str
) -> ResponseModel:
    """
    Khởi tạo phiên chat mới (reset): cập nhật `uuid` mới trong DB và phát thông báo SSE.

    Args:
        chat_id (str): Định danh cuộc hội thoại.

    Yields:
        str: Chuỗi SSE dạng `data: {...}` và token `[DONE]` khi hoàn tất.
    """
    try:
        new_uuid = str(uuid.uuid4())
        updated_uuid = await update_uuid(
            chat_id=chat_id,
            new_uuid=new_uuid
        )

        if not updated_uuid:
            logger.error("Lỗi ở cấp DB -> Không thể cập nhật uuid")
            return ResponseModel(
                content=None,
                error="Lỗi không thể cập nhật uuid"
            )
            
        else:
            logger.info(f"Cập nhật uuid của khách: {chat_id} là {updated_uuid}")

            response = (
                "Dạ em chào mừng khách đến với AnVie Spa 🌸 – "
                "nơi khách có thể dễ dàng đặt lịch và tìm hiểu các "
                "dịch vụ chăm sóc sắc đẹp, thư giãn trong không gian "
                "sang trọng, dịu nhẹ. Em rất hân hạnh được đồng hành và "
                "hỗ trợ khách để có trải nghiệm thư giãn trọn vẹn ạ."
            )

            return ResponseModel(
                content=response,
                error=None
            )
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        return ResponseModel(
            content=None,
            error=str(e)
        )
        
async def handle_delete_me(
    chat_id: str
) -> ResponseModel:
    """
    Dev only (delete customer with chat id): Xóa khách hàng khỏi DB.

    Args:
        chat_id (str): Định danh cuộc hội thoại.

    Yields:
        str: Chuỗi SSE dạng `data: {...}` và token `[DONE]` khi hoàn tất.
    """
    try:
        deleted_customer = await delete_customer(chat_id=chat_id)

        if not deleted_customer:
            logger.error(f"Lỗi ở cấp DB -> Không xóa khách với chat_id: {chat_id}")
            return ResponseModel(
                content=None,
                error="Lỗi không thể xóa khách hàng"
            )
            
        else:
            logger.info(f"Xóa thành công khách với chat_id: {chat_id}")

            response = (
                "Dev only: Đã xóa thành công khách hàng khỏi hệ thống."
            )

            return ResponseModel(
                content=response,
                error=None
            )
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        return ResponseModel(
            content=None,
            error=str(e)
        )
        
async def send_to_webhook(data: dict, chat_id: str):
    """
    Gửi response data đến webhook URL
    Args:
        data (dict): Dữ liệu response cần gửi
        chat_id (str): ID của chat
    """
    try:
        payload = {
            "chat_id": chat_id,
            "response": data,
            "timestamp": traceback.format_exc()  # Có thể thay bằng datetime.now().isoformat()
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                WEBHOOK_URL, 
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    logger.info(f"Đã gửi thành công response đến webhook cho chat_id: {chat_id}")
                else:
                    logger.error(f"Lỗi khi gửi đến webhook. Status: {response.status}, chat_id: {chat_id}")
                    
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise