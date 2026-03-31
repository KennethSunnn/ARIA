import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ARIA planner regression benchmark.")
    parser.add_argument("--min-match-rate", type=float, default=0.0, help="Fail if match_rate is below this threshold.")
    parser.add_argument("--min-strict-pass-rate", type=float, default=0.0, help="Fail if strict_pass_rate is below this threshold.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from aria_manager import ARIAManager

    cases_path = root / "benchmarks" / "regression_tasks.json"
    if not cases_path.is_file():
        raise SystemExit(f"missing benchmark file: {cases_path}")

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    manager = ARIAManager()
    manager.set_api_key("")
    rows = []

    for case in cases:
        query = str(case.get("query") or "").strip()
        expected = set(case.get("expected_keywords") or [])
        expected_mode = str(case.get("expected_mode") or "").strip()
        expected_risk = str(case.get("expected_risk_level") or "").strip()
        min_expected_hits = int(case.get("min_expected_hits", 1) or 1)
        plan = manager.plan_actions(query, "")
        actions = [str(a.get("type") or "") for a in (plan.get("actions") or [])]
        hit = len(expected.intersection(set(actions)))
        risk_level = manager.evaluate_action_risk_level(plan.get("actions") or [])
        mode_ok = (not expected_mode) or (str(plan.get("mode") or "") == expected_mode)
        risk_ok = (not expected_risk) or (risk_level == expected_risk)
        hit_ok = hit >= max(0, min_expected_hits)
        strict_ok = bool(mode_ok and risk_ok and hit_ok)
        rows.append(
            {
                "name": case.get("name"),
                "mode": plan.get("mode"),
                "risk_level": risk_level,
                "actions": actions,
                "expected_hit": hit,
                "expected_total": len(expected),
                "mode_ok": mode_ok,
                "risk_ok": risk_ok,
                "hit_ok": hit_ok,
                "strict_ok": strict_ok,
            }
        )

    hit_cases = sum(1 for r in rows if int(r["expected_hit"]) > 0)
    strict_cases = sum(1 for r in rows if bool(r.get("strict_ok")))
    total = len(rows)
    summary: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": total,
        "matched_cases": hit_cases,
        "strict_passed_cases": strict_cases,
        "match_rate": round(hit_cases / max(1, total), 4),
        "strict_pass_rate": round(strict_cases / max(1, total), 4),
        "rows": rows,
    }

    out_dir = root / "data" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "latest_regression_report.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved report to: {out_file}")
    if float(summary["match_rate"] or 0.0) < float(args.min_match_rate or 0.0):
        raise SystemExit(
            f"benchmark failed: match_rate={summary['match_rate']:.4f} < min_match_rate={float(args.min_match_rate):.4f}"
        )
    if float(summary["strict_pass_rate"] or 0.0) < float(args.min_strict_pass_rate or 0.0):
        raise SystemExit(
            "benchmark failed: strict_pass_rate="
            f"{summary['strict_pass_rate']:.4f} < min_strict_pass_rate={float(args.min_strict_pass_rate):.4f}"
        )


if __name__ == "__main__":
    main()
