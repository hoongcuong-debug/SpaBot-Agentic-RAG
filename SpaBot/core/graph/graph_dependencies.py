from fastapi import Request
from langgraph.graph import StateGraph

def get_graph(request: Request) -> StateGraph:
    return request.app.state.graph