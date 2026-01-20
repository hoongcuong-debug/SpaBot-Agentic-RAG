import os
import traceback
from dotenv import load_dotenv

from fastapi import APIRouter, HTTPException

from schemas.resquest import WebhookChatRequest, NormalChatRequest
from schemas.response import ChatResponse
from services.utils import now_vietnam_time
from core.graph.build_graph import create_main_graph
from services.v5.process_chat import handle_webhook_request, handle_invoke_request

from log.logger_config import setup_logging

load_dotenv()
logger = setup_logging(__name__)

N_DAYS = int(os.getenv("N_DAYS"))

router = APIRouter()
graph = create_main_graph()

@router.post("/chat/invoke", response_model=ChatResponse)
async def chat(request: NormalChatRequest) -> ChatResponse | HTTPException:
    chat_id = request.chat_id
    user_input = request.user_input
    
    timestamp_start = now_vietnam_time()
    logger.info(f"Received request at {timestamp_start.isoformat()}")
    
    try:    
        response = await handle_invoke_request(
            chat_id=chat_id,
            user_input=user_input,
            graph=graph,
            timestamp_start=timestamp_start
        )
        
        return response
            
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Error: {str(e)}"
        )
        
@router.post("/chat/webhook", response_model=ChatResponse)
async def chat(request: WebhookChatRequest):
    chat_id = request.chat_id
    user_input = request.user_input
    message_spans = request.message_spans
    
    timestamp_start = now_vietnam_time()
    logger.info(f"Received request at {timestamp_start.isoformat()}")
    
    try:    
        response = await handle_webhook_request(
            chat_id=chat_id,
            user_input=user_input,
            graph=graph,
            timestamp_start=timestamp_start,
            message_spans=message_spans
        )
        
        return response
            
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Exception: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Error: {str(e)}"
        )