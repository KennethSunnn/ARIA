from pathlib import Path

from scripts import harness_housekeeping


def test_agents_file_health_warns_when_missing(tmp_path: Path) -> None:
    result = harness_housekeeping._agents_file_health(tmp_path)
    assert result["exists"] is False
    assert result["ok"] is False


def test_agents_file_health_accepts_short_file(tmp_path: Path) -> None:
    content = "\n".join(["line"] * 10)
    (tmp_path / "AGENTS.md").write_text(content, encoding="utf-8")
    result = harness_housekeeping._agents_file_health(tmp_path)
    assert result["exists"] is True
    assert result["ok"] is True
