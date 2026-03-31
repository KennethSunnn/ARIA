import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    from aria_manager import format_wechat_need_disambiguation_message
    from automation.wechat_driver import WeChatDesktopDriver

    # 1) disambiguation message formatting
    msg = format_wechat_need_disambiguation_message(["张三", "张三(群聊)", "李四"])
    assert "需要消歧" in msg
    assert "1) 张三" in msg
    assert "2) 张三(群聊)" in msg

    msg2 = format_wechat_need_disambiguation_message([])
    assert "请补充接收人显示名" in msg2

    # 2) non-contact keyword filter heuristics
    d = WeChatDesktopDriver()
    assert d._is_probably_non_contact_result("微搜链接") is True
    assert d._is_probably_non_contact_result("公众号：测试") is True
    assert d._is_probably_non_contact_result("张三") is False

    # 3) match normalization doesn't explode
    assert d._normalize_for_match("  张三  ") == "张三"

    print("wechat_driver_regression_sanity_check:OK")


if __name__ == "__main__":
    main()

