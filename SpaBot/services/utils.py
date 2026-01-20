import json
import asyncio
from typing import Any
from typing import Optional
from zoneinfo import ZoneInfo
from langgraph.graph import StateGraph
from datetime import datetime, timezone
from core.graph.state import AgentState
from database.connection import supabase_client


from log.logger_config import setup_logging

logger = setup_logging(__name__)


async def check_state(config: dict, graph: StateGraph) -> AgentState:
    state = graph.get_state(config).values
    
    return state if state else None

async def get_uuid(chat_id: str) -> str | None:
    """
    Lấy `uuid` hiện thời theo `chat_id` từ bảng `customer`.

    Args:
        chat_id (str): Định danh cuộc hội thoại/khách hàng.

    Returns:
        str | None: UUID nếu tồn tại, ngược lại None.
    """
    try:
        res = (
            supabase_client.table("customers")
                .select("uuid")
                .eq("chat_id", chat_id)
                .execute()
        )

        return res.data[0]["uuid"] if res.data else None
    except Exception:
        raise
    
async def update_uuid(chat_id: str, new_uuid: str) -> str | None:
    """
    Cập nhật `uuid` mới cho một khách theo `chat_id`.

    Args:
        chat_id (str): Mã khách hàng/cuộc hội thoại.
        new_uuid (str): UUID mới cần cập nhật.

    Returns:
        str | None: UUID sau cập nhật nếu thành công, ngược lại None.
    """
    try:
        res = (
            supabase_client.table("customers")
            .update({"uuid": new_uuid})
            .eq("chat_id", chat_id)
            .execute()
        )

        return res.data[0]["uuid"] if res.data else None
    except Exception:
        raise
    
    
async def get_or_create_customer(chat_id: str) -> Optional[dict]:
    """
    Lấy thông tin khách theo `chat_id`, nếu chưa có sẽ tạo bản ghi mới.

    Args:
        chat_id (str): Định danh cuộc hội thoại/khách hàng.

    Returns:
        Optional[dict]: Bản ghi khách hàng (dict) hoặc None nếu thất bại.
    """
    response = (
        supabase_client.table("customers")
        .upsert(
            {"chat_id": chat_id},
            on_conflict="chat_id"
        )
        .execute()
    )
    
    return response.data[0] if response.data else None

async def delete_customer(chat_id: str) -> bool:
    """
    Xóa khách hàng theo `chat_id`.

    Args:
        chat_id (str): Định danh cuộc hội thoại/khách hàng.

    Returns:
        bool: True nếu xóa thành công, ngược lại False.
    """
    response = (
        supabase_client.table("customers")
        .delete()
        .eq("chat_id", chat_id)
        .execute()
    )
    return bool(response.data)

def now_vietnam_time() -> datetime:
    tz_vn = ZoneInfo("Asia/Ho_Chi_Minh")
    now_utc = datetime.now(timezone.utc)
    now_vn = now_utc.astimezone(tz_vn)
    return now_vn

def cal_duration_ms(
    timestamp_start: datetime,
    timestamp_end: datetime
) -> float:
    delta = timestamp_end - timestamp_start
    seconds = delta.total_seconds()
    duration_ms = seconds * 1000
    
    return duration_ms