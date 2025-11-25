from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import contextlib
from .usage import get_usage
from .lang_agent import run_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    async def send_once():
        payload = get_usage()
        payload["ts"] = time.time()
        await ws.send_json(payload)

    async def send_loop(interval: float, count: int | None):
        sent = 0
        while True:
            payload = get_usage()
            payload["ts"] = time.time()
            await ws.send_json(payload)
            sent += 1
            if count is not None and sent >= count:
                break
            await asyncio.sleep(max(0.01, interval))

    task: asyncio.Task | None = None

    await send_once()

    try:
        while True:
            msg = await ws.receive_text()
            try:
                cmd = run_agent(msg)
            except Exception as e:
                await ws.send_json({"error": "agent_failed"})
                continue
            if cmd["action"] == "stop":
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task
                task = None
                continue
            if cmd["action"] == "once":
                await send_once()
                continue
            if cmd["action"] == "stream":
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task
                interval = float(cmd.get("interval", 1.0))
                count = cmd.get("count")
                task = asyncio.create_task(send_loop(interval, count))
    except Exception:
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
