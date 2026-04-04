from memory.mcp_memory_server import MemoryOps


def test_remember_recall_search_chain(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ops = MemoryOps()

    saved = ops.remember(
        project="aria",
        agent="devops-automator",
        topic="deploy-checkpoint",
        content="Rolled out canary to 10% with no 5xx spike.",
        tags=["ops", "release"],
    )
    assert saved["ok"] is True
    assert saved["method_id"]

    recalled = ops.recall(query="canary", tags=["release"], limit=3)
    assert recalled["ok"] is True
    assert recalled["count"] >= 1

    searched = ops.search(query="deploy-checkpoint", limit=3)
    assert searched["ok"] is True
    assert searched["count"] >= 1


def test_rollback_chain(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ops = MemoryOps()

    first = ops.remember(
        project="aria",
        agent="infrastructure-maintainer",
        topic="latency-tuning",
        content="Set DB pool size to 40.",
        tags=["ops"],
    )
    assert first["ok"] is True

    second = ops.remember(
        project="aria",
        agent="infrastructure-maintainer",
        topic="latency-tuning",
        content="Reduced DB pool size to 24 after saturation.",
        tags=["ops"],
    )
    assert second["ok"] is True
    assert second["version"] >= 2

    rolled = ops.rollback(method_id=second["method_id"], to_version=1)
    assert rolled["ok"] is True
    assert rolled["rollback_to"] == 1

