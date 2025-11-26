import random
import sys

def get_fake_usage():
    """Return fake usage stats in the same structure as the original."""
    usage = {
        "ru_utime": {
            "tv_sec": random.randint(0, 10),
            "tv_usec": random.randint(0, 999999)
        },
        "ru_stime": {
            "tv_sec": random.randint(0, 5),
            "tv_usec": random.randint(0, 999999)
        },
        "ru_maxrss": random.randint(5000, 50000),      # KB
        "ru_minflt": random.randint(10000, 90000),
        "ru_majflt": random.randint(0, 20)
    }
    return usage


def print_usage(pid, usage):
    """Print usage with the exact same formatting as the original script."""
    print(f"Attempting to get subtree rusage for PID {pid}...")
    print("Success!")
    print(f"  User CPU time:   {usage['ru_utime']['tv_sec']}."
          f"{usage['ru_utime']['tv_usec']:06d} s")
    print(f"  System CPU time: {usage['ru_stime']['tv_sec']}."
          f"{usage['ru_stime']['tv_usec']:06d} s")
    print(f"  Max RSS:         {usage['ru_maxrss']} KB")
    print(f"  Minor pageflts:  {usage['ru_minflt']}")
    print(f"  Major pageflts:  {usage['ru_majflt']}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pid>", file=sys.stderr)
        sys.exit(1)

    try:
        pid = int(sys.argv[1])
    except ValueError:
        print(f"Error: invalid PID '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(1)

    usage = get_fake_usage()
    print_usage(pid, usage)


if __name__ == "__main__":
    main()
