#!/usr/bin/env python3
"""
session_end.py - SessionEnd hook
セッション終了時にスナップショットを保存し、context_summary.mdを更新する
"""

import json
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def load_decisions(context_dir: Path) -> dict:
    decisions_file = context_dir / "decisions.json"
    if not decisions_file.exists():
        return {"version": "1.0.0", "last_updated": None, "decisions": []}
    try:
        with open(decisions_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": "1.0.0", "last_updated": None, "decisions": []}


def save_snapshot(context_dir: Path, decisions_data: dict) -> Path:
    """decisions.jsonのスナップショットを保存する"""
    history_dir = context_dir / "decisions_history"
    history_dir.mkdir(parents=True, exist_ok=True)

    # タイムスタンプベースのディレクトリ名
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    snapshot_dir = history_dir / ts
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshot_file = snapshot_dir / "decisions.json"
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(decisions_data, f, ensure_ascii=False, indent=2)

    # 古いスナップショットのクリーンアップ（最新30件を保持）
    snapshots = sorted(history_dir.iterdir())
    if len(snapshots) > 30:
        for old in snapshots[:-30]:
            shutil.rmtree(old, ignore_errors=True)

    return snapshot_file


def generate_summary(decisions_data: dict, session_info: dict) -> str:
    """context_summary.mdの内容を生成する"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decisions = decisions_data.get("decisions", [])

    active = [d for d in decisions if d.get("status") == "active"]
    superseded = [d for d in decisions if d.get("status") == "superseded"]

    # カテゴリ別に集計
    categories: dict[str, list] = {}
    for d in active:
        cat = d.get("category", "general")
        categories.setdefault(cat, []).append(d)

    lines = [
        "# Context Summary",
        "",
        "_このファイルはsession_end.pyによって自動更新されます_",
        "",
        f"## 最終更新",
        f"{now}",
        "",
        f"## セッション情報",
        f"- セッションID: {session_info.get('session_id', 'unknown')}",
        f"- 終了理由: {session_info.get('reason', 'unknown')}",
        "",
        f"## 意思決定サマリー",
        f"- アクティブ: {len(active)}件",
        f"- 更新済み: {len(superseded)}件",
        f"- 合計: {len(decisions)}件",
        "",
    ]

    if active:
        lines.append("## アクティブな意思決定（カテゴリ別）")
        lines.append("")
        for cat, items in sorted(categories.items()):
            lines.append(f"### {cat}")
            for d in items[-10:]:
                v = d.get("version", "v?")
                ts = d.get("timestamp", "")[:10]
                title = d.get("title", "")
                lines.append(f"- **{v}** {title} _({ts})_")
            lines.append("")

    if superseded:
        lines.append("## 更新済みの意思決定（最新5件）")
        lines.append("")
        for d in superseded[-5:]:
            v = d.get("version", "v?")
            title = d.get("title", "")
            superseded_at = d.get("superseded_at", "")[:10]
            lines.append(f"- ~~{v}~~ {title} _(更新: {superseded_at})_")
        lines.append("")

    return "\n".join(lines)


def main():
    try:
        event_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event_data = {}

    project_root = get_project_root()
    context_dir = project_root / ".claude" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    decisions_data = load_decisions(context_dir)

    # スナップショット保存
    snapshot_path = save_snapshot(context_dir, decisions_data)

    # context_summary.md更新
    session_info = {
        "session_id": event_data.get("session_id", "unknown"),
        "reason": event_data.get("reason", "unknown"),
    }
    summary = generate_summary(decisions_data, session_info)

    summary_file = context_dir / "context_summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary)

    active_count = len([d for d in decisions_data.get("decisions", []) if d.get("status") == "active"])
    print(
        f"[Context Optimizer] セッション終了処理完了\n"
        f"  スナップショット: {snapshot_path}\n"
        f"  アクティブな意思決定: {active_count}件",
        file=sys.stderr,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
