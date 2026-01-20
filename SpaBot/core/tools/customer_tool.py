import traceback
from typing import Annotated, Optional

from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

from core.graph.state import AgentState
from core.utils.function import build_update
from repository.sync_repo import CustomerRepo
from database.connection import supabase_client

from log.logger_config import setup_logging

logger = setup_logging(__name__)

customer_repo = CustomerRepo(supabase_client=supabase_client)

@tool
def modify_customer_tool(
    new_name: Annotated[Optional[str], "Tên khách muốn thêm vào hoặc cập nhật"],
    new_phone: Annotated[Optional[str], "Số điện thoại khách muốn thêm vào hoặc cập nhật"],
    new_email: Annotated[Optional[str], "Email khách muốn thêm vào hoặc cập nhật"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này để chỉnh sửa thông tin của khách hàng.

    Chức năng: Chỉnh sửa thông tin (tên, số điện thoại, địa chỉ) cho một khách hàng đã tồn tại trong hệ thống.

    Tham số:
        - new_phone (str): Số điện thoại mới của khách hàng. Dùng để xác định và cập nhật thông tin.
        - new_name (str, tùy chọn): Tên mới của khách hàng.
        - new_address (str, tùy chọn): Địa chỉ mới của khách hàng.
    """
    logger.info("modify_customer_tool được gọi")
    
    if not any([new_name, new_phone]):
        logger.info(f"Khách thiếu ít nhất 1 thông tin Tên: {new_name} | Số điện thoại: {new_phone}")
        return Command(
            update=build_update(
                content="Khách phải cung cấp ít nhất một thông tin liên quan đến tên và số điện thoại để cập nhật, hỏi khách",
                tool_call_id=tool_call_id
            )
        )

    try:
        logger.info("Kiểm tra khách hàng")
        check_customer_exist = customer_repo.check_customer_id(
            customer_id=state["customer_id"]
        )
        
        # Nếu khách không tồn tại -> thông báo
        if not check_customer_exist:
            logger.error("Lỗi không tìm thấy khách hàng")
            return Command(
                update=build_update(
                    content=f"Không tìm thấy khách hàng, xin lỗi khách",
                    tool_call_id=tool_call_id
                )
            )

        logger.info("Thấy thông tin khách hàng")
        update_payload = {}
        if new_name:
            update_payload['name'] = new_name
        if new_phone:
            update_payload['phone'] = new_phone
        if new_email:
            update_payload['email'] = new_email

        logger.info(f"Cập nhật thông tin khách tên: {new_name} | SĐT: {new_phone} | email: {new_email}")
        updated_info = customer_repo.update_customer_by_customer_id(
            update_payload=update_payload,
            customer_id=state["customer_id"]
        )
        
        if not updated_info:
            logger.error("Xảy ra lỗi ở cấp DB -> Không thể cập nhật khách")
            return Command(
                update=build_update(
                    content=(
                        "Có lỗi trong quá trình thể cập nhật "
                        f"thông tin cho khách hàng có ID {state["customer_id"]}"
                    ),
                    tool_call_id=tool_call_id
                )
            )
        
        logger.info("Cập nhật thông tin khách thành công")
        return Command(
            update=build_update(
                content=(
                    "Đã cập nhật thông tin khách thành công:\n"
                    f"- Tên khách hàng: {updated_info["name"]}\n"
                    f"- Số điện thoại khách hàng {updated_info["phone"]}\n"
                    f"- Email khách hàng: {updated_info["email"]}\n"
                ),
                tool_call_id=tool_call_id,
                name=updated_info["name"],
                phone=updated_info["phone"],
                email=updated_info["email"],
            )
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise