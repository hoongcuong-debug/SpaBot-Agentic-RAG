import traceback
from langgraph.types import Command
from core.graph.state import AgentState
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.tools import services_toolbox
from database.connection import specialist_llm 

from log.logger_config import setup_logging

logger = setup_logging(__name__)

class ServiceAgent:
    def __init__(self):
        with open("core/prompts/service_agent_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = """
        Information you receive:
        - Customer's name (customer_name): {name}
        - Services the customer has viewed (seen_products): {seen_services}
        """

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        self.agent = create_react_agent(
            model=specialist_llm,
            tools=services_toolbox,
            prompt=self.prompt,
            state_schema=AgentState
        )

    def services_agent_node(self, state: AgentState) -> Command:
        """
        Xử lý các yêu cầu liên quan đến sản phẩm bằng công cụ `product_toolbox`.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, `seen_products` (nếu có) và kết thúc luồng.
        """
        try:
            result = self.agent.invoke(state)
            content = result["messages"][-1].content
            
            update = {
                "messages": [AIMessage(content=content, name="services_agent_node")],
                "next": "__end__"
            }
            
            if result.get("seen_services", None) is not None:
                    update["seen_services"] = result["seen_services"]
                            
            return Command(
                update=update,
                goto="__end__"
            )
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Exception: {e}")
            logger.error(f"Chi tiết lỗi: \n{error_details}")
            raise