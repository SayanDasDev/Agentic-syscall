import random

def get_usage():
    return {
        "ru_utime": {
            "tv_sec": random.randint(0, 10),
            "tv_usec": random.randint(0, 999999),
        },
        "ru_stime": {
            "tv_sec": random.randint(0, 5),
            "tv_usec": random.randint(0, 999999),
        },
        "ru_maxrss": random.randint(5000, 50000),
        "ru_minflt": random.randint(10000, 90000),
        "ru_majflt": random.randint(0, 20),
    }

