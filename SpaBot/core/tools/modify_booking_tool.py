from math import e
import traceback
from typing import Optional, Annotated

from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

from core.graph.state import AgentState
from database.connection import supabase_client
from repository.sync_repo import AppointmentRepo, RoomRepo, StaffRepo
from core.utils.function import (
    build_update, 
    return_appointments,
    update_book_info
)

from log.logger_config import setup_logging

logger = setup_logging(__name__)

appointment_repo = AppointmentRepo(supabase_client=supabase_client)
room_repo = RoomRepo(supabase_client=supabase_client)
staff_repo = StaffRepo(supabase_client=supabase_client)

@tool
def cancel_booking_tool(
    appointment_id: Annotated[Optional[int], "ID của lịch hẹn mà khách muốn huỷ"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng tool này để huỷ đặt lịch
    
    Tham số:
        - appointment_id (int | None): ID của lịch hẹn mà khách muốn huỷ, lấy trong book_info
    """
    logger.info(f"cancel_booking_tool được gọi")
    
    if not appointment_id:
        logger.info("Không xác định được lịch hẹn khách muốn huỷ")
        return Command(
            update=build_update(
                content=(
                    "Không biết khách muốn huỷ lịch hẹn nào, hỏi lại khách"
                ),
                tool_call_id=tool_call_id
            )
        )
    
    book_info = state["book_info"].copy()
    if appointment_id not in book_info:
        logger.info(f"Lịch hẹn với ID {appointment_id} không tồn tại trong book_info")
        return Command(
            update=build_update(
                content=(
                    f"Lịch hẹn với ID {appointment_id} không tồn tại"
                ),
                tool_call_id=tool_call_id
            )
        )
    
    try:
        success = appointment_repo.update_appointment(
            appointment_id=appointment_id,
            update_payload={"status": "cancelled"}
        )
        
        if not success:
            logger.error(f"Lỗi ở cấp DB -> Không thể huỷ lịch hẹn với ID {appointment_id}")
            return Command(
                update=build_update(
                    content=(
                        "Không thể huỷ lịch hẹn, xin lỗi khách và hứa sẽ khắc phục sớm nhất."
                    ),
                    tool_call_id=tool_call_id
                )
            )
            
        del book_info[appointment_id]
        logger.info(f"Huỷ lịch hẹn với ID {appointment_id} thành công")
        
        return Command(
            update=build_update(
                content=(
                    f"Đã huỷ lịch hẹn thành công. ID lịch hẹn: {appointment_id}."
                ),
                tool_call_id=tool_call_id,
                book_info=book_info
            )
        )
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise
    
@tool
def get_all_editable_booking(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng tool này để lấy tất cả các lịch hẹn có thể chỉnh sửa (status = 'booked') theo customer_id.

    Args:
        - customer_id (int): ID của khách hàng.
        - state (AgentState): Trạng thái hiện tại của agent.
        - tool_call_id (str): ID của tool call.
    """
    logger.info(f"get_all_editable_booking được gọi")
    
    if not state["customer_id"]:
        logger.error("Không xác định được ID của khách hàng")
        return Command(
            update=build_update(
                content=(
                    "Có lỗi trong quá trình xác định khách hàng, xin lỗi khách"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    try:
        # Lấy danh sách các lịch hẹn có trạng thái 'booked' theo customer_id
        booked_appointments = appointment_repo.get_all_booked_appointments(
            customer_id=state["customer_id"]
        )
        
        if not booked_appointments:
            logger.info("Không có lịch hẹn nào có thể chỉnh sửa")
            return Command(
                update=build_update(
                    content="Hiện tại không có lịch hẹn nào có thể chỉnh sửa.",
                    tool_call_id=tool_call_id
                )
            )
        
        book_info = state["book_info"].copy() if state["book_info"] else {}
        formatted_appointments = ""
        index = 1
        
        for booked in booked_appointments:
            book_info[booked["id"]] = update_book_info(
                appointment_details=booked
            )
            
            formatted_appointments += (
                f"Đơn thứ {index}:\n"
                f"{return_appointments(appointment_details=booked)}\n\n"
            )
            
            index += 1
        
        logger.info("Lấy danh sách lịch hẹn thành công")
        return Command(
            update=build_update(
                content=(
                    "Đây là danh sách các lịch hẹn mà khách có thể chỉnh sửa:\n"
                    f"{formatted_appointments}"
                ),
                tool_call_id=tool_call_id,
                book_info=book_info
            )
        )
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise

@tool
def edit_time_booking_tool(
    appointment_id: Annotated[Optional[int], "ID của lịch hẹn mà khách muốn huỷ"],
    booking_date_new: Annotated[Optional[str], "Ngày tháng năm cụ thể khách đặt lịch"],
    start_time_new: Annotated[Optional[str], "Thời gian khách muốn đặt lịch"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng tool này để thay đổi lịch đã đặt của khách
    
    Parameters:
        - appointment_id (int | None): ID của lịch hẹn mà khách muốn thay đổi, lấy trong book_info
        - booking_date_new (str | None)
            - Ngày tháng năm mà khách đặt, bắt buộc có định dạng "%Y-%m-%d".
            - Nếu khách chỉ đổi thời gian, giữ nguyên ngày thì tham số này giữ nguyên ngày trong `book_info`.
            - **Tham số này chấp nhận None**
        - start_time_new (str | None)
            - Giờ phút giây mà khách đặt, bắt buộc có định dạng "%H:%M:%S"
            - Nếu khách chỉ đổi ngày, giữ nguyên thời gian thì tham số này giữ nguyên thời gian trong `book_info`.
            - **Tham số này chấp nhận None**
    """
    logger.info(f"edit_time_booking_tool được gọi")
    
    if not appointment_id:
        logger.info("Không xác định được lịch hẹn khách muốn huỷ")
        return Command(
            update=build_update(
                content=(
                    "Không biết khách muốn huỷ lịch hẹn nào, hỏi lại khách"
                ),
                tool_call_id=tool_call_id
            )
        )
    
    book_info = state["book_info"].copy()
    if appointment_id not in book_info:
        logger.info(f"Lịch hẹn với ID {appointment_id} không tồn tại trong book_info")
        return Command(
            update=build_update(
                content=(
                    f"Lịch hẹn với ID {appointment_id} không tồn tại"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    if not booking_date_new:
        logger.info("Không xác định được ngày khách muốn thay đổi")
        return Command(
            update=build_update(
                content=(
                    "Không xác định được ngày khách muốn đổi, hỏi khách"
                ),
                tool_call_id=tool_call_id
            )
        )
            
    if not start_time_new:
        logger.info("Không xác định được thời gian khách muốn thay đổi")
        return Command(
            update=build_update(
                content=(
                    "Không xác định được thời gian khách muốn đổi, hỏi khách"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    logger.info(f"Khách đặt ngày: {booking_date_new} vào lúc: {start_time_new}")
    
    try:
        update_payload = {}
        if booking_date_new:
            update_payload["booking_date"] = booking_date_new
        if start_time_new:
            update_payload.update(
                {
                    "start_time": start_time_new,
                    "end_time": state["end_time"]
                }
            )
            
        update_payload.update(
            {
                "room_id": state["room_id"],
                "staff_id": state["staff_id"]
            }
        )
            
        success = appointment_repo.update_appointment(
            appointment_id=appointment_id,
            update_payload=update_payload
        )
        
        if not success:
            logger.error(f"Lỗi ở cấp DB -> Không thể thay đổi lịch hẹn với ID {appointment_id}")
            return Command(
                update=build_update(
                    content=(
                        "Không thể thay đổi lịch hẹn, xin lỗi khách và hứa sẽ khắc phục sớm nhất."
                    ),
                    tool_call_id=tool_call_id
                )
            )
            
        appointment_details = appointment_repo.get_appointment_details(
            appointment_id=appointment_id
        )
        
        booking_detail = return_appointments(
            appointment_details=appointment_details
        )
        
        book_info = state["book_info"].copy() if state["book_info"] else {}
        book_info[appointment_details["id"]] = update_book_info(
            appointment_details=appointment_details
        )
        
        logger.info(f"Thay đổi lịch hẹn với ID {appointment_id} thành công")
        
        return Command(
            update=build_update(
                content=(
                    "Thay đổi lịch cho khách thành công, "
                    "đây là chi tiết lịch sau khi thay đổi của khách:\n"
                    f"{booking_detail}\n"
                ),
                tool_call_id=tool_call_id,
                book_info=book_info
            )
        )
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise
    
@tool
def edit_services_booking_tool(
    appointment_id: Annotated[Optional[int], "ID của lịch hẹn mà khách muốn huỷ"],
    remove_service_ids: Annotated[Optional[list[int]], "Danh sách ID dịch vụ khách muốn xoá"],
    add_service_ids: Annotated[Optional[list[int]], "Danh sách ID dịch vụ khách muốn thêm"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dung tool này để thay đổi các dịch vụ mà khách đã đặt lịch
    
    Parameters:
        - appointment_id (int | None): ID của lịch hẹn mà khách muốn thay đổi, lấy trong book_info
        - remove_service_ids (list[int] | None): Danh sách ID dịch vụ khách muốn xoá. Được lấy trong `book_info`
        - add_service_ids (list[int] | None): Danh sách ID dịch vụ khách muốn thêm. Được lấy trong `seen_services`
    """
    logger.info(f"edit_time_booking_tool được gọi")
    
    if not appointment_id:
        logger.info("Không xác định được lịch hẹn khách muốn huỷ")
        return Command(
            update=build_update(
                content=(
                    "Không biết khách muốn huỷ lịch hẹn nào, hỏi lại khách"
                ),
                tool_call_id=tool_call_id
            )
        )
    
    book_info = state["book_info"].copy()
    if appointment_id not in book_info:
        logger.info(f"Lịch hẹn với ID {appointment_id} không tồn tại trong book_info")
        return Command(
            update=build_update(
                content=(
                    f"Lịch hẹn với ID {appointment_id} không tồn tại"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    if not remove_service_ids:
        logger.info("Không xác định được dịch vụ khách muốn xoá")
        return Command(
            update=build_update(
                content=(
                    "Không xác định được dịch vụ khách muốn xoá, hỏi khách"
                ),
                tool_call_id=tool_call_id
            )
        )
    
    if not add_service_ids:
        logger.info("Không xác định được dịch vụ khách muốn thêm")
        return Command(
            update=build_update(
                content=(
                    "Không xác định được dịch vụ khách muốn thêm, hỏi khách"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    try:
        pass
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise