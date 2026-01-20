import os
import json
import random
import asyncio
from typing import Any
from decimal import Decimal
from dotenv import load_dotenv
from datetime import date, time, datetime

from langgraph.graph import StateGraph
from langchain_core.messages import ToolMessage
from langchain_core.messages import AIMessage, HumanMessage

from core.graph.state import AgentState, Room
from repository.sync_repo import CustomerRepo
from database.connection import supabase_client
from core.graph.state import AgentState, BookInfo, Customer, Services, Staff

from log.logger_config import setup_logging

load_dotenv()
logger = setup_logging(__name__)
customer_repo = CustomerRepo(supabase_client=supabase_client)

OPEN_TIME_STR = os.getenv("OPEN_TIME_STR", "08:00:00")
CLOSE_TIME_STR = os.getenv("CLOSE_TIME_STR", "21:00:00")

NEW_CUSTOMER_DISCOUNT = os.getenv("NEW_CUSTOMER_DISCOUNT")
TWO_SERVICES_DISCOUNT = os.getenv("TWO_SERVICES_DISCOUNT")
THREE_SERVICES_DISCOUNT = os.getenv("THREE_SERVICES_DISCOUNT")
FOUR_PLUS_SERVICES_DISCOUNT = os.getenv("FOUR_PLUS_SERVICES_DISCOUNT")

def build_update(
    content: str,
    tool_call_id: Any,
    **kwargs
) -> dict:
    """
    Tạo payload `update` chuẩn cho LangGraph `Command` với một `ToolMessage`.

    Args:
        content (str): Nội dung phản hồi hiển thị cho người dùng.
        tool_call_id (Any): ID gọi tool để liên kết message với lần gọi công cụ.
        **kwargs: Các trường trạng thái bổ sung để cập nhật vào state.

    Returns:
        dict: Payload cập nhật cho `Command(update=...)`.
    """
    return {
        "messages": [
            ToolMessage
            (
                content=content,
                tool_call_id=tool_call_id
            )
        ],
        **kwargs
    }
        
async def test_bot(
    graph: StateGraph,
    state: AgentState,
    config: dict,
    mode: str = "updates"
):
    async for data in graph.astream(state, subgraphs=True, config=config, mode=mode):
        for key, value in data[1].items():
            if "messages" in value and value["messages"]:
                print(value["messages"][-1].pretty_print())
                
def pack_state_messgaes(messages: list) -> list[dict]:
    process_mess = []
    for mess in messages:
        process_mess.append({
            "type": mess.type,
            "content": mess.content
        })
    
    return process_mess

def unpack_state_messages(messages: list) -> list[dict]:
    unpack_messages = []
    for mess in messages:
        if mess["type"] == "human":
            unpack_messages.append(HumanMessage(content=mess["content"]))
        else:
            unpack_messages.append(AIMessage(content=mess["content"]))
            
    return unpack_messages

async def stream_messages(events: Any, thread_id: str):
    """
    Chuyển đổi luồng sự kiện từ graph thành SSE để client nhận theo thời gian thực.

    Args:
        events (Any): Async iterator sự kiện từ graph.astream.
        thread_id (str): Định danh luồng hội thoại.

    Yields:
        str: Chuỗi SSE dạng `data: {...}\n\n`.
    """
    last_printed = None
    closed = False

    try:
        async for data in events:
            for key, value in data.items():
                    messages = value.get("messages", [])
                    if not messages:
                        continue

                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage):
                        content = last_msg.content.strip()
                        if content and content != last_printed:
                            last_printed = content
                            msg = {"content": content}
                            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.01)  # slight delay for smoother streaming
    except GeneratorExit:
        closed = True
        raise
    except Exception as e:
        error_dict = {"error": str(e), "thread_id": thread_id}
        yield f"data: {json.dumps(error_dict, ensure_ascii=False)}\n\n"
    finally:
        if not closed:
            yield "data: [DONE]\n\n"

async def check_state(config: dict, graph: StateGraph) -> AgentState:
    state = graph.get_state(config).values
    
    return state if state else None

async def update_state_customer(
    chat_id: str,
    graph: StateGraph
) -> dict | None:
    try:
        config = {"configurable": {"thread_id": chat_id}}

        get_state = graph.get_state(config).values
        get_state["messages"] = pack_state_messgaes(
            messages=get_state["messages"]
        )

        update_customer = customer_repo.update_customer_by_chat_id(
            update_payload={"state": get_state},
            chat_id=chat_id
        )
        
        return update_customer if update_customer else None
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

def time_to_str(t):
    if t is None:
        return None
    if isinstance(t, datetime):
        return t.time().strftime("%H:%M:%S")
    if isinstance(t, time):
        return t.strftime("%H:%M:%S")
    if isinstance(t, str):
        return t
    raise TypeError(f"Unsupported time type: {type(t)}")

def date_to_str(d):
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()   # YYYY-MM-DD
    if isinstance(d, date):
        return d.isoformat()         # YYYY-MM-DD
    if isinstance(d, str):
        return d
    raise TypeError(f"Unsupported date type: {type(d)}")

def return_appointments(appointment_details: dict) -> str:
    index = 1
    if appointment_details["customer"]["email"]:
        email = appointment_details["customer"]["email"]
    else:
        email = "Không có"
        
    service_detail = (
        f"Thời gian đặt: {appointment_details["booking_date"]}\n"
        f"Thơi gian bắt đầu: {appointment_details["start_time"]}\n"
        f"Thời gian kết thúc: {appointment_details["end_time"]}\n"
        f"Tổng thời gian: {appointment_details["total_time"]} phút\n"
        f"Ghi chú: {appointment_details["note"]}\n\n"
        
        f"Tên khách: {appointment_details["customer"]["name"]}\n"
        f"SĐT khách: {appointment_details["customer"]["phone"]}\n"
        f"Email khách: {email}\n\n"
        f"Nhân viên thực hiện: {appointment_details["staff"]["name"]}\n"
        f"Phòng: {appointment_details["room"]["name"]}\n\n"
        "Các dịch vụ khách đã đăng ký:\n"
    )
    
    for service in appointment_details["appointment_services"]:
        price = service["services"]["price"]
        discount_value = service["services"]["service_discounts"][0]["discount_value"]
        price_after_discount = int(price * (1 - discount_value / 100))
        
        service_detail += (
            f"STT: {index}\n"
            f"Loại dịch vụ: {service["services"]["type"]}\n"
            f"Tên dịch vụ: {service["services"]["name"]}\n"
            f"Thời gian: {service["services"]["duration_minutes"]}\n"
            f"Giá: {price}VNĐ\n"
            f"Giảm giá: {discount_value}%\n"
            f"Giá sau giảm: {price_after_discount}VNĐ\n\n"
        )
        
        index += 1
    
    service_detail += (
        f"Tổng giá tiền: {appointment_details["total_price"]}VNĐ\n"
        # f"Giảm giá: {appointment_details["total_discount"]}%\n"
        # f"Tổng tiền sau giảm: {appointment_details["price_after_discount"]}VNĐ\n"
    )
    
    return service_detail

def convert_date_str(date_str: str) -> str:
    # Chuyển từ định dạng ISO “YYYY-MM-DD” sang “DD-MM-YYYY”
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d-%m-%Y")

def update_book_info(appointment_details: dict) -> BookInfo:
    booked_services = {}
    for service in appointment_details["appointment_services"]:
        service = service["services"]
        booked_services[service["id"]] = Services(
            service_id=service["id"],
            service_type=service["type"],
            service_name=service["name"],
            duration_minutes=service["duration_minutes"],
            price=service["price"]
        )
    
    book_info = BookInfo(
        appointment_id=appointment_details["id"],
        booking_date=appointment_details["booking_date"],
        start_time=appointment_details["start_time"],
        end_time=appointment_details["end_time"],
        total_time=appointment_details["total_time"],
        note=appointment_details["note"],
        
        status=appointment_details["status"],
        total_price=appointment_details["total_price"],
        total_discount=appointment_details["total_discount"],
        price_after_discount=appointment_details["price_after_discount"],
        create_date=appointment_details["created_at"],
        
        services=booked_services,
        customer=Customer(
            customer_id=appointment_details["customer"]["id"],
            name=appointment_details["customer"]["name"],
            phone=appointment_details["customer"]["phone"],
            email=appointment_details["customer"]["email"] if appointment_details["customer"]["email"] else ""
        ),
        staff=Staff(
            staff_id=appointment_details["staff"]["id"],
            name=appointment_details["staff"]["name"]
        ),
        room=Room(
            room_id=appointment_details["room"]["id"],
            room_name=appointment_details["room"]["name"]
        )
    )
    
    return book_info

def parese_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def parse_time(s: str) -> time:
    return datetime.strptime(s, "%H:%M:%S").time()

def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute

def minutes_to_time(m: int) -> time:
    h = m // 60
    mi = m % 60
    return time(hour=h, minute=mi)

def free_slots(
    orders: list, 
    key: str, 
    key_id: int, 
    open_time_str: str = OPEN_TIME_STR, 
    close_time_str: str = CLOSE_TIME_STR
) -> list:
    """
    orders: list các order
    key: "room_id" hoặc "staff_id"
    key_id: giá trị cụ thể (ví dụ room_id = 1 hoặc staff_id = 2)
    open_time_str, close_time_str: giờ mở & đóng cửa
    Trả về list các khoảng thời gian rỗi cho key = key_id
    """
    # lọc orders theo key
    filtered = [o for o in orders if o.get(key) == key_id]
    
    # convert thành các interval (start, end) bằng phút
    intervals = []
    for o in filtered:
        st = time_to_minutes(parse_time(o["start_time"]))
        et = time_to_minutes(parse_time(o["end_time"]))
        intervals.append( (st, et) )
    intervals.sort(key=lambda x: x[0])
    
    open_min = time_to_minutes(parse_time(open_time_str))
    close_min = time_to_minutes(parse_time(close_time_str))
    
    free_slots = []
    
    if not intervals:
        # nếu không có lịch nào → rỗi nguyên khung
        free_slots.append( (open_min, close_min) )
    else:
        # Trước booking đầu
        first_start = intervals[0][0]
        if first_start > open_min:
            free_slots.append( (open_min, first_start) )
        
        # Giữa các booking
        for i in range(len(intervals) - 1):
            end_current = intervals[i][1]
            next_start = intervals[i+1][0]
            if next_start > end_current:
                free_slots.append( (end_current, next_start) )
        
        # Sau booking cuối tới đóng cửa
        last_end = intervals[-1][1]
        if last_end < close_min:
            free_slots.append( (last_end, close_min) )
    
    # convert lại thành time string cho dễ nhìn
    free_slots_str = []
    for (s_min, e_min) in free_slots:
        s_time = minutes_to_time(s_min).strftime("%H:%M:%S")
        e_time = minutes_to_time(e_min).strftime("%H:%M:%S")
        free_slots_str.append({"start_time": s_time, "end_time": e_time})
    
    return free_slots_str

def free_slots_all(
    orders: list, 
    rooms_dict: dict, 
    staffs_dict: dict, 
    open_time_str: str = OPEN_TIME_STR, 
    close_time_str: str = CLOSE_TIME_STR    
):
    result = {
        "rooms": {},
        "staff": {}
    }
    # gom tất cả các key cần xét
    # room_ids và staff_ids
    room_ids = list(rooms_dict.keys())
    staff_ids = list(staffs_dict.keys())
    # duyệt lần lượt
    for key_type, key_ids in [("room_id", room_ids), ("staff_id", staff_ids)]:
        # key_type là "room_id" hoặc "staff_id"
        for kid in key_ids:
            result_field = "rooms" if key_type == "room_id" else "staff"
            result[result_field][kid] = free_slots(
                orders=orders,
                key=key_type,
                key_id=kid,
                open_time_str=open_time_str,
                close_time_str=close_time_str
            )
            
    return result

def staff_free_in_interval(
    orders: dict, 
    interval_start_min: int, 
    interval_end_min: int, 
    staffs: dict
) -> dict:
    
    free_staff = {}
    for st_id in staffs.keys():
        # tìm các order của staff này
        st_orders = [o for o in orders if o["staff_id"] == st_id]
        # nếu có bất kỳ order nào overlap với interval → không rỗi
        busy = False
        for o in st_orders:
            o_st = time_to_minutes(parse_time(o["start_time"]))
            o_et = time_to_minutes(parse_time(o["end_time"]))
            # kiểm tra overlap: (o_st < interval_end) và (o_et > interval_start)
            if (o_st < interval_end_min) and (o_et > interval_start_min):
                busy = True
                break
        if not busy:
            free_staff[st_id] = staffs[st_id]
    return free_staff

# Hàm free slots với capacity ≥ k + staff rỗi
def free_slots_with_staff(
    orders: dict, 
    room_id: int, 
    room_capacity: int, 
    staffs: dict, 
    k: int,
    open_time_str: str = OPEN_TIME_STR, 
    close_time_str: str = CLOSE_TIME_STR, 
) -> list:
    if not orders:  # orders is None or []
        return [{
            "start_time": open_time_str,
            "end_time": close_time_str,
            "free_capacity": room_capacity,
            "free_staffs": staffs   # tất cả nhân viên
        }]
    
    # Lọc orders của phòng
    room_orders = [o for o in orders if o["room_id"] == room_id]

    # Tạo event +1, -1 cho room bookings
    events = []
    for o in room_orders:
        st = time_to_minutes(parse_time(o["start_time"]))
        et = time_to_minutes(parse_time(o["end_time"]))
        events.append((st, +1))
        events.append((et, -1))

    open_min = time_to_minutes(parse_time(open_time_str))
    close_min = time_to_minutes(parse_time(close_time_str))
    events.append((open_min, 0))
    events.append((close_min, 0))

    # sort event
    events.sort(key=lambda x: (x[0], x[1]))

    free_slots = []
    curr_active = 0
    prev_time = open_min

    for time_point, delta in events:
        if time_point > prev_time:
            free_capacity = room_capacity - curr_active
            if free_capacity >= k:
                # đây là khoảng có ≥ k chỗ
                interval_start = prev_time
                interval_end = time_point
                # tìm staff rỗi trong khoảng này
                free_staff = staff_free_in_interval(
                    orders=orders, 
                    interval_start_min=interval_start, 
                    interval_end_min=interval_end, 
                    staffs=staffs
                )
                free_slots.append({
                    "start_time": minutes_to_time(interval_start).strftime("%H:%M:%S"),
                    "end_time":   minutes_to_time(interval_end).strftime("%H:%M:%S"),
                    "free_capacity": free_capacity,
                    "free_staffs": free_staff
                })
        curr_active += delta
        prev_time = time_point

    return free_slots

def interval_covers(s_free: str, e_free: str, s_req: str, e_req: str) -> bool:
    """
    s_free, e_free, s_req, e_req đều là string "HH:MM:SS"
    Trả True nếu [s_req, e_req] nằm hoàn toàn trong [s_free, e_free]
    """
    start_free = time_to_minutes(parse_time(s_free))
    end_free   = time_to_minutes(parse_time(e_free))
    start_req  = time_to_minutes(parse_time(s_req))
    end_req    = time_to_minutes(parse_time(e_req))
    
    return (start_free <= start_req) and (end_req <= end_free)

# Hàm chính: tìm phòng + chọn nhân viên ngẫu nhiên
def choose_room_and_staff(free_dict: dict, s_req: str, e_req: str):
    """
    free_dict: dict mapping room_id → list of khoảng trống, mỗi khoảng có
               {start_time, end_time, free_capacity, free_staffs}
    s_req, e_req: thời gian khách muốn đặt
    Trả về (room_id, staff_id, staff_name) nếu có; nếu không có phòng phù hợp trả None
    """
    # duyệt qua các phòng theo thứ tự key (như “từ trên xuống dưới”)
    for room_id, slots in free_dict.items():
        # nếu không có slot trống nào skip
        if not slots:
            continue
        for slot in slots:
            # nếu slot này bao phủ thời gian khách muốn
            if interval_covers(slot["start_time"], slot["end_time"], s_req, e_req):
                # nếu có free_staffs và không rỗng
                fs = slot.get("free_staffs", {})
                if fs:
                    # chọn ngẫu nhiên staff_id trong dict free_staffs
                    staff_id = random.choice(list(fs.keys()))
                    return {
                        "room_id": room_id,
                        "staff_id": staff_id
                    }
                else:
                    return {
                        "room_id": room_id,
                        "staff_id": None
                    }
    # nếu không tìm được phòng nào phù hợp
    return {
        "room_id": None,
        "staff_id": None
    }

def cal_discount(
    total_price: int, 
    services: dict,
    new_customer: bool | None
) -> tuple[float, int, str]:
    if not new_customer:
        new_customer = False
    
    total_discount = Decimal('0.0')
    explain = ""
    services_len = services.__len__()
    
    # Calculate new customer discount
    if new_customer:
        discount = Decimal(str(NEW_CUSTOMER_DISCOUNT))
        total_discount += discount
        explain += f"- Khách hàng mới được giảm {float(discount)*100}%\n"
    
    # Calculate service count discount
    if services_len == 2:
        discount = Decimal(str(TWO_SERVICES_DISCOUNT))
        total_discount += discount
        explain += f"- Sử dụng 2 dịch vụ được giảm {float(discount)*100}%\n"
    elif services_len == 3:
        discount = Decimal(str(THREE_SERVICES_DISCOUNT))
        total_discount += discount
        explain += f"- Sử dụng 3 dịch vụ được giảm {float(discount)*100}%\n"
    elif services_len >= 4:
        discount = Decimal(str(FOUR_PLUS_SERVICES_DISCOUNT))
        total_discount += discount
        explain += f"- Sử dụng 4 dịch vụ trở lên được giảm {float(discount)*100}%\n"
    
    price_after_discount = total_price * (1 - float(total_discount))
    total_discount = float(total_discount) * 100
    explain += f"- Tổng giảm giá: {total_discount}%\n"
    
    return total_discount, price_after_discount, explain