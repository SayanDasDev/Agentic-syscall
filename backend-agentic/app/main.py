from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import logging
import json
import requests
from .agent_nlu import parse_agentic_selection

app = FastAPI()

logger = logging.getLogger("backend_agentic")
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

@app.get("/")
def root():
    return {"status": "ok"}

def build_machine_url(u: str) -> str:
    return u if u.startswith("http") else f"http://{u}"

@app.post("/agent/query")
def agent_query(payload: dict = Body(...)):
    query = str(payload.get("query", ""))
    machines = payload.get("machines", [])
    sel = parse_agentic_selection(query, machines)
    base = build_machine_url(str(sel.get("machine_url", "")))
    if not base:
        return {"error": "machine_url_missing", "selection": sel}
    pid = int(sel.get("pid", 0))
    try:
        r = requests.get(f"{base}/usage", params={"pid": pid}, timeout=10)
        r.raise_for_status()
        usage = r.json()
    except Exception:
        usage = None
    return {"selection": sel, "usage": usage}

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
                await ws.send_json({"type": "stopped"})
                continue
            query = str(payload.get("query", ""))
            machines = payload.get("machines", [])
            sel = parse_agentic_selection(query, machines)
            base = build_machine_url(str(sel.get("machine_url", "")))
            if not base:
                await ws.send_json({"error": "machine_url_missing", "selection": sel})
                continue
            pid = int(sel.get("pid", 0))
            interval = float(sel.get("interval", 1.0))
            async def loop():
                while True:
                    try:
                        r = requests.get(f"{base}/usage", params={"pid": pid}, timeout=10)
                        usage = r.json() if r.status_code == 200 else None
                    except Exception:
                        usage = None
                    await ws.send_json({"ts": time.time(), "type": "usage", "selection": sel, "data": usage})
                    await asyncio.sleep(interval)
            if task and not task.done():
                task.cancel()
            if interval and interval > 0:
                task = asyncio.create_task(loop())
            else:
                try:
                    r = requests.get(f"{base}/usage", params={"pid": pid}, timeout=10)
                    usage = r.json() if r.status_code == 200 else None
                except Exception:
                    usage = None
                await ws.send_json({"ts": time.time(), "type": "usage", "selection": sel, "data": usage})
    except WebSocketDisconnect:
        if task and not task.done():
            task.cancel()
        return
