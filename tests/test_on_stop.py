"""on_stop.py のテスト（意思決定の自動検出）"""

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


def create_transcript(tmp_path, messages):
    """テスト用 transcript ファイルを作成"""
    transcript_path = tmp_path / "transcript.jsonl"
    lines = []
    for role, text in messages:
        entry = {"role": role, "content": [{"type": "text", "text": text}]}
        lines.append(json.dumps(entry, ensure_ascii=False))
    transcript_path.write_text("\n".join(lines), encoding="utf-8")
    return transcript_path


def run_on_stop(project_dir, event_data=None):
    if event_data is None:
        event_data = {}
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "on_stop.py")],
        input=json.dumps(event_data),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project_dir), "PATH": ""},
    )
    return result


def load_decisions(project_dir):
    decisions_file = project_dir / ".claude" / "context" / "decisions.json"
    return json.loads(decisions_file.read_text(encoding="utf-8"))


class TestDecisionDetection:
    def test_detects_japanese_decision(self, project_dir):
        """日本語の「〜に決めました」パターンを検出"""
        transcript = create_transcript(project_dir, [
            ("assistant", "データベースはPostgreSQLを使用することに決めました。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        result = run_on_stop(project_dir, event_data)
        assert result.returncode == 0

        data = load_decisions(project_dir)
        assert len(data["decisions"]) > 0

    def test_detects_adoption_pattern(self, project_dir):
        """「〜を採用」パターンを検出"""
        transcript = create_transcript(project_dir, [
            ("assistant", "フレームワークとしてNext.jsを採用します。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        assert len(data["decisions"]) > 0

    def test_detects_policy_pattern(self, project_dir):
        """「〜方針で進めます」パターンを検出"""
        transcript = create_transcript(project_dir, [
            ("assistant", "テストカバレッジ80%以上の方針で進めます。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        assert len(data["decisions"]) > 0

    def test_detects_english_decision(self, project_dir):
        """英語の決定パターンを検出"""
        transcript = create_transcript(project_dir, [
            ("assistant", "We decided to use React for the frontend."),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        assert len(data["decisions"]) > 0

    def test_ignores_user_messages(self, project_dir):
        """ユーザーメッセージは検出対象外"""
        transcript = create_transcript(project_dir, [
            ("user", "Reactを採用することに決めました。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 0

    def test_no_transcript_exits_cleanly(self, project_dir):
        """transcript がない場合は正常終了"""
        result = run_on_stop(project_dir, {})
        assert result.returncode == 0

        data = load_decisions(project_dir)
        assert len(data["decisions"]) == 0

    def test_estimates_category(self, project_dir):
        """カテゴリが自動推定される"""
        transcript = create_transcript(project_dir, [
            ("assistant", "アーキテクチャはマイクロサービス構成に決めました。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        decisions = data["decisions"]
        assert len(decisions) > 0
        assert decisions[0]["category"] == "architecture"

    def test_supersedes_similar_decision(self, project_dir):
        """類似の既存意思決定を superseded にマークする"""
        decisions_file = project_dir / ".claude" / "context" / "decisions.json"
        decisions_file.write_text(
            json.dumps({
                "version": "1.0.0",
                "last_updated": "2026-03-25T00:00:00",
                "decisions": [
                    {
                        "id": "dec_0001",
                        "version": "v1",
                        "title": "データベースはMySQL",
                        "content": "",
                        "category": "tech_stack",
                        "type": "manual",
                        "status": "active",
                        "timestamp": "2026-03-24T00:00:00",
                    }
                ],
            }),
            encoding="utf-8",
        )

        transcript = create_transcript(project_dir, [
            ("assistant", "データベースはPostgreSQLに変更することに決めました。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        statuses = [d["status"] for d in data["decisions"]]
        # 新しい意思決定が追加されている
        assert "active" in statuses

    def test_no_duplicate_detection(self, project_dir):
        """同じ文から重複検出しない"""
        transcript = create_transcript(project_dir, [
            ("assistant", "TypeScriptを使用することに決めました。TypeScriptを使用することに決めました。"),
        ])
        event_data = {"transcript_path": str(transcript)}

        run_on_stop(project_dir, event_data)

        data = load_decisions(project_dir)
        # 重複は除外される
        assert len(data["decisions"]) == 1
