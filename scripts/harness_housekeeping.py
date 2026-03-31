import argparse
import json
import time
from pathlib import Path
from typing import Any


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _agents_file_health(root: Path) -> dict:
    p = root / "AGENTS.md"
    if not p.is_file():
        return {"exists": False, "line_count": 0, "ok": False, "warning": "AGENTS.md missing"}
    lines = p.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    ok = line_count <= 60
    return {
        "exists": True,
        "line_count": line_count,
        "ok": ok,
        "warning": "" if ok else f"AGENTS.md too long ({line_count} > 60)",
    }


def _regression_health(root: Path, min_strict_pass_rate: float) -> dict:
    path = root / "data" / "benchmarks" / "latest_regression_report.json"
    data = _read_json(path, {})
    strict = float(data.get("strict_pass_rate", 0.0) or 0.0) if isinstance(data, dict) else 0.0
    total = int(data.get("total_cases", 0) or 0) if isinstance(data, dict) else 0
    ok = total > 0 and strict >= min_strict_pass_rate
    warning = ""
    if total <= 0:
        warning = "regression report missing or empty"
    elif strict < min_strict_pass_rate:
        warning = f"strict_pass_rate too low ({strict:.4f} < {min_strict_pass_rate:.4f})"
    return {
        "available": total > 0,
        "total_cases": total,
        "strict_pass_rate": round(strict, 4),
        "ok": ok,
        "warning": warning,
    }


def _methodology_health(root: Path) -> dict:
    path = root / "data" / "methodology" / "ab_stats.json"
    data = _read_json(path, {})
    methods = data.get("methods", {}) if isinstance(data, dict) else {}
    low_quality = 0
    for _, row in methods.items():
        if not isinstance(row, dict):
            continue
        quality = float(row.get("quality_score_avg", 0.0) or 0.0)
        if quality > 0 and quality < 0.45:
            low_quality += 1
    return {
        "method_count": len(methods) if isinstance(methods, dict) else 0,
        "low_quality_methods": low_quality,
        "ok": low_quality == 0,
        "warning": "" if low_quality == 0 else f"found {low_quality} low-quality methods",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run weekly ARIA harness housekeeping checks.")
    parser.add_argument("--min-strict-pass-rate", type=float, default=0.6)
    parser.add_argument("--fail-on-warn", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": {
            "agents_file": _agents_file_health(root),
            "regression": _regression_health(root, float(args.min_strict_pass_rate)),
            "methodology": _methodology_health(root),
        },
    }
    warnings: list[dict[str, str]] = []
    for name, item in report["checks"].items():
        if not bool(item.get("ok")):
            warnings.append({"check": name, "warning": item.get("warning", "check failed")})
    report["warnings"] = warnings
    report["ok"] = len(warnings) == 0

    out = root / "data" / "benchmarks" / "harness_housekeeping_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved report to: {out}")
    if args.fail_on_warn and warnings:
        raise SystemExit("housekeeping failed due to warnings")


if __name__ == "__main__":
    main()
