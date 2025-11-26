import requests
import logging

logger = logging.getLogger("backend_agentic.tools")

def build_machine_url(u: str) -> str:
    s = (u or "").strip()
    if not s:
        return ""
    if s.startswith("http"):
        return s.rstrip("/")
    return ("http://" + s).rstrip("/")

def get_usage(machine_url: str, pid: int, interval: float | int | None = None, samples: int | None = None) -> dict | None:
    base = build_machine_url(machine_url)
    try:
        logger.info("➡️ Calling %s/usage?pid=%s", base, pid)
        r = requests.get(f"{base}/usage", params={"pid": pid}, timeout=10)
        r.raise_for_status()
        usage = r.json()
        logger.info("✅ Usage fetched status=%s", r.status_code)
        return usage
    except Exception:
        logger.warning("⚠️ Usage fetch failed")
        return None

def list_processes(machine_url: str) -> list[dict] | None:
    base = build_machine_url(machine_url)
    try:
        logger.info("➡️ Calling %s/processes", base)
        r = requests.get(f"{base}/processes", timeout=10)
        r.raise_for_status()
        processes = r.json()
        logger.info("✅ Processes fetched status=%s", r.status_code)
        return processes
    except Exception:
        logger.warning("⚠️ Process list fetch failed")
        return None

def stop_agent() -> dict:
    logger.info("🛑 Stop tool invoked")
    return {"stopped": True}
