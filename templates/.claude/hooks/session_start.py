#!/usr/bin/env python3
"""
session_start.py - SessionStart hook
セッション開始時に意思決定ログをCLAUDE.mdに注入する
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """CLAUDE.mdが存在するプロジェクトルートを返す"""
    # hookはプロジェクトルートのcwdで実行される
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    return cwd


def load_decisions(context_dir: Path) -> dict:
    """decisions.jsonを読み込む"""
    decisions_file = context_dir / "decisions.json"
    if not decisions_file.exists():
        return {"version": "1.0.0", "last_updated": None, "decisions": []}
    try:
        with open(decisions_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": "1.0.0", "last_updated": None, "decisions": []}


def load_context_summary(context_dir: Path) -> str:
    """context_summary.mdを読み込む"""
    summary_file = context_dir / "context_summary.md"
    if not summary_file.exists():
        return ""
    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            return f.read()
    except IOError:
        return ""


def format_decisions_for_context(decisions_data: dict) -> str:
    """意思決定データをCLAUDE.md用のテキストにフォーマットする"""
    decisions = decisions_data.get("decisions", [])
    if not decisions:
        return "_(意思決定の記録なし)_"

    # statusがactiveなものを優先、最新20件まで
    active = [d for d in decisions if d.get("status") == "active"]
    superseded = [d for d in decisions if d.get("status") == "superseded"]

    lines = []

    if active:
        lines.append("### アクティブな意思決定")
        for d in active[-20:]:
            v = d.get("version", "v?")
            ts = d.get("timestamp", "")[:10] if d.get("timestamp") else ""
            category = d.get("category", "general")
            title = d.get("title", "")
            content = d.get("content", "")
            lines.append(f"- **[{v}]** `{category}` {title} _{ts}_")
            if content:
                lines.append(f"  > {content}")

    if superseded:
        lines.append("\n### 更新済みの意思決定（参考）")
        for d in superseded[-5:]:
            v = d.get("version", "v?")
            ts = d.get("timestamp", "")[:10] if d.get("timestamp") else ""
            title = d.get("title", "")
            lines.append(f"- ~~[{v}]~~ {title} _{ts}_")

    return "\n".join(lines)


def update_claude_md(project_root: Path, decisions_data: dict, summary: str):
    """CLAUDE.mdの意思決定セクションを更新する"""
    claude_md = project_root / "CLAUDE.md"

    # 既存のCLAUDE.mdを読み込む
    existing_content = ""
    if claude_md.exists():
        with open(claude_md, "r", encoding="utf-8") as f:
            existing_content = f.read()

    # 管理セクションのマーカー
    START_MARKER = "<!-- CONTEXT-OPTIMIZER:START -->"
    END_MARKER = "<!-- CONTEXT-OPTIMIZER:END -->"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decision_count = len([d for d in decisions_data.get("decisions", []) if d.get("status") == "active"])
    last_updated = decisions_data.get("last_updated", "なし")

    decisions_text = format_decisions_for_context(decisions_data)

    injected_section = f"""{START_MARKER}
## 🧠 コンテキスト最適化 - 自動注入セクション
> _最終更新: {now} | アクティブな意思決定: {decision_count}件_
> _このセクションはsession_start.pyによって自動生成されます_

{decisions_text}

### セッションサマリー（前回まで）
{summary if summary else "_(サマリーなし)_"}
{END_MARKER}"""

    # 既存のマーカーセクションを置き換え or 末尾に追加
    if START_MARKER in existing_content and END_MARKER in existing_content:
        start_idx = existing_content.index(START_MARKER)
        end_idx = existing_content.index(END_MARKER) + len(END_MARKER)
        new_content = existing_content[:start_idx] + injected_section + existing_content[end_idx:]
    else:
        new_content = existing_content.rstrip() + "\n\n" + injected_section + "\n"

    with open(claude_md, "w", encoding="utf-8") as f:
        f.write(new_content)

    return decision_count


def main():
    # stdin からイベントデータを読み込む（Claude Codeから渡される）
    try:
        event_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event_data = {}

    project_root = get_project_root()
    context_dir = project_root / ".claude" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    # データ読み込み
    decisions_data = load_decisions(context_dir)
    summary = load_context_summary(context_dir)

    # CLAUDE.md更新
    count = update_claude_md(project_root, decisions_data, summary)

    # Claude Codeへの追加コンテキスト注入（additionalContext）
    session_id = event_data.get("session_id", "unknown")
    trigger = event_data.get("trigger", "startup")

    output = {
        "additionalContext": (
            f"[Context Optimizer] セッション開始 (trigger={trigger})\n"
            f"アクティブな意思決定: {count}件\n"
            f"CLAUDE.mdに意思決定ログを注入済み。"
            f"重要な設計変更・方針決定は必ず記録するよう心がけてください。"
        )
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
