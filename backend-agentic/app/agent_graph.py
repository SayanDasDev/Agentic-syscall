import logging
import os
import json
import requests
from typing import Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from .tools import get_usage, list_processes, stop_agent

logger = logging.getLogger("backend_agentic.graph")

class AgentState(BaseModel):
    query: str
    machines: list[dict]
    result: list | dict | None = None
    tool_name: str | None = None
    tool_args: dict = Field(default_factory=dict)

class GetUsage(BaseModel):
    machine_url: str = Field(..., description="URL")
    pid: int = Field(..., description="PID")
    interval: float | int | None = Field(default=None, description="seconds between samples")
    samples: int | None = Field(default=None, description="number of samples")

class ListProcesses(BaseModel):
    machine_url: str = Field(..., description="URL")
KRUTRIM_API_URL = "https://cloud.olakrutrim.com/v1/chat/completions"
KRUTRIM_MODEL = "Qwen3-Next-80B-A3B-Instruct"

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    return "tools"

def call_model(state: AgentState):
    logger.info("🤖 Agent thinking | query=%s \n machines=%s", state.query, len(state.machines))
    api_key = os.getenv("KRUTRIM_API_KEY")
    logger.info("🔑 Krutrim API key present=%s", "yes" if api_key else "no")
    sys_msg = (
        "ROLE: Tool Router. "
        "TOOLS: GetUsage, ListProcesses, Stop. "
        "SCHEMA: "
        "GetUsage {tool:\"GetUsage\", args:{machine_url:string(one of machines[].url), pid:int, interval?:number, samples?:number}}. "
        "ListProcesses {tool:\"ListProcesses\", args:{machine_url:string(one of machines[].url)}}. "
        "Stop {tool:\"Stop\", args:{}}. "
        "MACHINES: " + json.dumps(state.machines) + ". "
        "RULES: "
        "1) Reply ONLY a JSON object exactly {\"tool\":\"<name>\",\"args\":{...}} with no prose. "
        "2) When a specific process id is requested, choose GetUsage. If no interval/samples provided, omit them. "
        "3) Map machine by name; set machine_url to that machine's url. If no name matches, use the first machine. "
        "4) If the request is to list/show processes or no pid is specified, choose ListProcesses. "
        "5) For stop/cancel/end, choose Stop. "
        "EXAMPLES: "
        "Monitor process id 123 on machine alpha -> {\"tool\":\"GetUsage\",\"args\":{\"machine_url\":\"http://127.0.0.1:8001\",\"pid\":123}} "
        "Monitor id 123 every 2s for 3 samples -> {\"tool\":\"GetUsage\",\"args\":{\"machine_url\":\"http://127.0.0.1:8001\",\"pid\":123,\"interval\":2,\"samples\":3}} "
        "list processes on beta -> {\"tool\":\"ListProcesses\",\"args\":{\"machine_url\":\"http://127.0.0.1:8001\"}} "
        "stop -> {\"tool\":\"Stop\",\"args\":{}}"
    )
    payload = {
        "model": KRUTRIM_MODEL,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": state.query},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }
    headers = {
        "Authorization": f"Bearer {api_key}" if api_key else "",
        "Content-Type": "application/json",
    }
    try:
        logger.info("🤖 Calling Krutrim model=%s", KRUTRIM_MODEL)
        r = requests.post(KRUTRIM_API_URL, headers=headers, json=payload, timeout=12)
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        logger.info("🤖 Krutrim status=%s", r.status_code)
        logger.info("🤖 Krutrim raw content=%s", (content[:1000] + ("..." if len(content) > 1000 else "")))
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {}
            if "```" in content:
                fence_start = content.find("```")
                fence_end = content.find("```", fence_start + 3)
                snippet = content[fence_start + 3:fence_end] if fence_end != -1 else content[fence_start + 3:]
                brace_start = snippet.find("{")
                brace_end = snippet.rfind("}")
                if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                    try:
                        parsed = json.loads(snippet[brace_start:brace_end+1])
                    except Exception:
                        parsed = {}
            if not parsed:
                brace_start = content.find("{")
                brace_end = content.rfind("}")
                if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                    try:
                        parsed = json.loads(content[brace_start:brace_end+1])
                    except Exception:
                        parsed = {}
        tool_name = parsed.get("tool")
        tool_args = parsed.get("args", {})
        logger.info("🤖 Agent Infers: tool=%s args=%s", tool_name, tool_args)
        if tool_name:
            return {"tool_name": tool_name, "tool_args": tool_args}
        else:
            logger.warning("⚠️ Krutrim call failed")
            return {"tool_name": None, "tool_args": {}}
    except Exception:
        logger.warning("⚠️ Krutrim call failed")
        return {"tool_name": None, "tool_args": {}}

def call_tool(state: AgentState):
    tool_name = state.tool_name
    tool_args = state.tool_args or {}
    if not tool_name:
        return {"result": {"error": "no_tool"}}
    logger.info("🤖 Agent decided to use tool: %s with args: %s", tool_name, tool_args)
    if tool_name == "GetUsage":
        result = get_usage(**tool_args)
    elif tool_name == "ListProcesses":
        result = list_processes(**tool_args)
    elif tool_name == "Stop":
        result = stop_agent()
    else:
        result = {"error": f"unknown_tool:{tool_name}"}
    return {"result": result}


workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", call_tool)
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
)
workflow.add_edge("tools", END)

graph = workflow.compile()
