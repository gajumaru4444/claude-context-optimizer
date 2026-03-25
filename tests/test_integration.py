"""統合テスト: セッションライフサイクル全体の動作確認"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "templates" / ".claude" / "hooks"
CLI_PATH = Path(__file__).parent.parent / "bin" / "cli.js"


@pytest.fixture
def project_dir(tmp_path):
    """CLI でセットアップ済みのプロジェクト"""
    subprocess.run(
        ["node", str(CLI_PATH)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    return tmp_path


def run_hook(project_dir, script, event_data=None):
    if event_data is None:
        event_data = {}
    return subprocess.run(
        [sys.executable, str(project_dir / ".claude" / "hooks" / script)],
        input=json.dumps(event_data),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
    )


def load_decisions(project_dir):
    f = project_dir / ".claude" / "context" / "decisions.json"
    return json.loads(f.read_text(encoding="utf-8"))


class TestFullSessionLifecycle:
    def test_session_lifecycle(self, project_dir):
        """
        セッション全体のライフサイクルをシミュレート:
        1. session_start → CLAUDE.md に空の意思決定セクション注入
        2. 手動で意思決定を追加
        3. session_end → サマリー生成・スナップショット保存
        4. 新セッション session_start → 前回の意思決定が CLAUDE.md に反映
        """
        # ── セッション1: 開始 ──
        result = run_hook(project_dir, "session_start.py", {
            "session_id": "session-1",
            "trigger": "startup",
        })
        assert result.returncode == 0

        claude_md = project_dir / "CLAUDE.md"
        content = claude_md.read_text(encoding="utf-8")
        assert "意思決定の記録なし" in content

        # ── セッション1: 意思決定を追加 ──
        subprocess.run(
            [sys.executable, str(project_dir / ".claude" / "hooks" / "decision_manager.py"),
             "add", "マイクロサービスアーキテクチャを採用",
             "--category", "architecture",
             "--content", "スケーラビリティと独立デプロイのため"],
            capture_output=True,
            text=True,
            env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
        )

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["status"] == "active"

        # ── セッション1: 終了 ──
        result = run_hook(project_dir, "session_end.py", {
            "session_id": "session-1",
            "reason": "user_exit",
        })
        assert result.returncode == 0

        # サマリーが生成されている
        summary = (project_dir / ".claude" / "context" / "context_summary.md").read_text(encoding="utf-8")
        assert "アクティブ: 1件" in summary
        assert "マイクロサービス" in summary

        # スナップショットが保存されている
        history_dir = project_dir / ".claude" / "context" / "decisions_history"
        assert len(list(history_dir.iterdir())) == 1

        # ── セッション2: 開始 ──
        result = run_hook(project_dir, "session_start.py", {
            "session_id": "session-2",
            "trigger": "startup",
        })
        assert result.returncode == 0

        # 前回の意思決定が CLAUDE.md に反映されている
        content = claude_md.read_text(encoding="utf-8")
        assert "マイクロサービスアーキテクチャを採用" in content
        assert "アクティブな意思決定: 1件" in content
        # 前回のサマリーも注入されている
        assert "アクティブ: 1件" in content

    def test_context_size_stays_bounded(self, project_dir):
        """
        意思決定を大量に追加しても CLAUDE.md のサイズが制御される
        （最新20件のみ表示される仕様）
        """
        manager = str(project_dir / ".claude" / "hooks" / "decision_manager.py")
        env = {"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""}

        # 25件の意思決定を追加
        for i in range(25):
            subprocess.run(
                [sys.executable, manager, "add", f"意思決定{i+1:02d}"],
                capture_output=True, text=True, env=env,
            )

        # session_start で CLAUDE.md を更新
        run_hook(project_dir, "session_start.py", {"session_id": "test", "trigger": "startup"})

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")

        # 最新20件は含まれる（v6〜v25）
        assert "意思決定25" in content
        assert "意思決定06" in content
        # 古い意思決定は含まれない（v1〜v5）— 20件制限
        # NOTE: format_decisions_for_context で active[-20:] にスライスされる
        assert "意思決定01" not in content

    def test_decision_update_flow(self, project_dir):
        """意思決定の更新フローが正しく機能する"""
        manager = str(project_dir / ".claude" / "hooks" / "decision_manager.py")
        env = {"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""}

        # v1: 元の決定
        subprocess.run(
            [sys.executable, manager, "add", "MySQL使用", "--category", "tech_stack"],
            capture_output=True, text=True, env=env,
        )

        # v2: 決定を更新
        subprocess.run(
            [sys.executable, manager, "update", "dec_0001",
             "--title", "PostgreSQL使用", "--content", "JSONBサポートのため"],
            capture_output=True, text=True, env=env,
        )

        # session_start で反映
        run_hook(project_dir, "session_start.py", {"session_id": "test", "trigger": "startup"})

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        # 新しい決定が表示
        assert "PostgreSQL使用" in content
        # 古い決定は superseded セクションに
        assert "更新済みの意思決定" in content
