# from langgraph.pregel import RetryPolicy
import os
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.graph import fallback_agent
from core.graph.state import AgentState
from core.graph.supervisor import Supervisor
from core.graph.booking_agent import BookingAgent
from core.graph.services_agent import ServiceAgent
from core.graph.fallback_agent import FallbackAgent
from core.graph.modify_booking_agent import ModifyBookingAgent
from state_management.state_cleanup_manager import StateCleanupManager

load_dotenv()

CLEANUP_INTERVAL_MINUTES = os.getenv("CLEANUP_INTERVAL_MINUTES")
STATE_TTL_MINUTES = os.getenv("STATE_TTL_MINUTES")

# retry_policy = RetryPolicy(
#     max_attempts=2,
#     backoff_factor=1,
#     retry_on=(Exception,)
# )

def create_main_graph() -> StateGraph:
    # Khởi tạo các agent
    service_agent = ServiceAgent()
    booking_agent = BookingAgent()
    modify_booking_agent = ModifyBookingAgent()
    supervisor_chain = Supervisor()
    fallback_agent = FallbackAgent()

    # Xây dựng graph
    workflow = StateGraph(AgentState)
    workflow.add_node(
        "supervisor", 
        supervisor_chain.supervisor_node,
        # retry=retry_policy
    )
    workflow.add_node(
        "service_agent", 
        service_agent.services_agent_node,
        # retry=retry_policy
    )
    workflow.add_node(
        "booking_agent", 
        booking_agent.booking_agent_node,
        # retry=retry_policy
    )
    workflow.add_node(
        "modify_booking_agent", 
        modify_booking_agent.modify_booking_agent_node,
        # retry=retry_policy
    )
    workflow.add_node(
        "fallback_agent", 
        fallback_agent.fallback_agent_node,
        # retry=retry_policy
    )

    workflow.set_entry_point("supervisor")
    
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    
    # Khởi tạo cleanup manager
    # cleanup_manager = StateCleanupManager(
    #     graph=graph,
    #     cleanup_interval_minutes=CLEANUP_INTERVAL_MINUTES, # Chạy cleanup mỗi 30 phút
    #     state_ttl_minutes=STATE_TTL_MINUTES # State sống 2 tiếng
    # )
    
    # graph.cleanup_manager = cleanup_manager

    return graph