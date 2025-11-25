import os
from typing import Optional, Literal, TypedDict
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

class UsageCommand(BaseModel):
    action: Literal["once", "stream", "stop"]
    interval: Optional[float] = None
    count: Optional[int] = None

class State(TypedDict):
    user_input: str
    result: dict

def build_graph():
    def parse(state: State):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY missing")
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)
        tool = llm.with_structured_output(UsageCommand)
        prompt = (
            "You are a controller for system usage streaming. "
            "Return a JSON with fields: action in {once, stream, stop}, "
            "interval in seconds if streaming, and optional count samples. "
            "Examples: 'every 2 minutes' => {action: stream, interval: 120}, "
            "'every 5 seconds for 10 samples' => {action: stream, interval: 5, count: 10}, "
            "'stop' => {action: stop}, 'once' => {action: once}. "
            "Input: "
            + state["user_input"]
        )
        res = tool.invoke(prompt)
        return {"result": res.model_dump()}

    g = StateGraph(State)
    g.add_node("parse", parse)
    g.add_edge("parse", END)
    g.set_entry_point("parse")
    return g.compile()

_graph = None

def run_agent(text: str) -> dict:
    global _graph
    if _graph is None:
        _graph = build_graph()
    out = _graph.invoke({"user_input": text})
    return out["result"]
