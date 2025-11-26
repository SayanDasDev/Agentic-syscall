import ctypes
import ctypes.util
import errno
import os
import sys
import psutil

# --- Part 1: Define the C structures from your syscall ---
class CTimeval(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long),
                ("tv_usec", ctypes.c_long)]

class CRusage(ctypes.Structure):
    _fields_ = [("ru_utime", CTimeval),
                ("ru_stime", CTimeval),
                ("ru_maxrss", ctypes.c_long),
                ("ru_ixrss", ctypes.c_long),
                ("ru_idrss", ctypes.c_long),
                ("ru_isrss", ctypes.c_long),
                ("ru_minflt", ctypes.c_long),
                ("ru_majflt", ctypes.c_long),
                ("ru_nswap", ctypes.c_long),
                ("ru_inblock", ctypes.c_long),
                ("ru_oublock", ctypes.c_long),
                ("ru_msgsnd", ctypes.c_long),
                ("ru_msgrcv", ctypes.c_long),
                ("ru_nsignals", ctypes.c_long),
                ("ru_nvcsw", ctypes.c_long),
                ("ru_nivcsw", ctypes.c_long)
               ]

# --- Part 2: Load libc and find the syscall function ---
NR_GET_PROC_SUBTREE_RUSAGE = 472 # Your syscall number
syscall = None
try:
    libc_path = ctypes.util.find_library("c")
    if not libc_path:
        print("Error: Could not find C library (libc)", file=sys.stderr)
    else:
        libc = ctypes.CDLL(libc_path, use_errno=True)
        syscall = libc.syscall
        # long syscall(long syscall_num, int pid, int flags, struct rusage *usage_ptr)
        syscall.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(CRusage)]
        syscall.restype = ctypes.c_long
except Exception as e:
    print(f"Error loading libc or syscall: {e}", file=sys.stderr)
    syscall = None

# --- Part 3: The "tool" function our app will call ---

def call_custom_syscall(pid: int) -> dict | None:
    """
    This function calls your REAL custom 'get_proc_subtree_rusage' syscall
    and returns a rich dictionary with all the resource fields.
    """
    
    if not syscall:
        print("Fatal: syscall function is not loaded. Cannot get usage.", file=sys.stderr)
        return {"error": "Syscall function not loaded."}

    process_name = "N/A"
    try:
        # We use psutil just to get the friendly name
        p = psutil.Process(pid)
        process_name = p.name()
    except psutil.NoSuchProcess:
        # Process is dead, but we can still get stats
        pass 
    except Exception:
        pass # Other errors (e.g., permissions)

    # 1. Create an empty C-style rusage struct
    usage = CRusage()
    
    # 2. We must set errno to 0 before the call
    ctypes.set_errno(0)
    
    # 3. Call the syscall
    ret = syscall(NR_GET_PROC_SUBTREE_RUSAGE, pid, 0, ctypes.byref(usage))

    # 4. Check for errors
    if ret < 0:
        e = ctypes.get_errno()
        error_message = os.strerror(e)
        print(f"syscall(...) failed for PID {pid}: {error_message}", file=sys.stderr)
        return {"error": error_message, "pid": pid}

    # 5. Success! Convert C data to Python types.
    user_time = usage.ru_utime.tv_sec + (usage.ru_utime.tv_usec / 1_000_000.0)
    sys_time = usage.ru_stime.tv_sec + (usage.ru_stime.tv_usec / 1_000_000.0)
    
    # 6. Return the full dictionary
    return {
        "pid": pid,
        "process_name": process_name,
        "user_time": user_time,
        "sys_time": sys_time,
        "max_rss_kb": usage.ru_maxrss,
        "minor_page_faults": usage.ru_minflt,
        "major_page_faults": usage.ru_majflt
    }


def list_processes() -> list[dict]:
    procs = []
    for p in psutil.process_iter(['pid', 'name']):
        procs.append(p.info)
    return procs
