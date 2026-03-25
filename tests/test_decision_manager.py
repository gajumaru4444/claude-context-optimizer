"""decision_manager.py のテスト"""

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
        """基本的な意思決定の追加"""
        result = run_manager(project_dir, ["add", "TypeScriptを採用"])
        assert result.returncode == 0

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["title"] == "TypeScriptを採用"
        assert data["decisions"][0]["status"] == "active"
        assert data["decisions"][0]["id"] == "dec_0001"
        assert data["decisions"][0]["version"] == "v1"

    def test_add_with_category(self, project_dir):
        """カテゴリ指定付きの追加"""
        run_manager(project_dir, ["add", "REST APIを採用", "--category", "api"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["category"] == "api"

    def test_add_with_content(self, project_dir):
        """詳細説明付きの追加"""
        run_manager(project_dir, ["add", "PostgreSQL", "--content", "スケーラビリティのため"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["content"] == "スケーラビリティのため"

    def test_add_with_tags(self, project_dir):
        """タグ付きの追加"""
        run_manager(project_dir, ["add", "Docker化", "--tags", "infra,devops"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["tags"] == ["infra", "devops"]

    def test_add_increments_version(self, project_dir):
        """追加するたびにバージョンが増加する"""
        run_manager(project_dir, ["add", "決定1"])
        run_manager(project_dir, ["add", "決定2"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["version"] == "v1"
        assert data["decisions"][1]["version"] == "v2"

    def test_add_updates_last_updated(self, project_dir):
        """last_updated が更新される"""
        run_manager(project_dir, ["add", "テスト"])

        data = load_decisions(project_dir)
        assert data["last_updated"] is not None


class TestList:
    def test_list_empty(self, project_dir):
        """意思決定がない場合"""
        result = run_manager(project_dir, ["list"])
        assert result.returncode == 0
        assert "該当する意思決定がありません" in result.stdout

    def test_list_shows_active(self, project_dir):
        """アクティブな意思決定を表示"""
        run_manager(project_dir, ["add", "テスト決定"])
        result = run_manager(project_dir, ["list"])
        assert "テスト決定" in result.stdout

    def test_list_filter_by_category(self, project_dir):
        """カテゴリフィルタ"""
        run_manager(project_dir, ["add", "API設計", "--category", "api"])
        run_manager(project_dir, ["add", "DB設計", "--category", "architecture"])

        result = run_manager(project_dir, ["list", "--category", "api"])
        assert "API設計" in result.stdout
        assert "DB設計" not in result.stdout


class TestUpdate:
    def test_update_creates_new_version(self, project_dir):
        """更新すると新しいバージョンが作成される"""
        run_manager(project_dir, ["add", "元の決定"])
        run_manager(project_dir, ["update", "dec_0001", "--title", "更新後の決定"])

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 2
        assert data["decisions"][0]["status"] == "superseded"
        assert data["decisions"][1]["title"] == "更新後の決定"
        assert data["decisions"][1]["status"] == "active"

    def test_update_nonexistent_id(self, project_dir):
        """存在しないIDの更新はエラー"""
        result = run_manager(project_dir, ["update", "dec_9999", "--title", "test"])
        assert result.returncode == 1


class TestSupersede:
    def test_supersede_marks_status(self, project_dir):
        """supersede で status が変更される"""
        run_manager(project_dir, ["add", "古い決定"])
        run_manager(project_dir, ["supersede", "dec_0001", "--reason", "方針変更"])

        data = load_decisions(project_dir)
        assert data["decisions"][0]["status"] == "superseded"
        assert data["decisions"][0]["supersede_reason"] == "方針変更"

    def test_supersede_nonexistent_id(self, project_dir):
        """存在しないIDの supersede はエラー"""
        result = run_manager(project_dir, ["supersede", "dec_9999"])
        assert result.returncode == 1


class TestShow:
    def test_show_displays_details(self, project_dir):
        """詳細表示"""
        run_manager(project_dir, ["add", "詳細テスト", "--content", "詳しい内容"])
        result = run_manager(project_dir, ["show", "dec_0001"])
        assert "詳細テスト" in result.stdout
        assert "詳しい内容" in result.stdout

    def test_show_nonexistent_id(self, project_dir):
        """存在しないIDの表示はエラー"""
        result = run_manager(project_dir, ["show", "dec_9999"])
        assert result.returncode == 1
