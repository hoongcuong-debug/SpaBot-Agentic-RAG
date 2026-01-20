from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field

from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.graph.state import AgentState 
from repository.sync_repo import CustomerRepo
from database.connection import supabase_client
from database.connection import orchestrator_llm

from log.logger_config import setup_logging

logger = setup_logging(__name__)

class Route(BaseModel):
    """Chọn agent tiếp theo để xử lý yêu cầu."""
    next: Literal[
        "service_agent", 
        "booking_agent", 
        "modify_booking_agent", 
        "fallback_agent",
        "__end__"
    ] = Field(
        description=(
            "Chọn 'service_agent' cho các câu hỏi về dịch vụ, "
            "'booking_agent' cho các tác vụ liên quan đến lên lịch đặt"
            ", 'modify_booking_agent' để thay đổi hoặc hủy đặt chỗ, "
            "'fallback_agent' để xử lý các trường hợp chatbot không thể xử lý được, "
            "và '__end__' để kết thúc."
        )
    )

class Supervisor:
    def __init__(self):
        with open("core/prompts/supervisor_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = (
            "Các thông tin bạn nhận được:\n"
            "- Các dịch vụ khách chọn: {services}\n"
            "- Lịch khách đã đặt thành công: {book_info}"
        )
            
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{user_input}")
        ])
        
        self.chain = self.prompt | orchestrator_llm.with_structured_output(Route)
        self.customer_repo = CustomerRepo(supabase_client=supabase_client)
        
    def supervisor_node(self, state: AgentState) -> Command:
        """
        Phân luồng yêu cầu của khách tới agent phù hợp dựa trên `state` và prompt điều phối.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, trường `next` và điều hướng `goto` tới node tiếp theo.
        """
        update = {}
        try:
            if not state["customer_id"]:
                customer = self.customer_repo.get_or_create_customer(
                    chat_id=state["chat_id"]
                )
                
                logger.info(f"Tạo mới hoặc lấy thông tin khách: {customer}")

                if not customer:
                    logger.error("Lỗi không lấy được thông tin khách")
                else:
                    update.update({
                        "customer_id": customer.get("id"),
                        "name": customer.get("name"),
                        "phone": customer.get("phone"),
                        "emai": customer.get("email")
                    })
                    state["customer_id"] = customer.get("id")
            else:
                logger.info(
                    "Thông tin của khách: "
                    f"- Tên: {state["name"]} | "
                    f"- Số điện thoại: {state["phone"]} | "
                    f"- Email: {state["email"]}"
                )
            
            # Check the customer is new or not
            if state["new_customer"] is None:
                update["new_customer"] = self.customer_repo.is_new_customer(
                    customer_id=state.get("customer_id", 0)
                )
                state["new_customer"] = update["new_customer"]
            
            logger.info(f"New customer: {state["new_customer"]}")
            logger.info(f"Yêu cầu của khách: {state["user_input"]}")
            
            result = self.chain.invoke(state)
            
            next_node = result.next
            update["next"] = next_node
            update["messages"] = [HumanMessage(
                content=state["user_input"]
            )]
            update.update({
                "next": next_node,
                "messages": [HumanMessage(
                    content=state["user_input"]
                )],
                "current_date": str(datetime.now().strftime("%A, %d-%m-%Y"))
            })
            
            logger.info(f"Agent tiếp theo: {next_node}")
    
            return Command(
                update=update,
                goto=next_node
            )
        
        except Exception as e:
            logger.error(f"Lỗi: {e}")
            raise
        