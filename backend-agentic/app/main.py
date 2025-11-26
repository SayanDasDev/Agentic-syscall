from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import logging
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from dotenv import load_dotenv

app = FastAPI()

logger = logging.getLogger("backend_agentic")
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

# Load environment variables early
def _load_env():
    try:
        base = Path(__file__).resolve().parents[2]
        local = Path(__file__).resolve().parents[1]
        p1 = base / ".env"
        p2 = local / ".env"
        if p1.exists():
            load_dotenv(str(p1))
        if p2.exists():
            load_dotenv(str(p2))
    except Exception:
        pass

_load_env()
logger.info("🔑 KRUTRIM_API_KEY present=%s", "yes" if os.getenv("KRUTRIM_API_KEY") else "no")

from .agent_graph import graph, call_model, AgentState
from .tools import get_usage, list_processes

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/agent/query")
def agent_query(payload: dict = Body(...)):
    query = str(payload.get("query", ""))
    machines = payload.get("machines", [])
    inputs = {"query": query, "machines": machines}
    result = graph.invoke(inputs)
    return {"result": result.get("result")}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    task = None
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except Exception:
                await ws.send_json({"error": "invalid_payload"})
                continue
            if isinstance(payload, dict) and payload.get("type") == "stop":
                if task and not task.done():
                    task.cancel()
                task = None
                logger.info("🛑 Agent stopped")
                await ws.send_json({"type": "stopped"})
                continue
            query = str(payload.get("query", ""))
            machines = payload.get("machines", [])
            state = AgentState(query=query, machines=machines)
            decision = call_model(state)
            tool = decision.get("tool_name")
            args = decision.get("tool_args", {})
            if tool == "GetUsage":
                base_url = str(args.get("machine_url", ""))
                pid = int(args.get("pid", 0))
                interval = float(args.get("interval", 0)) if args.get("interval") is not None else 0.0
                samples = int(args.get("samples", 1)) if args.get("samples") is not None else 1
                async def loop_samples():
                    count = 0
                    while True:
                        try:
                            usage = get_usage(base_url, pid)
                        except Exception:
                            usage = None
                        await ws.send_json({"ts": time.time(), "type": "usage", "data": usage})
                        count += 1
                        if samples and count >= samples:
                            break
                        await asyncio.sleep(interval if interval and interval > 0 else 0)
                if task and not task.done():
                    task.cancel()
                task = asyncio.create_task(loop_samples())
            elif tool == "ListProcesses":
                base_url = str(args.get("machine_url", ""))
                procs = list_processes(base_url)
                await ws.send_json({"ts": time.time(), "type": "processes", "data": procs})
            elif tool == "Stop":
                if task and not task.done():
                    task.cancel()
                task = None
                await ws.send_json({"type": "stopped"})
            else:
                await ws.send_json({"error": "no_tool", "args": args})
    except WebSocketDisconnect:
        if task and not task.done():
            task.cancel()
        return
