import argparse
import json
import time
from typing import Any

import requests


def _post_json(base_url: str, path: str, payload: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.post(url, json=payload, timeout=timeout_s)
    try:
        body = resp.json()
    except Exception as e:
        raise RuntimeError(f"non-json response from {path}: status={resp.status_code}, err={e}") from e
    if resp.status_code >= 400:
        raise RuntimeError(f"request failed {path}: status={resp.status_code}, body={body}")
    return body


def _get_json(base_url: str, path: str, params: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.get(url, params=params, timeout=timeout_s)
    try:
        body = resp.json()
    except Exception as e:
        raise RuntimeError(f"non-json response from {path}: status={resp.status_code}, err={e}") from e
    if resp.status_code >= 400:
        raise RuntimeError(f"request failed {path}: status={resp.status_code}, body={body}")
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanity check ARIA ReAct API flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="ARIA server base URL")
    parser.add_argument(
        "--query",
        default="打开百度并搜索 Python 教程，告诉我搜索页标题。",
        help="Input query to run through /api/process_input with react_mode=true",
    )
    parser.add_argument("--poll-ms", type=int, default=800, help="Polling interval for /api/execution/status")
    parser.add_argument("--timeout-s", type=int, default=120, help="Overall timeout in seconds")
    parser.add_argument("--request-timeout-s", type=int, default=20, help="Single HTTP request timeout in seconds")
    args = parser.parse_args()

    start = time.time()
    req_id = f"react-sanity-{int(start)}"

    first = _post_json(
        args.base_url,
        "/api/process_input",
        {
            "user_input": args.query,
            "request_id": req_id,
            "new_task": True,
            "react_mode": True,
        },
        timeout_s=args.request_timeout_s,
    )
    conversation_id = str(first.get("conversation_id") or "").strip()
    if not conversation_id:
        raise SystemExit("missing conversation_id in /api/process_input response")

    if not bool(first.get("needs_confirmation")):
        # ReAct flow is designed to require confirmation; if not, still continue for compatibility.
        print("warning: needs_confirmation=false, trying to poll execution status directly")
    else:
        _post_json(
            args.base_url,
            "/api/confirm_actions",
            {
                "conversation_id": conversation_id,
                "request_id": req_id,
                "force": False,
            },
            timeout_s=args.request_timeout_s,
        )

    terminal_states = {"completed", "aborted", "manual_takeover"}
    last_status = ""
    final_payload: dict[str, Any] = {}
    while True:
        if time.time() - start > args.timeout_s:
            raise SystemExit(f"timeout after {args.timeout_s}s, last_status={last_status}")
        st = _get_json(
            args.base_url,
            "/api/execution/status",
            {"conversation_id": conversation_id},
            timeout_s=args.request_timeout_s,
        )
        status = str(st.get("status") or "")
        if status != last_status:
            print(f"[status] {status}")
            last_status = status
        if status in terminal_states:
            final_payload = st
            break
        time.sleep(max(0.1, args.poll_ms / 1000.0))

    session_kind = str(final_payload.get("session_kind") or "")
    react_trace_raw = final_payload.get("react_trace")
    react_trace: list[Any] = react_trace_raw if isinstance(react_trace_raw, list) else []
    report_raw = final_payload.get("report")
    report: list[Any] = report_raw if isinstance(report_raw, list) else []
    print(
        json.dumps(
            {
                "conversation_id": conversation_id,
                "status": final_payload.get("status"),
                "session_kind": session_kind,
                "react_steps": len(react_trace),
                "executed_actions": len(report),
                "react_final_message": str(final_payload.get("react_final_message") or "")[:300],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if session_kind != "react":
        raise SystemExit("sanity failed: expected session_kind=react")
    if str(final_payload.get("status")) != "completed":
        raise SystemExit(f"sanity failed: execution not completed (status={final_payload.get('status')})")


if __name__ == "__main__":
    main()
