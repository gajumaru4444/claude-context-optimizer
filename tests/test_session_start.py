"""Tests for session_start.py"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "templates" / ".claude" / "hooks"


@pytest.fixture
def project_dir(tmp_path):
    """Create a test project directory"""
    context_dir = tmp_path / ".claude" / "context"
    context_dir.mkdir(parents=True)
    # Empty decisions.json
    (context_dir / "decisions.json").write_text(
        json.dumps({"version": "1.0.0", "last_updated": None, "decisions": []}),
        encoding="utf-8",
    )
    (context_dir / "context_summary.md").write_text("", encoding="utf-8")
    return tmp_path


def run_session_start(project_dir, event_data=None):
    """Run session_start.py"""
    if event_data is None:
        event_data = {"session_id": "test-session", "trigger": "startup"}
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "session_start.py")],
        input=json.dumps(event_data),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
    )
    return result


class TestSessionStart:
    def test_creates_claude_md_when_missing(self, project_dir):
        """Creates a new CLAUDE.md when it does not exist"""
        result = run_session_start(project_dir)
        assert result.returncode == 0

        claude_md = project_dir / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text(encoding="utf-8")
        assert "<!-- CONTEXT-OPTIMIZER:START -->" in content
        assert "<!-- CONTEXT-OPTIMIZER:END -->" in content

    def test_injects_into_existing_claude_md(self, project_dir):
        """Appends the section to an existing CLAUDE.md"""
        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nExisting content.\n", encoding="utf-8")

        result = run_session_start(project_dir)
        assert result.returncode == 0

        content = claude_md.read_text(encoding="utf-8")
        assert "# My Project" in content
        assert "Existing content." in content
        assert "<!-- CONTEXT-OPTIMIZER:START -->" in content

    def test_updates_existing_section(self, project_dir):
        """Updates the existing optimizer section"""
        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text(
            "# My Project\n\n"
            "<!-- CONTEXT-OPTIMIZER:START -->\nold content\n<!-- CONTEXT-OPTIMIZER:END -->\n",
            encoding="utf-8",
        )

        result = run_session_start(project_dir)
        assert result.returncode == 0

        content = claude_md.read_text(encoding="utf-8")
        assert "old content" not in content
        assert "Context Optimization" in content

    def test_injects_active_decisions(self, project_dir):
        """Active decisions are injected into CLAUDE.md"""
        decisions_file = project_dir / ".claude" / "context" / "decisions.json"
        decisions_file.write_text(
            json.dumps({
                "version": "1.0.0",
                "last_updated": "2026-03-25T00:00:00",
                "decisions": [
                    {
                        "id": "dec_0001",
                        "version": "v1",
                        "title": "TypeScriptを採用",
                        "content": "型安全のため",
                        "category": "tech_stack",
                        "type": "manual",
                        "status": "active",
                        "timestamp": "2026-03-25T00:00:00",
                    }
                ],
            }),
            encoding="utf-8",
        )

        result = run_session_start(project_dir)
        assert result.returncode == 0

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "TypeScriptを採用" in content
        assert "Active decisions: 1" in content

    def test_injects_context_summary(self, project_dir):
        """The previous session summary is injected into CLAUDE.md"""
        summary_file = project_dir / ".claude" / "context" / "context_summary.md"
        summary_file.write_text("前回はAPIの設計を行いました。", encoding="utf-8")

        result = run_session_start(project_dir)
        assert result.returncode == 0

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "前回はAPIの設計を行いました。" in content

    def test_outputs_additional_context(self, project_dir):
        """Outputs additionalContext JSON to stdout"""
        result = run_session_start(project_dir)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        assert "additionalContext" in output
        assert "Session started" in output["additionalContext"]

    def test_handles_corrupted_decisions_json(self, project_dir):
        """Does not crash on corrupted decisions.json"""
        decisions_file = project_dir / ".claude" / "context" / "decisions.json"
        decisions_file.write_text("not valid json{{{", encoding="utf-8")

        result = run_session_start(project_dir)
        assert result.returncode == 0

    def test_superseded_decisions_shown_separately(self, project_dir):
        """Superseded decisions are shown in a separate reference section"""
        decisions_file = project_dir / ".claude" / "context" / "decisions.json"
        decisions_file.write_text(
            json.dumps({
                "version": "1.0.0",
                "last_updated": "2026-03-25T00:00:00",
                "decisions": [
                    {
                        "id": "dec_0001",
                        "version": "v1",
                        "title": "JavaScript使用",
                        "content": "",
                        "category": "tech_stack",
                        "type": "manual",
                        "status": "superseded",
                        "timestamp": "2026-03-24T00:00:00",
                    },
                    {
                        "id": "dec_0002",
                        "version": "v2",
                        "title": "TypeScriptに変更",
                        "content": "",
                        "category": "tech_stack",
                        "type": "manual",
                        "status": "active",
                        "timestamp": "2026-03-25T00:00:00",
                    },
                ],
            }),
            encoding="utf-8",
        )

        result = run_session_start(project_dir)
        assert result.returncode == 0

        content = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "TypeScriptに変更" in content
        assert "Superseded Decisions" in content
