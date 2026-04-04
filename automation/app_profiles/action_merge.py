"""
可配置动作链合并：例如相邻同目标动作去重合并。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

_MERGE_RULES_CACHE: list[dict[str, Any]] | None = None


def _merge_rules_path() -> Path:
    return Path(__file__).resolve().parent / "merge_rules.yaml"


def load_merge_pairs() -> list[dict[str, Any]]:
    global _MERGE_RULES_CACHE
    if _MERGE_RULES_CACHE is not None:
        return _MERGE_RULES_CACHE
    rules: list[dict[str, Any]] = []
    path = _merge_rules_path()
    if path.is_file():
        try:
            import yaml  # type: ignore

            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            extra = data.get("merge_pairs")
            if isinstance(extra, list) and extra:
                for item in extra:
                    if isinstance(item, dict) and item.get("first") and item.get("second"):
                        rules.append(
                            {
                                "first": str(item["first"]).strip(),
                                "second": str(item["second"]).strip(),
                                "id_fields": list(
                                    item.get("id_fields")
                                    or ["recipient", "contact_name", "contact", "target"]
                                ),
                            }
                        )
        except Exception:
            rules = []
    _MERGE_RULES_CACHE = rules
    return _MERGE_RULES_CACHE


def _contact_id(action: dict[str, Any], id_fields: list[str]) -> str:
    p = action.get("params") if isinstance(action.get("params"), dict) else {}
    for k in id_fields:
        v = p.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    t = action.get("target")
    if t is not None and str(t).strip():
        return str(t).strip()
    return ""


def normalize_actions_with_merge_rules(
    actions: list[dict[str, Any]],
    normalize_alias: Callable[[str], str],
) -> list[dict[str, Any]]:
    """
    按 merge_rules.yaml 合并相邻重复链。
    """
    a = [x for x in (actions or []) if isinstance(x, dict)]
    if len(a) < 2:
        return a
    pairs = load_merge_pairs()
    if not pairs:
        return a
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(a):
        cur = a[i]
        merged = False
        t0 = normalize_alias(str(cur.get("type") or ""))
        for rule in pairs:
            first = rule.get("first") or ""
            second = rule.get("second") or ""
            id_fields = list(rule.get("id_fields") or ["recipient", "contact_name", "contact", "target"])
            if t0 != normalize_alias(first):
                continue
            if i + 1 >= len(a):
                continue
            nxt = a[i + 1]
            t1 = normalize_alias(str(nxt.get("type") or ""))
            if t1 != normalize_alias(second):
                continue
            c0 = _contact_id(cur, id_fields)
            c1 = _contact_id(nxt, id_fields)
            if c0 and c1 and c0 == c1:
                out.append(nxt)
                i += 2
                merged = True
                break
        if not merged:
            out.append(cur)
            i += 1
    return out
