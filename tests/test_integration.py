"""Integration tests: full session lifecycle verification"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "templates" / ".claude" / "hooks"
CLI_PATH = Path(__file__).parent.parent / "bin" / "cli.js"


@pytest.fixture
def project_dir(tmp_path):
    """Project set up via CLI"""
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
        Simulate a full session lifecycle:
        1. session_start -> inject empty decision section into CLAUDE.md
        2. Manually add a decision
        3. session_end -> generate summary and save snapshot
        4. New session session_start -> previous decisions reflected in CLAUDE.md
        """
        # -- Session 1: Start --
        result = run_hook(project_dir, "session_start.py", {
            "session_id": "session-1",
            "trigger": "startup",
        })
        assert result.returncode == 0

        claude_md = project_dir / "CLAUDE.md"
        content = claude_md.read_text(encoding="utf-8")
        assert "No decisions recorded" in content

        # -- Session 1: Add a decision --
        subprocess.run(
            [sys.executable, str(project_dir / ".claude" / "hooks" / "decision_manager.py"),
             "add", "Adopt microservices architecture",
             "--category", "architecture",
             "--content", "For scalability and independent deployment"],
            capture_output=True,
            text=True,
            env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
        )

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["status"] == "active"

        # -- Session 1: End --
        result = run_hook(project_dir, "session_end.py", {
            "session_id": "session-1",
            "reason": "user_exit",
        })
        assert result.returncode == 0

        # Summary has been generated
        summary = (project_dir / ".claude" / "context" / "context_summary.md").read_text(encoding="utf-8")
        assert "Active: 1" in summary
        assert "microservices" in summary

        # Snapshot has been saved
        history_dir = project_dir / ".claude" / "context" / "decisions_history"
        assert len(list(history_dir.iterdir())) == 1

        # -- Session 2: Start --
        result = run_hook(project_dir, "session_start.py", {
            "session_id": "session-2",
            "trigger": "startup",
        })
        assert result.returncode == 0

        # Previous decisions are reflected in CLAUDE.md
        content = claude_md.read_text(encoding="utf-8")
        assert "Adopt microservices architecture" in content
        assert "Active decisions: 1" in content
        # Previous summary is also injected
        assert "Active: 1" in content

    def test_context_size_stays_bounded(self, project_dir):
        """
        CLAUDE.md size stays controlled even with many decisions added
        (only the latest 20 are displayed)
        """
        manager = str(project_dir / ".claude" / "hooks" / "decision_manager.py")
        env = {"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""}

        # Add 25 decisions
        for i in range(25):
            subprocess.run(
                [sys.executable, manager, "add", f"decision{i+1:02d}"],
                capture_output=True, text=True, env=env,
            )

        # Update CLAUDE.md via session_start
        run_hook(project_dir, "session_start.py", {"session_id": "test", "trigger": "startup"})

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")

        # Latest 20 are included (v6-v25)
        assert "decision25" in content
        assert "decision06" in content
        # Older decisions are not included (v1-v5) -- 20-item limit
        # NOTE: format_decisions_for_context slices with active[-20:]
        assert "decision01" not in content

    def test_decision_update_flow(self, project_dir):
        """Decision update flow works correctly"""
        manager = str(project_dir / ".claude" / "hooks" / "decision_manager.py")
        env = {"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""}

        # v1: Original decision
        subprocess.run(
            [sys.executable, manager, "add", "Use MySQL", "--category", "tech_stack"],
            capture_output=True, text=True, env=env,
        )

        # v2: Update the decision
        subprocess.run(
            [sys.executable, manager, "update", "dec_0001",
             "--title", "Use PostgreSQL", "--content", "For JSONB support"],
            capture_output=True, text=True, env=env,
        )

        # Reflect via session_start
        run_hook(project_dir, "session_start.py", {"session_id": "test", "trigger": "startup"})

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        # New decision is displayed
        assert "Use PostgreSQL" in content
        # Old decision is in the superseded section
        assert "Superseded Decisions" in content
