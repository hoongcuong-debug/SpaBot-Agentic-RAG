from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.tools import booking_toolbox
from core.graph.state import AgentState
from database.connection import specialist_llm

from log.logger_config import setup_logging

logger = setup_logging(__name__)

class BookingAgent:
    def __init__(self):
        with open("core/prompts/booking_agent_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = """
        Các thông tin bạn nhận được:
        - Ngày hiện tại current_date: {current_date}
        - Tên của khách hàng customer_name: {name}
        - SĐT của khách phone: {phone}
        - Email của khách: {email}
        - Ngày đặt booking_date: {booking_date}
        - Thời gian đặt start_time: {start_time}
        - Các dịch vụ khách đã xem seen_products: {seen_services}
        - Các dịch vụ khách đã chọn services: {services}
        - Ghi chú của khách note: {note}
        """
            
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", context + system_prompt),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        self.agent = create_react_agent(
            model=specialist_llm,
            tools=booking_toolbox,
            prompt=self.prompt,
            state_schema=AgentState
        )
    
    def booking_agent_node(self, state: AgentState) -> Command:
        """
        Xử lý các yêu cầu liên quan đến đơn hàng (lên đơn, cập nhật, hủy, ...) bằng `order_toolbox`.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        """
        try:
            result = self.agent.invoke(state)
            content = result["messages"][-1].content
            
            update = {
                "messages": [AIMessage(content=content, name="booking_agent_node")],
                "next": "__end__"
            }
            
            for key in [
                "customer_id", "name", "phone", "email", "booking_date", "note",
                "start_time", "end_time", "room_id", "room_name", "staff_id", "staff_name",
                "book_info", "seen_services", "services", "total_price", "total_time",
                "total_discount", "price_after_discount", "explain"
            ]:
                if result.get(key, None) is not None:
                    update[key] = result[key]
            
            return Command(
                update=update,
                goto="__end__"
            )
            
        except Exception as e:
            logger.error(f"Lỗi: {e}")
            raise