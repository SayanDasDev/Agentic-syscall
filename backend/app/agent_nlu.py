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
You are an expert NLU (Natural Language Understanding) agent for a Streamlit app.
Your sole purpose is to convert a user's command into a single-line JSON object.
You do not chat. You do not explain. You ONLY output the JSON.

Here are the possible intents:

1.  **List User Processes:**
    -   Triggers: "list my processes", "show me what's running", "ps -u", "show the process list"
    -   JSON: {"intent": "list_processes"}

2.  **Monitor PIDs (Multiple):**
    -   Triggers: "monitor PID 12345", "watch 999 888 777", "update on 12345 and 45678 every 0.5s"
    -   JSON: {"intent": "monitor_pids", "pids": [<pid1>, <pid2>, ...], "interval": <number_in_seconds>}
    -   You MUST extract all PIDs.
    -   Default 'interval' is 1.0 if not specified.

3.  **Stop Monitoring:**
    -   Triggers: "stop monitoring", "clear", "stop", "halt"
    -   JSON: {"intent": "stop_monitoring"}

4.  **Unknown/Error:**
    -   Triggers: Any command that doesn't fit.
    -   JSON: {"intent": "unknown", "message": "I didn't understand. Try 'list processes' or 'monitor <pid1> <pid2> ...'"}
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
