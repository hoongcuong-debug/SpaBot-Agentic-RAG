import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from core.graph.build_graph import create_main_graph

from api.chatbot.v4.routes import router as api_router_v4
from api.chatbot.v5.routes import router as api_chatbot_router_v5

from api.admin.v1.routes import router as api_admin_router_v1

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     graph = create_main_graph()
#     app.state.graph = graph
    
#     # Start cleanup task
#     graph.cleanup_manager.start_cleanup_task()
    
#     yield
    
#     # Shutdown
#     graph.cleanup_manager.stop_cleanup_task()

# Create a FastAPI app instance
app = FastAPI(
    title="Chatbot customer service project", 
    # lifespan=lifespan
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Include the API router with a prefix

app.include_router(api_router_v4, prefix="/api/chatbot/v4") # -> web
app.include_router(api_chatbot_router_v5, prefix="/api/chatbot/v5") # -> add tracing

app.include_router(api_admin_router_v1, prefix="/api/admin/v1")

# Define a root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to selling bot"}

@app.get("/health")
async def health():
    """
    Endpoint kiểm tra tình trạng dịch vụ.

    Returns:
        dict: Trạng thái "healthy" nếu ứng dụng sẵn sàng.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    # This will only run if you execute the file directly
    # Not when using langgraph dev
    uvicorn.run(app, host="127.0.0.1", port=8080)
