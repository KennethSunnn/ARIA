"""测试统一应用意图识别器"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.app_profiles.unified_app_intent import detect_app_intent


def test_cases():
    cases = [
        ("帮我打开小红书", {"app": "xiaohongshu", "operation": "open"}),
        ("给张三发微信", {"app": "wechat", "operation": "send_message"}),
        ("在小红书发笔记", {"app": "xiaohongshu", "operation": "post"}),
        ("打开微信聊天", {"app": "wechat", "operation": "open_chat"}),
        ("检查小红书是否登录", {"app": "xiaohongshu", "operation": "check_login"}),
        ("打开记事本", None),  # 不在注册表中
    ]

    print("=" * 60)
    print("统一应用意图识别测试")
    print("=" * 60)

    for text, expected in cases:
        result = detect_app_intent(text)
        status = "✓" if (result and expected and result["app"] == expected["app"] and result["operation"] == expected["operation"]) or (result is None and expected is None) else "✗"
        print(f"\n{status} 输入: {text}")
        print(f"  期望: {expected}")
        print(f"  实际: {result}")


if __name__ == "__main__":
    test_cases()
