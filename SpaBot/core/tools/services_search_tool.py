import traceback
from shutil import ExecError
from pydantic import BaseModel, Field
from typing import Annotated, Optional, List

from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

from core.utils.function import build_update
from repository.sync_repo import ServiceRepo
from core.graph.state import AgentState, Services
from database.connection import supabase_client, embeddings_model

from log.logger_config import setup_logging

logger = setup_logging(__name__)

service_repo = ServiceRepo(supabase_client=supabase_client)

def _get_services_and_discount_by_embedding(
    query_embedding: list[float],
    match_count: int = 5
) -> list[dict] | None:

    rag_results = service_repo.get_services_by_embedding(
        query_embedding=query_embedding,
        match_count=match_count
    )
    
    if not rag_results:
        logger.error("Error calling RPC match_services")
        raise ExecError("Error calling RPC match_services")
    
    service_id_list = [item.get("service_id") for item in rag_results]
    data = service_repo.get_services_by_ids(service_id_list=service_id_list)
    
    return data

def _get_qna_by_embedding(
    query_embedding: list[float],
    match_count: int = 5
) -> list[dict] | None:

    rag_results = service_repo.get_qna_by_embedding(
        query_embedding=query_embedding,
        match_count=match_count
    )
    
    if not rag_results:
        logger.error("Error calling RPC match_qna")
        raise ExecError("Error calling RPC match_qna")
    
    qna_id_list = [item.get("qna_id") for item in rag_results]
    data = service_repo.get_qna_by_ids(qna_id_list=qna_id_list)
    
    return data

def _update_seen_services(
    seen_services: dict, 
    services: List[dict]
) -> dict:
    """
    Updates `seen_services` in the state with the returned service results.

    Args:
        seen_services (dict): The existing set of seen services.
        services (List[dict]): The list of services from SQL/RAG.

    Returns:
        dict: The `seen_services` set after being updated/overwritten by `service_id`.
    """
    for service in services:
        service_id = service.get("id")
        
        price = service["price"]
        discount_value = service["service_discounts"][0]["discount_value"]
        price_after_discount = price * (1 - discount_value / 100) if discount_value else price
        
        seen_services[service_id] = Services(
            service_id=service_id,
            service_type=service["type"],
            service_name=service["name"],
            duration_minutes=service["duration_minutes"],
            price=price,
            discount_value=discount_value,
            price_after_discount=price_after_discount
        )
    return seen_services

@tool
def get_services_tool(
    keyword: Annotated[str, "Only accept Vietnamese - The keyword provided by the customer that refers to a specific service"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Use this tool when the customer is asking about a **specific service**.

    - If the customer provides the exact full service name, the tool will perform an exact SQL search.  
    - If the customer only provides partial information (e.g., general description), the tool will use semantic search (RAG) to find the closest matching services.

    Purpose: Retrieve detailed information about one or more spa services, such as description, duration, and price.  

    Parameters:
        - keyword (str): Only accept Vietnamese - The essential keyword (name, or core description) of the service the customer is asking about.
    """
    
    logger.info(f"get_services_tool called with keyword: {keyword}")
    # --- SQL First Approach ---
    try:
        db_result = service_repo.get_service_by_keyword(
            keyword=keyword
        )
     
        # logger.info(f"SQL data returned: {db_result}")

        if db_result:
            logger.info("Data returned from SQL")
            
            updated_seen_services = _update_seen_services(
                seen_services=state["seen_services"] if state["seen_services"] is not None else {},
                services=db_result
            )
            
            formatted_response = (
                "Here are the services found based on the customer's request:\n"
                f"{db_result}\n"
            )
            
            logger.info("Returning results from SQL")
            return Command(
                update=build_update(
                    content=formatted_response,
                    tool_call_id=tool_call_id,
                    seen_services=updated_seen_services
                )
            )
            
        logger.info("No results from SQL, switching to RAG search")
        
        query_embedding = embeddings_model.embed_query(state["user_input"])
        
        services = _get_services_and_discount_by_embedding(
            query_embedding=query_embedding,
            match_count=5
        )
        
        # logger.info(f"RAG results: {services}")
        
        if not services:
            logger.info("No results from RAG")
            return Command(update=build_update(
                content="Apologies to the customer, couldn't find the service you're looking for.",
                tool_call_id=tool_call_id
            ))

        logger.info("Results returned from RAG")

        updated_seen_services = _update_seen_services(
            seen_services=state["seen_services"] if state["seen_services"] is not None else {},
            services=services
        )
        
        formatted_response = (
            "Here are the services returned based on the customer's request:\n\n"
            f"{services}\n"
        )
        
        logger.info("Returning results from RAG")
        return Command(
            update=build_update(
                content=formatted_response,
                tool_call_id=tool_call_id,
                seen_services=updated_seen_services
            )
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise

@tool
def get_qna_tool(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Use this tool when the customer is asking about **general information related to the spa**.

    - This tool will search the Frequently Asked Questions (FAQ) database to provide detailed answers and guidance.
    - It is suitable for questions about booking procedures, opening hours, available services, or other general inquiries about the spa.

    Purpose: Retrieve detailed information or instructions related to the customer's common questions about the spa.
    """
    query = state["user_input"]
    logger.info(f"get_qna_tool called with query: {query}")
    
    try:
        query_embedding = embeddings_model.embed_query(query)
        
        qnas = _get_qna_by_embedding(
            query_embedding=query_embedding,
            match_count=3
        )

        if not qnas:
            logger.error("No Q&A documents found from RAG")
            return Command(
                update=build_update(
                    content="Sorry customer, an error occurred while searching for instructions.",
                    tool_call_id=tool_call_id
                )
            ) 
        
        # logger.info(f"qna: {qnas}")
        
        logger.info(f"Found {len(qnas)} Q&A documents")
        return Command(
            update=build_update(
                content=(
                    "Here is the information found related to the customer's question: \n"
                    f"{qnas}"
                ),
                tool_call_id=tool_call_id
            )
        )
             
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        raise
