#!/usr/bin/env python3
"""
Measure /api/process_input wall time and token_usage for perf baselines.

Compare: plain vs react_mode vs react_mode + react_computer_use_vision.
For TTFB, use browser DevTools Network on the same endpoint (this script reports full response time).

Usage (server must be running, API key configured server-side):
  python scripts/measure_process_input_perf.py
  python scripts/measure_process_input_perf.py --react
  python scripts/measure_process_input_perf.py --react --react-vision
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def post_json(url: str, payload: dict, timeout: float) -> tuple[float, dict]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}") from e
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    try:
        obj = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        obj = {"_parse_error": True, "raw": raw.decode("utf-8", errors="replace")[:2000]}
    if not isinstance(obj, dict):
        obj = {"_unexpected": obj}
    return elapsed_ms, obj


def main() -> int:
    p = argparse.ArgumentParser(description="POST /api/process_input and print latency + token_usage.")
    p.add_argument("--base", default="http://127.0.0.1:5000", help="Origin of web_app (no trailing slash)")
    p.add_argument(
        "--prompt",
        default="Reply with exactly the word: perf_ping",
        help="Short user_input to minimize LLM work",
    )
    p.add_argument("--react", action="store_true", help="Set react_mode true")
    p.add_argument("--react-vision", action="store_true", help="Set react_computer_use_vision true (implies --react)")
    p.add_argument("--timeout", type=float, default=180.0)
    args = p.parse_args()
    if args.react_vision:
        args.react = True

    url = f"{args.base.rstrip('/')}/api/process_input"
    payload: dict = {
        "user_input": args.prompt,
        "new_task": True,
        "react_mode": bool(args.react),
        "react_computer_use_vision": bool(args.react_vision),
    }
    label = "plain"
    if args.react_vision:
        label = "react+computer_use_vision"
    elif args.react:
        label = "react"

    print(f"POST {url}  scenario={label}", flush=True)
    try:
        ms, body = post_json(url, payload, args.timeout)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    tu = body.get("token_usage")
    print(f"elapsed_ms={ms:.1f}", flush=True)
    print(f"token_usage={json.dumps(tu, ensure_ascii=False)}", flush=True)
    print(f"success={body.get('success')} cancelled={body.get('cancelled')}", flush=True)
    if body.get("message"):
        print(f"message={body.get('message')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
