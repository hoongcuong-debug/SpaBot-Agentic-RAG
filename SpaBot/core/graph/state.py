from langgraph.graph.message import add_messages

from typing import Annotated, Any, TypedDict, Optional
from langgraph.prebuilt.chat_agent_executor import AgentState as Origin_AgentState


def _remain_dict(old: dict, new: dict | None):
    return new if new is not None else old

def _remain_value(old: Optional[Any], new: Optional[Any]) -> Optional[Any]:
    return new if new is not None else old

class Services(TypedDict):
    service_id: int
    service_type: str
    service_name: str
    duration_minutes: int
    price: int
    discount_value: float | None
    price_after_discount: float | None

class Customer(TypedDict):
    customer_id: int
    name: str
    phone: str
    email: str

class Staff(TypedDict):
    staff_id: int
    name: str
    
class Room(TypedDict):
    room_id: int
    room_name: str

class BookInfo(TypedDict):
    appointment_id: int
    booking_date: str
    start_time: str
    end_time: str
    total_time: int
    note: str
    
    status: str
    total_price: int
    total_discount: float
    price_after_discount: int
    create_date: str

    services: dict[int, Services]
    customer: Customer
    staff: Staff
    room: Room

class PreBookings(TypedDict):
    booking_date: str
    start_time: str
    end_time: str
    total_time: int
    total_price: int
    note: str
    
    customer: Customer
    staff: Staff
    room: Room
    
    services: dict[int, Services]
    

class AgentState(Origin_AgentState):
    messages: Annotated[list, add_messages]
    user_input: Annotated[str, _remain_value]
    chat_id: Annotated[str, _remain_value]
    next: Annotated[str, _remain_value]
    current_date: Annotated[str, _remain_value]
    
    customer_id: Annotated[Optional[int], _remain_value]
    name: Annotated[Optional[str], _remain_value]
    phone: Annotated[Optional[str], _remain_value]
    email: Annotated[Optional[str], _remain_value]
    new_customer: Annotated[Optional[bool], _remain_value]
    session_id: Annotated[int | None, _remain_value]
    
    seen_services: Annotated[Optional[dict[int, Services]], _remain_dict]
    services: Annotated[Optional[dict[int, Services]], _remain_dict]
    staff_id: Annotated[Optional[int], _remain_value]
    staff_name: Annotated[Optional[str], _remain_value]
    room_id: Annotated[Optional[int], _remain_value]
    room_name: Annotated[Optional[str], _remain_value]
    
    booking_date: Annotated[Optional[str], _remain_value]
    start_time: Annotated[Optional[str], _remain_value]
    end_time: Annotated[Optional[str], _remain_value]
    total_time: Annotated[Optional[int], _remain_value]
    
    total_price: Annotated[Optional[int], _remain_value]
    note: Annotated[Optional[str], _remain_value]
    
    total_discount: Annotated[Optional[float], _remain_value]
    price_after_discount: Annotated[Optional[int], _remain_value]
    explain: Annotated[Optional[str], _remain_value]
    
    pre_bookings: Annotated[Optional[dict[int, PreBookings]], _remain_dict]
    book_info: Annotated[Optional[dict[int, BookInfo]], _remain_dict]
    
    
def init_state() -> AgentState:
    return AgentState(
        messages=[],               
        user_input="",
        chat_id="",
        next="",
        current_date=None,
        
        customer_id=None,
        name=None,
        phone=None,
        email=None,
        new_customer=None,
        session_id=None,
        
        seen_services=None,
        services=None,
        staff_id=None,
        staff_name=None,
        room_id=None,
        room_name=None,
        
        booking_date=None,
        start_time=None,
        end_time=None,
        total_time=None,
        
        total_price=None,
        note=None,
        
        total_discount=None,
        price_after_discount=None,
        explain=None,
        
        pre_bookings=None,
        book_info=None
    )