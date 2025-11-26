"""
This is the NEW "Agentic Brain" file.
It uses LangGraph to define the NLU and routing logic.
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any

# Import your agent and tools
from app.agent_nlu import parse_command_krutrim
from app.tools import tool_list_processes

# ==========================================================
#  AGENT STATE
# ==========================================================

class AgentState(TypedDict):
    # The initial command from the user
    command: str
    
    # The parsed command from the NLU
    parsed_command: Dict
    
    # The final result to pass back to Streamlit
    # This will be our "plan"
    result: Dict[str, Any]

# ==========================================================
#  LANGGRAPH NODES
# ==========================================================

def node_nlu_parser(state: AgentState):
    """
    Node for Agent A (NLU): Parses the user's command.
    """
    command = state['command']
    parsed = parse_command_krutrim(command)
    return {"parsed_command": parsed}

def node_tool_list_processes(state: AgentState):
    """
    Node for Agent B: Calls the `ps -u` tool.
    """
    process_list_str = tool_list_processes()
    result = {
        "type": "list",
        "data": process_list_str
    }
    return {"result": result}

def node_plan_monitor(state: AgentState):
    """
    This node doesn't run a tool. It just creates the "plan"
    for the Streamlit UI to execute.
    """
    pids = state['parsed_command'].get('pids', [])
    interval = state['parsed_command'].get('interval', 1.0)
    result = {
        "type": "monitor",
        "pids": pids,
        "interval": interval
    }
    return {"result": result}

def node_plan_stop(state: AgentState):
    """
    This node creates the "stop" plan.
    """
    return {"result": {"type": "stop"}}

def node_handle_unknown(state: AgentState):
    """
    This node handles NLU failures.
    """
    message = state['parsed_command'].get('message', "I don't understand.")
    return {"result": {"type": "error", "message": message}}

# ==========================================================
#  LANGGRAPH ROUTER
# ==========================================================

def router(state: AgentState):
    """
    Reads the NLU's intent and routes to the correct node.
    """
    intent = state['parsed_command'].get('intent')
    print(f"[LangGraph Router] Got intent: '{intent}'. Routing...")
    
    if intent == "list_processes":
        return "list_processes_tool"
    elif intent == "monitor_pids":
        return "monitor_plan"
    elif intent == "stop_monitoring":
        return "stop_plan"
    else:
        return "unknown"

# ==========================================================
#  BUILD AND COMPILE THE GRAPH
# ==========================================================

def build_graph():
    """Builds and compiles the LangGraph."""
    
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("nlu_parser", node_nlu_parser)
    workflow.add_node("list_processes_tool", node_tool_list_processes)
    workflow.add_node("monitor_plan", node_plan_monitor)
    workflow.add_node("stop_plan", node_plan_stop)
    workflow.add_node("unknown", node_handle_unknown)

    # Set the entrypoint
    workflow.set_entry_point("nlu_parser")

    # Add the conditional router
    workflow.add_conditional_edges(
        "nlu_parser",
        router,
        {
            "list_processes_tool": "list_processes_tool",
            "monitor_plan": "monitor_plan",
            "stop_plan": "stop_plan",
            "unknown": "unknown"
        }
    )

    # All tool/plan nodes go to the end
    workflow.add_edge("list_processes_tool", END)
    workflow.add_edge("monitor_plan", END)
    workflow.add_edge("stop_plan", END)
    workflow.add_edge("unknown", END)

    # Compile the graph
    return workflow.compile()

# --- Build the app and export it for main.py to use ---
app = build_graph()
