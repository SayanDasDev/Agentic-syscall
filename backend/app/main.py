from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import contextlib
import logging
import os
from .syscall_wrapper import call_custom_syscall
from .agent_graph import app as agent_app

app = FastAPI()

logger = logging.getLogger("backend.app")
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

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("ws accepted")

    async def send_once(pids: list[int] | None = None):
        now = time.time()
        if not pids:
            data = {"ts": now, "type": "usage", "data": call_custom_syscall(os.getpid())}
            await ws.send_json(data)
        else:
            batch = {pid: call_custom_syscall(pid) for pid in pids}
            await ws.send_json({"ts": now, "type": "batch", "data": batch})
        logger.info("sent once sample")

    async def send_loop(pids: list[int], interval: float):
        sent = 0
        try:
            while True:
                now = time.time()
                batch = {pid: call_custom_syscall(pid) for pid in pids}
                try:
                    await ws.send_json({"ts": now, "type": "batch", "data": batch})
                except Exception:
                    logger.info("ws send failed; stopping stream")
                    break
                logger.info("stream tick interval=%s sent=%s", interval, sent + 1)
                sent += 1
                await asyncio.sleep(max(0.01, interval))
        except asyncio.CancelledError:
            logger.info("stream task cancelled")
            return

    task: asyncio.Task | None = None

    try:
        while True:
            msg = await ws.receive_text()
            logger.info("ws message received: %s", msg)
            try:
                plan = agent_app.invoke({"command": msg})["result"]
                logger.info("agent plan: %s", plan)
            except Exception:
                logger.exception("agent plan failure")
                await ws.send_json({"error": "agent_failed"})
                continue
            t = plan.get("type")
            if t == "stop":
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task
                task = None
                logger.info("stream stopped via command")
                continue
            if t == "list":
                await ws.send_json({"type": "list", "data": plan.get("data", "")})
                continue
            if t == "monitor":
                pids = plan.get("pids", [])
                interval = float(plan.get("interval", 1.0))
                if not pids:
                    await ws.send_json({"error": "no_pids"})
                    continue
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task
                logger.info("stream starting interval=%s pids=%s", interval, pids)
                task = asyncio.create_task(send_loop(pids, interval))
                continue
            if t == "error":
                await ws.send_json({"error": plan.get("message", "unknown")})
                continue
    except WebSocketDisconnect:
        logger.info("ws disconnected")
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        return
    except Exception:
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        logger.exception("ws handler exception")
