import argparse
import subprocess
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a command with bounded retry attempts.")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")
    args = parser.parse_args()

    command = [c for c in args.cmd if c]
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("missing command")

    attempts = max(1, int(args.max_attempts))
    for i in range(1, attempts + 1):
        print(f"[bounded-retry] attempt={i}/{attempts} cmd={' '.join(command)}")
        completed = subprocess.run(command, check=False)
        if completed.returncode == 0:
            print("[bounded-retry] success")
            return
        if i < attempts:
            time.sleep(max(0.0, float(args.sleep_seconds)))

    print("[bounded-retry] failed after max attempts; hand over to manual takeover path")
    sys.exit(1)


if __name__ == "__main__":
    main()
