import traceback
from typing import Optional, Annotated

from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

from core.utils.function import build_update, cal_discount
from core.graph.state import AgentState, BookInfo, Customer, Services, Staff

from log.logger_config import setup_logging

logger = setup_logging(__name__)

def _return_selective_services(
    services: dict,
    total_time: int,
    total_price: int,
    total_discount: float = 0.0,
    explain: str = "",
    price_after_discount: int = 0,
) -> str:
    index = 1
    service_detail = ""
    
    for service in services.values():
        service_detail += (
            f"STT: {index}\n"
            f"Loại dịch vụ: {service["service_type"]}\n"
            f"Tên dịch vụ: {service["service_name"]}\n"
            f"Thời gian: {service["duration_minutes"]}\n"
            f"Giá: {service["price"]} VNĐ\n"
            f"Giảm giá: {service["discount_value"]}%\n"
            f"Giá sau giảm: {int(service["price_after_discount"])} VNĐ\n\n"
        )
        
        index += 1
        
    service_detail += (
        f"Tổng thời gian: {total_time}\n"
        f"Tổng giá tiền: {int(total_price)} VNĐ\n"
    )
    
    if total_discount != 0.0:
        service_detail += (
            f"Giảm giá: {total_discount}%\n"
            f"Chi tiết giảm giá: \n{explain}\n"
            f"Tổng tiền sau giảm: {int(price_after_discount)}\n"
        )
    
    return service_detail

def _update_services_state(
    services_state: dict | None,
    seen_services: dict,
    service_id_list: list[dict]
) -> tuple[dict, int, int]:
    if services_state is None:
        services_state = {}

    total_time = 0
    total_price = 0
    
    for id in service_id_list:
        services_state[id] = Services(
            service_id=id,
            service_type=seen_services[id]["service_type"],
            service_name=seen_services[id]["service_name"],
            duration_minutes=seen_services[id]["duration_minutes"],
            price=seen_services[id]["price"],
            discount_value=seen_services[id]["discount_value"],
            price_after_discount=seen_services[id]["price_after_discount"]
        )
        
        total_time += seen_services[id]["duration_minutes"]
        total_price += seen_services[id]["price_after_discount"]
    
    return services_state, total_time, total_price

@tool
def add_service_tool(
    service_id_list: Annotated[Optional[list[int]], (
        "Đây là danh sách các id của các dịch vụ mà khách chọn, "
        "được lấy trong danh sách seen_services"
    )],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng tool này để lưu lại các dịch vụ mà khách chọn
    
    Parameters:
        - service_id_list: 
            - Danh sách các id của các dịch vụ mà khách chọn. 
            - Nhìn vào danh sách seen_services, tìm dịch vụ nào có tên tương ứng với yêu cầu của khách và lấy id của dịch vụ đó.

    """
    logger.info(f"add_service_tool được gọi")
    
    if not service_id_list:
        logger.info("Không xác định được dịch vụ khách chọn")
        return Command(
            update=build_update(
                content=(
                    "Không biết khách chọn dịch vụ nào, hỏi lại khách"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    try:
        services_state, new_total_time, new_total_price = _update_services_state(
            services_state=state["services"],
            seen_services=state["seen_services"],
            service_id_list=service_id_list
        )
        
        logger.info("Thêm dịch vụ khách chọn vào state thành công")
        
        old_total_time = state["total_time"] if state["total_time"] is not None else 0
        old_total_price = state["total_price"] if state["total_price"] is not None else 0
        
        total_time = old_total_time + new_total_time
        total_price = old_total_price + new_total_price
        
        # total_discount, price_after_discount, explain = cal_discount(
        #     total_price=total_price,
        #     services=state["services"],
        #     new_customer=state["new_customer"]
        # )
        
        service_detail = _return_selective_services(
            services=services_state,
            total_time=total_time,
            total_price=total_price,
            # total_discount=total_discount,
            # explain=explain,
            # price_after_discount=price_after_discount
        )
        
        return Command(
            update=build_update(
                content=(
                    "Đây là thông tin các dịch vụ mà khách chọn:\n"
                    f"{service_detail}\n"
                ),
                tool_call_id=tool_call_id,
                services=services_state,
                total_time=total_time,
                total_price=total_price,
                # total_discount=total_discount,
                # price_after_discount=price_after_discount,
                # explain=explain
            )
        )
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise
    
@tool
def remove_service_tool(
    service_id_list: Annotated[Optional[list[int]], (
        "Đây là danh sách các id của các dịch vụ mà khách muốn xóa, "
        "được lấy trong danh sách seen_services"
    )],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng tool này để xóa các dịch vụ mà khách không muốn làm nữa
    
    Parameters:
        - service_id_list: danh sách các id của các dịch vụ mà khách muốn xóa

    """
    logger.info(f"remove_service_tool được gọi")
    
    if not service_id_list:
        logger.info("Không xác định được dịch vụ khách muốn xóa")
        return Command(
            update=build_update(
                content=(
                    "Không biết khách muốn xóa dịch vụ nào, hỏi lại khách"
                ),
                tool_call_id=tool_call_id
            )
        )
        
    try:
        if not state["services"]:
            logger.info("Danh sách services rỗng -> không thể xóa")
            return Command(
                update=build_update(
                    content=(
                        "Khách chưa chọn dịch vụ nào, không thể xóa"
                    ),
                    tool_call_id=tool_call_id
                )
            )
        
        for id in service_id_list:
            if id in state["services"]:
                del state["services"][id]
        
        total_time = 0
        total_price = 0
        
        for service in state["services"].values():
            total_time += service["duration_minutes"]
            total_price += service["price_after_discount"]
            
        # total_discount, price_after_discount, explain = cal_discount(
        #     total_price=total_price,
        #     services_len=state["services"].__len__(),
        #     new_customer=state["new_customer"]
        # )
        
        service_detail = _return_selective_services(
            services=state["services"],
            total_time=total_time,
            total_price=total_price,
            # total_discount=total_discount,
            # explain=explain,
            # price_after_discount=price_after_discount
        )
        
        logger.info("Xóa dịch vụ khách không muốn làm nữa thành công")
        
        return Command(
            update=build_update(
                content=(
                    "Đây là thông tin các dịch vụ còn lại mà khách chọn:\n"
                    f"{service_detail}\n"
                ),
                tool_call_id=tool_call_id,
                services=state["services"],
                total_time=total_time,
                total_price=total_price,
                # total_discount=total_discount,
                # price_after_discount=price_after_discount,
                # explain=explain
            )
        )
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise