"""Tests for decision_manager.py"""

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


def run_manager(project_dir, args):
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "decision_manager.py")] + args,
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
    )
    return result


def load_decisions(project_dir):
    decisions_file = project_dir / ".claude" / "context" / "decisions.json"
    return json.loads(decisions_file.read_text(encoding="utf-8"))


class TestAdd:
    def test_add_basic(self, project_dir):
        """Basic decision addition"""
        result = run_manager(project_dir, ["add", "TypeScriptを採用"])
        assert result.returncode == 0

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["title"] == "TypeScriptを採用"
        assert data["decisions"][0]["status"] == "active"
        assert data["decisions"][0]["id"] == "dec_0001"
        assert data["decisions"][0]["version"] == "v1"

    def test_add_with_category(self, project_dir):
        """Addition with category specified"""
        run_manager(project_dir, ["add", "REST APIを採用", "--category", "api"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["category"] == "api"

    def test_add_with_content(self, project_dir):
        """Addition with detailed description"""
        run_manager(project_dir, ["add", "PostgreSQL", "--content", "スケーラビリティのため"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["content"] == "スケーラビリティのため"

    def test_add_with_tags(self, project_dir):
        """Addition with tags"""
        run_manager(project_dir, ["add", "Docker化", "--tags", "infra,devops"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["tags"] == ["infra", "devops"]

    def test_add_increments_version(self, project_dir):
        """Version increments with each addition"""
        run_manager(project_dir, ["add", "Decision 1"])
        run_manager(project_dir, ["add", "Decision 2"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["version"] == "v1"
        assert data["decisions"][1]["version"] == "v2"

    def test_add_updates_last_updated(self, project_dir):
        """last_updated is updated"""
        run_manager(project_dir, ["add", "Test"])

        data = load_decisions(project_dir)
        assert data["last_updated"] is not None


class TestList:
    def test_list_empty(self, project_dir):
        """When there are no decisions"""
        result = run_manager(project_dir, ["list"])
        assert result.returncode == 0
        assert "No matching decisions found" in result.stdout

    def test_list_shows_active(self, project_dir):
        """Shows active decisions"""
        run_manager(project_dir, ["add", "Test decision"])
        result = run_manager(project_dir, ["list"])
        assert "Test decision" in result.stdout

    def test_list_filter_by_category(self, project_dir):
        """Category filter"""
        run_manager(project_dir, ["add", "API design", "--category", "api"])
        run_manager(project_dir, ["add", "DB design", "--category", "architecture"])

        result = run_manager(project_dir, ["list", "--category", "api"])
        assert "API design" in result.stdout
        assert "DB design" not in result.stdout


class TestUpdate:
    def test_update_creates_new_version(self, project_dir):
        """Updating creates a new version"""
        run_manager(project_dir, ["add", "Original decision"])
        run_manager(project_dir, ["update", "dec_0001", "--title", "Updated decision"])

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 2
        assert data["decisions"][0]["status"] == "superseded"
        assert data["decisions"][1]["title"] == "Updated decision"
        assert data["decisions"][1]["status"] == "active"

    def test_update_nonexistent_id(self, project_dir):
        """Updating a nonexistent ID returns an error"""
        result = run_manager(project_dir, ["update", "dec_9999", "--title", "test"])
        assert result.returncode == 1


class TestSupersede:
    def test_supersede_marks_status(self, project_dir):
        """supersede changes the status"""
        run_manager(project_dir, ["add", "Old decision"])
        run_manager(project_dir, ["supersede", "dec_0001", "--reason", "Policy change"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["status"] == "superseded"
        assert data["decisions"][0]["supersede_reason"] == "Policy change"

    def test_supersede_nonexistent_id(self, project_dir):
        """Superseding a nonexistent ID returns an error"""
        result = run_manager(project_dir, ["supersede", "dec_9999"])
        assert result.returncode == 1


class TestShow:
    def test_show_displays_details(self, project_dir):
        """Shows decision details"""
        run_manager(project_dir, ["add", "Detail test", "--content", "Detailed content"])
        result = run_manager(project_dir, ["show", "dec_0001"])
        assert "Detail test" in result.stdout
        assert "Detailed content" in result.stdout

    def test_show_nonexistent_id(self, project_dir):
        """Showing a nonexistent ID returns an error"""
        result = run_manager(project_dir, ["show", "dec_9999"])
        assert result.returncode == 1
