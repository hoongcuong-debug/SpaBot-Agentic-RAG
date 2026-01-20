import pickle
import base64
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from supabase import AsyncClient, Client
from database.connection import supabase_client

from database.connection import get_async_supabase_client

VALID_EVENT_TYPES = {
    "new_customer", 
    "returning_customer", 
    "bot_response_success",
    "bot_response_failure",
}

async def _create_async_supabase_client() -> AsyncClient:
    return await get_async_supabase_client()

def _get_time_vn() -> str:
    tz_vn = ZoneInfo("Asia/Ho_Chi_Minh")
    now_vn = datetime.now(tz_vn)

    now_vn = now_vn.replace(microsecond=0)
    now_vn = now_vn.strftime("%Y-%m-%d %H:%M:%S+07")
    
    return now_vn

def _to_vn(dt_str_or_dt) -> str:
    if isinstance(dt_str_or_dt, str):
        # parse chuỗi ISO (UTC)
        dt = datetime.fromisoformat(dt_str_or_dt)
    else:
        dt = dt_str_or_dt
    # nếu dt không có tzinfo, giả sử là UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # chuyển sang giờ VN
    dt_vn = dt.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    dt_vn = dt_vn.strftime("%Y-%m-%d %H:%M:%S+07")
    
    return dt_vn

def _encode_state(state: dict) -> str:
    dumps = pickle.dumps(state)
    encoded = base64.b64encode(dumps).decode("utf-8")
    
    return encoded

def _decode_state(data: str) -> dict:
    if not data:
        return {}
    
    dumps = base64.b64decode(data.encode("utf-8"))
    state = pickle.loads(dumps)
    
    return state

class AsyncCustomerRepo:
    def __init__(self):
        self.supabase_client = supabase_client
        
    async def get_uuid(self, chat_id: str) -> str | None:
        response = (
            self.supabase_client.table("customers")
            .select("uuid")
            .eq("chat_id", chat_id).execute()
        )

        return response.data[0]["uuid"] if response.data else None
    
    async def get_or_create_customer(self, chat_id: str) -> dict | None:
        response = (
            self.supabase_client.table("customers")
            .upsert(
                {"chat_id": chat_id},
                on_conflict="chat_id"
            )
            .execute()
        )

        return response.data[0] if response.data else None

    async def delete_customer(self, customer_id: int) -> bool:
        response = (
            self.supabase_client.table("customers")
            .delete()
            .eq("id", customer_id)
            .execute()
        )
        return bool(response.data)
    
    async def update_uuid(self, chat_id: str, new_uuid: str) -> str | None:
        response = (
            self.supabase_client.table("customers")
            .update({"uuid": new_uuid})
            .eq("chat_id", chat_id)
            .execute()
        )

        return response.data[0]["uuid"] if response.data else None
    
    async def find_customer(self, chat_id: str) -> dict | None:
        response = (
            self.supabase_client.table("customers")
            .select("*, sessions(*)")
            .eq("chat_id", chat_id)
            .eq("sessions.status", "active")
            .execute()
        )

        if not response.data:
            return None
        
        if response.data[0]["sessions"]:
            session = response.data[0]["sessions"][0]
            session["started_at"] = _to_vn(session["started_at"]) 
            session["last_active_at"] = _to_vn(session["last_active_at"]) 
            session["state_base64"] = _decode_state(session["state_base64"])
        
        return response.data[0]
    
    async def create_customer(self, chat_id: str) -> dict | None:
        response = (
            self.supabase_client.table("customers")
            .insert({"chat_id": chat_id})
            .execute()
        )

        return response.data[0] if response.data else None
    
    async def update_customer(self, chat_id: str, payload: dict) -> dict | None:
        response = (
            self.supabase_client.table("customers")
            .update(payload)
            .eq("chat_id", chat_id)
            .execute()
        )

        return response.data[0] if response.data else None        
class AsyncSessionRepo:
    def __init__(self):
        self.supabase_client = supabase_client
        
    async def create_session(self, customer_id: int, thread_id: str) -> dict | None:
        response = (
            self.supabase_client.table("sessions")
            .insert(
                {
                    "customer_id": customer_id,
                    "thread_id": thread_id,
                    "started_at": _get_time_vn(),
                    "last_active_at": _get_time_vn(),
                    "status": "active"
                }
            )
            .execute()
        )

        return response.data[0] if response.data else None
    
    async def update_end_session(self, session_id: int) -> dict | None:
        response = (
            self.supabase_client.table("sessions")
            .update(
                {
                    "status": "inactive",
                    "ended_at": _get_time_vn()
                }
            )
            .eq("id", session_id)
            .execute()
        )

        return response.data[0] if response.data else None
    
    async def update_last_active_session(self, session_id: int) -> dict | None:
        response = (
            self.supabase_client.table("sessions")
            .update(
                {
                    "last_active_at": _get_time_vn()
                }
            )
            .eq("id", session_id)
            .execute()
        )

        return response.data[0] if response.data else None
    
    async def update_state_session(self, state: dict, session_id: int) -> dict | None:
        response = (
            self.supabase_client.table("sessions")
            .update(
                {
                    "state_base64": _encode_state(state=state)
                }
            )
            .eq("id", session_id)
            .execute()
        )

        return response.data[0] if response.data else None
    
    async def get_state_session(self, session_id: int) -> dict | None:
        response = (
            self.supabase_client.table("sessions")
            .select("state_base64")
            .eq("id", session_id)
            .execute()
        )
        
        data = response.data[0]["state_base64"]
        if not data:
            return None

        return _decode_state(data=data)
    
class AsyncEventRepo:
    def __init__(self):
        self.supabase_client = supabase_client
        
    async def create_event(self, customer_id: int, session_id: int, event_type: str) -> str | None:
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {event_type}. Must be one of {VALID_EVENT_TYPES}")

        response = (
            self.supabase_client.table("events")
            .insert(
                {
                    "customer_id": customer_id,
                    "session_id": session_id,
                    "event_type": event_type,
                    "timestamp": _get_time_vn()
                }
            )
            .execute()
        )
        
        return response.data[0] if response.data else None
    
class AsyncMessageSpanRepo:
    def __init__(self):
        self.supabase_client = supabase_client
        
    async def create_message_span(
        self, 
        session_id: int, 
        sender: str, 
        content: str
    ) -> dict | None:
        response = (
            self.supabase_client.table("messages")
            .insert(
                {
                    "session_id": session_id,
                    "sender": sender,
                    "content": content,
                    "timestamp": _get_time_vn()
                }
            )
            .execute()
        )

        return response.data[0] if response.data else None
    
    async def create_message_span_bulk(
        self,
        message_spans: list[dict]
    ) -> list[dict] | None:
        response = (
            self.supabase_client.table("message_spans")
            .insert(message_spans)
            .execute()
        )

        return response.data if response.data else None
    
    async def get_latest_event_and_bot_span(self, customer_id: int) -> dict:
        # 1. Lấy bản ghi event mới nhất cho customer_id
        r1 = (
            self.supabase_client
            .table("events")
            .select("customer_id, session_id")
            .eq("customer_id", customer_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        if not r1.data:
            return None  # không có event cho customer này
        event = r1.data[0]
        session_id = event["session_id"]

        # 2. Lấy bot span mới nhất cho session đó và direction = 'outbound'
        r2 = (
            self.supabase_client
            .table("message_spans")
            .select("id, timestamp_end")
            .eq("session_id", session_id)
            .eq("direction", "outbound")
            .order("timestamp_end", desc=True)
            .limit(1)
            .execute()
        )
        span = r2.data[0] if r2.data else None

        # 3. Chuẩn bị kết quả
        result = {
            "customer_id": customer_id,
            "event_session_id": session_id,
            "span_id": None,
            "span_end_ts": None
        }

        if span:
            result["span_id"] = span["id"]
            result["span_end_ts"] = span["timestamp_end"]

        return result