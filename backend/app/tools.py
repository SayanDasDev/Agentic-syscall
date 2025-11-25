"""
This file holds the tools for Agents B and C.
- Agent B (Process Lister): tool_list_processes()
- Agent C (Syscall Monitor): tool_call_syscall()

The complex syscall logic is now abstracted into 'syscall_wrapper.py'.
"""

import subprocess
import os
import sys

# --- Import our new, clean syscall function ---
from app.syscall_wrapper import call_custom_syscall

# ==========================================================
#  TOOL FOR AGENT B (PROCESS LISTER)
# ==========================================================

def tool_list_processes() -> str:
    """
    Runs `ps -u $USER` and returns the raw string output.
    """
    try:
        # Get the current user to run `ps -u $USER`
        user = os.environ.get("USER")
        if not user:
            # Fallback for environments where USER isn't set
            user = os.getlogin() 
            
        result = subprocess.run(
            ['ps', '-u', user], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running 'ps -u {user}':\n{e.stderr}"
    except FileNotFoundError:
        return "Error: 'ps' command not found. Is this a Unix-like system?"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# ==========================================================
#  TOOL FOR AGENT C (SYSCALL MONITOR)
# ==========================================================

def tool_call_syscall(pid: int) -> dict | None:
    """
    This tool is a simple wrapper.
    It calls the complex, abstracted function from the other file.
    
    This keeps our 'tools' file clean and easy to read.
    """
    # Just call the imported function
    return call_custom_syscall(pid)
