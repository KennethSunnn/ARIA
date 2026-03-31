import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    from automation.interaction_intelligence import InteractionIntelligenceCore

    core = InteractionIntelligenceCore()

    r1 = core.normalize_result("desktop_open_app", {"success": True, "message": "ok"})
    assert r1["strategy_path"] == "rule_path"
    assert float(r1["confidence"]) > 0.5

    r2 = core.normalize_result(
        "wechat_send_message",
        {"success": False, "message": "wechat_send_failed", "stderr": "target_not_found"},
    )
    assert r2["safe_block_reason"] == "unresolved_target"
    assert float(r2["confidence"]) <= 0.35 + 1e-6

    should = core.should_try_browser_fallback(
        "browser_click",
        {"params": {"selector": ".bad-selector"}},
        {"success": False, "stderr": "timeout 30000ms exceeded"},
    )
    # 环境未启用 Playwright 时应为 False；启用且已安装时可为 True。
    assert isinstance(should, bool)

    print("interaction_intelligence_sanity_check:OK")


if __name__ == "__main__":
    main()

