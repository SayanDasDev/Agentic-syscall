import random
import psutil

def call_custom_syscall(pid: int) -> dict | None:
    process_name = "N/A"
    try:
        p = psutil.Process(pid)
        process_name = p.name()
    except Exception:
        pass

    user_time = round(random.uniform(0.0, 10.0), 6)
    sys_time = round(random.uniform(0.0, 5.0), 6)
    max_rss_kb = random.randint(5000, 50000)
    minor_page_faults = random.randint(10000, 90000)
    major_page_faults = random.randint(0, 20)

    return {
        "pid": pid,
        "process_name": process_name,
        "user_time": user_time,
        "sys_time": sys_time,
        "max_rss_kb": max_rss_kb,
        "minor_page_faults": minor_page_faults,
        "major_page_faults": major_page_faults,
    }
