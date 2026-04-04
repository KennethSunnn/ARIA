from unittest.mock import patch

from aria_manager import ARIAManager


class _NoopMethodManager:
    pass


class _NoopConversationManager:
    pass


def test_execute_actions_retries_recoverable_error_then_succeeds() -> None:
    manager = ARIAManager()
    manager.max_action_retries = 1
    outputs = iter(
        [
            {"success": False, "error_code": "timeout", "retryable": True, "stderr": "timeout"},
            {"success": True, "stdout": "ok"},
        ]
    )

    def _handler(*_args, **_kwargs):
        return next(outputs)

    manager.action_registry["custom_action"] = _handler
    payload = manager.execute_actions(
        [{"type": "custom_action", "target": "", "params": {}, "filters": {}, "risk": "low"}],
        "conv",
        "req",
        _NoopMethodManager(),
        _NoopConversationManager(),
    )
    report = payload["report"]
    assert len(report) == 2
    assert report[0]["outcome_state"] == "recoverable_error"
    assert report[0]["recovery_decision"].startswith("retry_scheduled:")
    assert report[1]["outcome_state"] == "success"
    assert report[1]["attempt"] == 2
    assert payload["manual_takeover_required"] is False


def test_execute_actions_marks_manual_takeover_when_verify_fails_after_retry() -> None:
    manager = ARIAManager()
    manager.max_action_retries = 1

    def _handler(*_args, **_kwargs):
        return {"success": True, "stdout": "simulated_write"}

    manager.action_registry["file_write"] = _handler
    payload = manager.execute_actions(
        [
            {
                "type": "file_write",
                "target": "tmp/never-created.txt",
                "params": {"path": "tmp/never-created.txt", "content": "demo"},
                "filters": {},
                "risk": "low",
            }
        ],
        "conv",
        "req",
        _NoopMethodManager(),
        _NoopConversationManager(),
    )
    report = payload["report"]
    assert len(report) == 2
    assert report[-1]["outcome_state"] == "verify_failed"
    assert report[-1]["needs_manual_takeover"] is True
    assert payload["manual_takeover_required"] is True


def test_execute_actions_cancellation_creates_cancelled_state() -> None:
    manager = ARIAManager()
    manager.max_action_retries = 1
    outputs = iter([{"success": False, "error_code": "timeout", "retryable": True}])

    def _handler(*_args, **_kwargs):
        return next(outputs)

    manager.action_registry["custom_action_cancel"] = _handler
    calls = {"n": 0}

    def _is_cancelled(_request_id: str) -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    with patch.object(manager, "is_cancelled", side_effect=_is_cancelled):
        payload = manager.execute_actions(
            [{"type": "custom_action_cancel", "target": "", "params": {}, "filters": {}, "risk": "low"}],
            "conv",
            "req",
            _NoopMethodManager(),
            _NoopConversationManager(),
        )
    report = payload["report"]
    assert len(report) == 1
    assert report[-1]["outcome_state"] == "cancelled"
    assert report[-1]["recovery_decision"] == "cancelled_by_user"
