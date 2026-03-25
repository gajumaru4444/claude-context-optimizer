"""session_end.py のテスト"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "templates" / ".claude" / "hooks"


@pytest.fixture
def project_dir(tmp_path):
    context_dir = tmp_path / ".claude" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "decisions.json").write_text(
        json.dumps({"version": "1.0.0", "last_updated": None, "decisions": []}),
        encoding="utf-8",
    )
    return tmp_path


def run_session_end(project_dir, event_data=None):
    if event_data is None:
        event_data = {"session_id": "test-session", "reason": "user_exit"}
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "session_end.py")],
        input=json.dumps(event_data),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
    )
    return result


class TestSessionEnd:
    def test_creates_context_summary(self, project_dir):
        """context_summary.md が生成される"""
        result = run_session_end(project_dir)
        assert result.returncode == 0

        summary = project_dir / ".claude" / "context" / "context_summary.md"
        assert summary.exists()
        content = summary.read_text(encoding="utf-8")
        assert "# Context Summary" in content
        assert "セッション情報" in content

    def test_summary_contains_session_info(self, project_dir):
        """サマリーにセッション情報が含まれる"""
        event_data = {"session_id": "abc-123", "reason": "user_exit"}
        run_session_end(project_dir, event_data)

        content = (project_dir / ".claude" / "context" / "context_summary.md").read_text(encoding="utf-8")
        assert "abc-123" in content
        assert "user_exit" in content

    def test_summary_contains_decision_counts(self, project_dir):
        """サマリーに意思決定の件数が含まれる"""
        decisions_file = project_dir / ".claude" / "context" / "decisions.json"
        decisions_file.write_text(
            json.dumps({
                "version": "1.0.0",
                "last_updated": "2026-03-25T00:00:00",
                "decisions": [
                    {
                        "id": "dec_0001", "version": "v1", "title": "Test1",
                        "category": "general", "status": "active",
                        "timestamp": "2026-03-25T00:00:00",
                    },
                    {
                        "id": "dec_0002", "version": "v2", "title": "Test2",
                        "category": "general", "status": "superseded",
                        "timestamp": "2026-03-25T00:00:00",
                    },
                ],
            }),
            encoding="utf-8",
        )

        run_session_end(project_dir)

        content = (project_dir / ".claude" / "context" / "context_summary.md").read_text(encoding="utf-8")
        assert "アクティブ: 1件" in content
        assert "更新済み: 1件" in content
        assert "合計: 2件" in content

    def test_creates_snapshot(self, project_dir):
        """decisions_history にスナップショットが保存される"""
        run_session_end(project_dir)

        history_dir = project_dir / ".claude" / "context" / "decisions_history"
        assert history_dir.exists()
        snapshots = list(history_dir.iterdir())
        assert len(snapshots) == 1
        assert (snapshots[0] / "decisions.json").exists()

    def test_snapshot_matches_current_decisions(self, project_dir):
        """スナップショットの内容が現在の decisions.json と一致する"""
        decisions_data = {
            "version": "1.0.0",
            "last_updated": "2026-03-25T00:00:00",
            "decisions": [
                {
                    "id": "dec_0001", "version": "v1", "title": "Snapshot Test",
                    "category": "general", "status": "active",
                    "timestamp": "2026-03-25T00:00:00",
                },
            ],
        }
        decisions_file = project_dir / ".claude" / "context" / "decisions.json"
        decisions_file.write_text(json.dumps(decisions_data), encoding="utf-8")

        run_session_end(project_dir)

        history_dir = project_dir / ".claude" / "context" / "decisions_history"
        snapshot = list(history_dir.iterdir())[0] / "decisions.json"
        snapshot_data = json.loads(snapshot.read_text(encoding="utf-8"))
        assert snapshot_data["decisions"][0]["title"] == "Snapshot Test"

    def test_snapshot_cleanup_keeps_30(self, project_dir):
        """古いスナップショットは30件まで保持"""
        history_dir = project_dir / ".claude" / "context" / "decisions_history"
        history_dir.mkdir(parents=True)

        # 35個の古いスナップショットを作成
        for i in range(35):
            snap_dir = history_dir / f"20260301T{i:06d}"
            snap_dir.mkdir()
            (snap_dir / "decisions.json").write_text("{}", encoding="utf-8")

        run_session_end(project_dir)

        snapshots = list(history_dir.iterdir())
        # 30件 + 新規1件 = 最大30件に保持
        assert len(snapshots) <= 31

    def test_handles_empty_decisions(self, project_dir):
        """意思決定が0件でも正常終了する"""
        result = run_session_end(project_dir)
        assert result.returncode == 0

        content = (project_dir / ".claude" / "context" / "context_summary.md").read_text(encoding="utf-8")
        assert "アクティブ: 0件" in content
