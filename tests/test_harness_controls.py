from aria_manager import ARIAManager


def test_tool_allowlist_filters_by_task_form() -> None:
    manager = ARIAManager()
    plan = {
        "mode": "action",
        "task_form": "web_information",
        "summary": "test",
        "actions": [
            {"type": "web_understand", "target": "https://example.com", "params": {}, "filters": {}, "risk": "low"},
            {"type": "file_delete", "target": "tmp.txt", "params": {}, "filters": {}, "risk": "high"},
        ],
    }
    filtered = manager._apply_task_form_tool_allowlist(plan)
    action_types = [a.get("type") for a in filtered.get("actions", [])]
    assert "web_understand" in action_types
    assert "file_delete" not in action_types


def test_exec_context_window_keeps_recent_steps() -> None:
    manager = ARIAManager()
    rows = [
        {"step": "s1", "description": "d1", "agent_type": "TextExecAgent", "result": "r1"},
        {"step": "s2", "description": "d2", "agent_type": "TextExecAgent", "result": "r2"},
        {"step": "s3", "description": "d3", "agent_type": "TextExecAgent", "result": "r3"},
        {"step": "s4", "description": "d4", "agent_type": "TextExecAgent", "result": "r4"},
        {"step": "s5", "description": "d5", "agent_type": "TextExecAgent", "result": "r5"},
    ]
    text = manager._build_exec_context_window(rows)
    assert "s5" in text
    assert "s1" not in text


def test_workspace_mode_filters_social_actions_for_engineer_autocad() -> None:
    manager = ARIAManager()
    manager.set_workspace_mode("aria_engineer_autocad")
    plan = {
        "mode": "action",
        "task_form": "local_execute",
        "summary": "autocad flow",
        "actions": [
            {"type": "desktop_open_app", "target": "AutoCAD", "params": {}, "filters": {}, "risk": "low"},
            {"type": "wechat_send_message", "target": "team", "params": {}, "filters": {}, "risk": "medium"},
        ],
    }
    filtered = manager._apply_task_form_tool_allowlist(plan)
    action_types = [a.get("type") for a in filtered.get("actions", [])]
    assert "desktop_open_app" in action_types
    assert "wechat_send_message" not in action_types
    assert filtered.get("workspace_mode") == "aria_engineer_autocad"
