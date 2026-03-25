"""bin/cli.js のテスト"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).parent.parent / "bin" / "cli.js"


@pytest.fixture
def target_dir(tmp_path):
    return tmp_path


class TestCLI:
    def test_help_flag(self):
        """--help でヘルプが表示される"""
        result = subprocess.run(
            ["node", str(CLI_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "claude-context-optimizer" in result.stdout
        assert "使い方" in result.stdout

    def test_init_copies_all_files(self, target_dir):
        """init で全ファイルがコピーされる"""
        result = subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )
        assert result.returncode == 0

        # 全ファイルが存在するか確認
        assert (target_dir / "CLAUDE.md").exists()
        assert (target_dir / ".claude" / "settings.json").exists()
        assert (target_dir / ".claude" / "hooks" / "session_start.py").exists()
        assert (target_dir / ".claude" / "hooks" / "on_stop.py").exists()
        assert (target_dir / ".claude" / "hooks" / "session_end.py").exists()
        assert (target_dir / ".claude" / "hooks" / "decision_manager.py").exists()
        assert (target_dir / ".claude" / "context" / "decisions.json").exists()
        assert (target_dir / ".claude" / "context" / "context_summary.md").exists()

    def test_init_claude_md_has_markers(self, target_dir):
        """コピーされた CLAUDE.md にマーカーが含まれる"""
        subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )

        content = (target_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "<!-- CONTEXT-OPTIMIZER:START -->" in content
        assert "<!-- CONTEXT-OPTIMIZER:END -->" in content

    def test_init_settings_json_valid(self, target_dir):
        """コピーされた settings.json が有効なJSON"""
        subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )

        settings = json.loads(
            (target_dir / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        assert "hooks" in settings
        assert "SessionStart" in settings["hooks"]
        assert "Stop" in settings["hooks"]
        assert "SessionEnd" in settings["hooks"]

    def test_init_merges_existing_settings(self, target_dir):
        """既存の settings.json がある場合マージされる"""
        settings_dir = target_dir / ".claude"
        settings_dir.mkdir(parents=True)
        existing = {"customKey": "customValue", "hooks": {}}
        (settings_dir / "settings.json").write_text(
            json.dumps(existing), encoding="utf-8"
        )

        subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )

        merged = json.loads(
            (target_dir / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        assert merged["customKey"] == "customValue"
        assert "SessionStart" in merged["hooks"]

    def test_init_merges_existing_claude_md(self, target_dir):
        """既存の CLAUDE.md にセクションを追記する"""
        (target_dir / "CLAUDE.md").write_text(
            "# My Project\n\nCustom content.\n", encoding="utf-8"
        )

        subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )

        content = (target_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "# My Project" in content
        assert "Custom content." in content
        assert "<!-- CONTEXT-OPTIMIZER:START -->" in content

    def test_init_skips_existing_optimizer_section(self, target_dir):
        """既に optimizer セクションがある CLAUDE.md はスキップ"""
        (target_dir / "CLAUDE.md").write_text(
            "# Project\n<!-- CONTEXT-OPTIMIZER:START -->\nold\n<!-- CONTEXT-OPTIMIZER:END -->\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )

        assert "マージ不要" in result.stdout

    def test_hooks_have_execute_permission(self, target_dir):
        """hooks の .py ファイルに実行権限が付与される"""
        subprocess.run(
            ["node", str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(target_dir),
        )

        import os
        hooks_dir = target_dir / ".claude" / "hooks"
        for py_file in hooks_dir.glob("*.py"):
            assert os.access(py_file, os.X_OK), f"{py_file.name} has no execute permission"
