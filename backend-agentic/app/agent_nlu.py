"""
This file holds the logic for Agent A (NLU).
It has been UPDATED to understand multiple PIDs.
"""

import requests
import os
import sys
import json
import re
from dotenv import load_dotenv
import logging

logger = logging.getLogger("backend_agentic.nlu")

# --- Krutrim API Configuration ---

# 1. Get your API key from an environment variable
#    (Never hardcode keys in your code)
#    In your terminal, run:
#    export KRUTRIM_API_KEY='your_secret_key_here'
load_dotenv()

KRUTRIM_API_KEY = os.getenv("KRUTRIM_API_KEY")
KRUTRIM_API_URL = 'https://cloud.olakrutrim.com/v1/chat/completions'
KRUTRIM_MODEL = 'Qwen3-Next-80B-A3B-Instruct'

# --- UPDATED SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are an NLU agent. Given a free-form request and a list of machines
(each with a name and url), output a single-line JSON with keys:
machine_name, machine_url, pid, interval.
Rules:
- machine_name must exactly match one entry from the provided machines list.
- machine_url must be the corresponding url from the same machines list.
- pid must be an integer extracted from the request.
- interval is the sampling interval in seconds; default to 1.0 if missing.
- Do not explain; only output JSON.
Example:
Request: "give me usage stats of process id 123 every 3 seconds of machine X"
Machines: [{"name":"machine X","url":"localhost:8001"}]
Output: {"machine_name":"machine X","machine_url":"localhost:8001","pid":123,"interval":3}
"""

def parse_command_krutrim(user_input: str) -> dict:
    """
    Agent A (NLU): Parses the user's command by calling the
    Krutrim LLM API.
    """
    print(f"\n[Agent A] Contacting Krutrim NLU for: '{user_input}'")

    if not KRUTRIM_API_KEY:
        print("Error: KRUTRIM_API_KEY environment variable not set.", file=sys.stderr)
        return {"intent": "error", "message": "KRUTRIM_API_KEY not set on server."}

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {KRUTRIM_API_KEY}'
    }
    
    payload = {
        'model': KRUTRIM_MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_input}
        ],
        'stream': False # We want a single JSON response
    }

    try:
        response = requests.post(KRUTRIM_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status() 
        
        response_data = response.json()
        llm_output_string = response_data['choices'][0]['message']['content']
        
        try:
            parsed_json = json.loads(llm_output_string)
            if 'intent' not in parsed_json:
                 raise ValueError("LLM response missing 'intent' key")
            
            print(f"[Agent A] Krutrim NLU parsed: {parsed_json}")
            return parsed_json
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Agent A Error] Krutrim returned invalid JSON: {llm_output_string} ({e})")
            # --- MOCK FALLBACK (in case Krutrim fails) ---
            print("[Agent A] Warning: NLU failed, using local mock.")
            return parse_command_mock(user_input)

    except requests.exceptions.HTTPError as e:
        print(f"[Agent A Error] HTTP Error from API: {e.response.status_code} {e.response.text}")
        return {"intent": "error", "message": f"Krutrim API error (HTTP {e.response.status_code})"}
    except requests.exceptions.RequestException as e:
        print(f"[Agent A Error] API call failed: {e}")
        return {"intent": "error", "message": f"Krutrim API connection error: {e}"}

def parse_command_mock(user_input: str) -> dict:
    """A simple mock parser in case the API fails."""
    lowered = user_input.lower()
    
    if "list" in lowered or "ps -u" in lowered:
        return {"intent": "list_processes"}
    
    if "stop" in lowered or "clear" in lowered:
        return {"intent": "stop_monitoring"}
        
    if "monitor" in lowered or any(char.isdigit() for char in lowered):
        pids = [int(p) for p in re.findall(r'\b\d+\b', user_input) if len(p) > 2]
        interval = 1.0
        m = re.search(r'every\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|s)\b', lowered)
        if m:
            try:
                interval = float(m.group(1))
            except ValueError:
                pass
        else:
            m = re.search(r'every\s+(\d+(?:\.\d+)?)\s*(minutes?|mins?|m)\b', lowered)
            if m:
                try:
                    interval = float(m.group(1)) * 60.0
                except ValueError:
                    pass
        if pids:
            return {"intent": "monitor_pids", "pids": pids, "interval": interval}

    return {"intent": "unknown", "message": "I didn't understand. Try 'list processes' or 'monitor <pid>'."}

def parse_agentic_selection(user_input: str, machines: list[dict]) -> dict:
    logger.info("🤖 Agent thinking | query=%s machines=%s", user_input, len(machines))
    if not KRUTRIM_API_KEY:
        return parse_agentic_mock(user_input, machines)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {KRUTRIM_API_KEY}'
    }
    machines_str = json.dumps(machines, ensure_ascii=False)
    payload = {
        'model': KRUTRIM_MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f"Machines: {machines_str}\nRequest: {user_input}"}
        ],
        'stream': False
    }
    try:
        response = requests.post(KRUTRIM_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        out = data['choices'][0]['message']['content']
        parsed = json.loads(out)
        if not isinstance(parsed.get('pid'), int):
            raise ValueError('pid missing')
        if 'interval' not in parsed:
            parsed['interval'] = 1.0
        mname = parsed.get('machine_name')
        murl = parsed.get('machine_url')
        if not mname or not murl:
            table = {str(x.get('name','')): str(x.get('url','')) for x in machines}
            if not mname and table:
                mname = list(table.keys())[0]
            if not murl and mname in table:
                murl = table[mname]
            parsed['machine_name'] = mname
            parsed['machine_url'] = murl
        logger.info("🤖 Agent Infers: name=%s url=%s pid=%s interval=%s", parsed.get('machine_name'), parsed.get('machine_url'), parsed.get('pid'), parsed.get('interval'))
        return parsed
    except Exception:
        logger.warning("⚠️ Agent NLU error; using mock")
        return parse_agentic_mock(user_input, machines)

def parse_agentic_mock(user_input: str, machines: list[dict]) -> dict:
    lowered = user_input.lower()
    pids = [int(p) for p in re.findall(r'\b\d+\b', user_input)]
    pid = pids[0] if pids else 0
    m = re.search(r'every\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|s)\b', lowered)
    interval = 1.0
    if m:
        try:
            interval = float(m.group(1))
        except ValueError:
            interval = 1.0
    else:
        m2 = re.search(r'every\s+(\d+(?:\.\d+)?)\s*(minutes?|mins?|m)\b', lowered)
        if m2:
            try:
                interval = float(m2.group(1)) * 60.0
            except ValueError:
                interval = 60.0
    machine_names = [str(x.get('name','')) for x in machines]
    name_to_url = {str(x.get('name','')): str(x.get('url','')) for x in machines}
    chosen = machine_names[0] if machine_names else ''
    for name in machine_names:
        if name and name.lower() in lowered:
            chosen = name
            break
    url = name_to_url.get(chosen, '')
    result = {"machine_name": chosen, "machine_url": url, "pid": pid, "interval": interval}
    logger.info("🤖 Agent Mock Infers: name=%s url=%s pid=%s interval=%s", chosen, url, pid, interval)
    return result
