import traceback
from langgraph.types import Command
from core.graph.state import AgentState
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.tools import fallback_toolbox
from database.connection import specialist_llm 

from log.logger_config import setup_logging

logger = setup_logging(__name__)

class FallbackAgent:
    def __init__(self):
        with open("core/prompts/fallback_agent_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = """
        Information you receive:
        - Customer's name (name): {name}
        - Customer's phone (phone): {phone}
        - Services the customer has viewed (seen_products): {seen_services}
        - Appointments the customer has made (book_info): {book_info}
        """

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        self.agent = create_react_agent(
            model=specialist_llm,
            tools=fallback_toolbox,
            prompt=self.prompt,
            state_schema=AgentState
        )

    def fallback_agent_node(self, state: AgentState) -> Command:
        """
        Xử lý các yêu cầu mà chatbot không thể xử lý được.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, `seen_products` (nếu có) và kết thúc luồng.
        """
        try:
            result = self.agent.invoke(state)
            content = result["messages"][-1].content
            
            update = {
                "messages": [AIMessage(content=content, name="complaint_agent_node")],
                "next": "__end__"
            }
            
            for key in [
                "customer_id", "name", "phone", "email", "book_info"
            ]:
                if result.get(key, None) is not None:
                    update[key] = result[key]
                            
            return Command(
                update=update,
                goto="__end__"
            )
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Exception: {e}")
            logger.error(f"Chi tiết lỗi: \n{error_details}")
            raise