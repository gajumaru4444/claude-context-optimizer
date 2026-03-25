#!/usr/bin/env python3
"""
decision_manager.py - 意思決定の手動管理CLIツール
Claude Codeから /decision コマンドで呼び出せる

使い方:
  python3 decision_manager.py add "タイトル" --content "詳細" --category architecture
  python3 decision_manager.py list
  python3 decision_manager.py list --category architecture
  python3 decision_manager.py update <id> --content "新しい詳細"
  python3 decision_manager.py supersede <id> --reason "理由"
  python3 decision_manager.py show <id>
  python3 decision_manager.py history
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


VALID_CATEGORIES = [
    "architecture", "tech_stack", "api", "ui_ux",
    "infrastructure", "policy", "business", "general"
]

VALID_STATUSES = ["active", "superseded", "archived"]


def get_context_dir() -> Path:
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    context_dir = project_root / ".claude" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir


def load_decisions(context_dir: Path) -> dict:
    decisions_file = context_dir / "decisions.json"
    if not decisions_file.exists():
        return {"version": "1.0.0", "last_updated": None, "decisions": []}
    with open(decisions_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_decisions(context_dir: Path, data: dict):
    decisions_file = context_dir / "decisions.json"
    data["last_updated"] = datetime.now().isoformat()
    with open(decisions_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 保存: {decisions_file}")


def generate_version(decisions: list) -> str:
    if not decisions:
        return "v1"
    max_v = 0
    for d in decisions:
        try:
            num = int(d.get("version", "v0").replace("v", ""))
            max_v = max(max_v, num)
        except ValueError:
            pass
    return f"v{max_v + 1}"


def cmd_add(args, context_dir: Path):
    """意思決定を追加する"""
    data = load_decisions(context_dir)
    decisions = data.get("decisions", [])

    new_id = f"dec_{len(decisions) + 1:04d}"
    version = generate_version(decisions)
    now = datetime.now().isoformat()

    new_decision = {
        "id": new_id,
        "version": version,
        "title": args.title,
        "content": args.content or "",
        "category": args.category or "general",
        "type": "manual",
        "status": "active",
        "timestamp": now,
        "supersedes": None,
        "superseded_at": None,
        "tags": args.tags.split(",") if args.tags else [],
    }

    decisions.append(new_decision)
    data["decisions"] = decisions
    save_decisions(context_dir, data)

    print(f"\n📌 意思決定を追加しました")
    print(f"  ID      : {new_id}")
    print(f"  バージョン: {version}")
    print(f"  タイトル  : {args.title}")
    print(f"  カテゴリ  : {args.category or 'general'}")
    if args.content:
        print(f"  詳細    : {args.content}")


def cmd_list(args, context_dir: Path):
    """意思決定一覧を表示する"""
    data = load_decisions(context_dir)
    decisions = data.get("decisions", [])

    # フィルタリング
    filtered = decisions
    if args.category:
        filtered = [d for d in filtered if d.get("category") == args.category]
    if args.status:
        filtered = [d for d in filtered if d.get("status") == args.status]
    else:
        filtered = [d for d in filtered if d.get("status") == "active"]

    if not filtered:
        print("該当する意思決定がありません")
        return

    print(f"\n📋 意思決定一覧 ({len(filtered)}件)\n")
    print(f"{'ID':<12} {'Ver':<6} {'Category':<15} {'Status':<12} {'Date':<12} Title")
    print("-" * 90)
    for d in filtered:
        ts = d.get("timestamp", "")[:10]
        print(
            f"{d.get('id', ''):<12} "
            f"{d.get('version', ''):<6} "
            f"{d.get('category', ''):<15} "
            f"{d.get('status', ''):<12} "
            f"{ts:<12} "
            f"{d.get('title', '')}"
        )


def cmd_show(args, context_dir: Path):
    """特定の意思決定の詳細を表示する"""
    data = load_decisions(context_dir)
    decisions = data.get("decisions", [])

    target = next((d for d in decisions if d.get("id") == args.id), None)
    if not target:
        print(f"❌ ID '{args.id}' が見つかりません")
        sys.exit(1)

    print(f"\n📌 意思決定詳細\n")
    for key, value in target.items():
        print(f"  {key:<15}: {value}")


def cmd_update(args, context_dir: Path):
    """既存の意思決定を更新する（バージョンアップ）"""
    data = load_decisions(context_dir)
    decisions = data.get("decisions", [])

    target = next((d for d in decisions if d.get("id") == args.id), None)
    if not target:
        print(f"❌ ID '{args.id}' が見つかりません")
        sys.exit(1)

    now = datetime.now().isoformat()
    old_version = target.get("version", "v0")

    # 古いものをsupersededに
    target["status"] = "superseded"
    target["superseded_at"] = now

    # 新しいバージョンを追加
    new_id = f"dec_{len(decisions) + 1:04d}"
    new_version = generate_version(decisions)

    new_decision = {
        "id": new_id,
        "version": new_version,
        "title": args.title or target["title"],
        "content": args.content or target.get("content", ""),
        "category": args.category or target.get("category", "general"),
        "type": target.get("type", "manual"),
        "status": "active",
        "timestamp": now,
        "supersedes": [args.id],
        "superseded_at": None,
        "tags": args.tags.split(",") if args.tags else target.get("tags", []),
    }

    decisions.append(new_decision)
    data["decisions"] = decisions
    save_decisions(context_dir, data)

    print(f"\n🔄 意思決定を更新しました")
    print(f"  {old_version} → {new_version} ({args.id} → {new_id})")
    print(f"  タイトル: {new_decision['title']}")


def cmd_supersede(args, context_dir: Path):
    """意思決定をsupersededにマークする"""
    data = load_decisions(context_dir)
    decisions = data.get("decisions", [])

    target = next((d for d in decisions if d.get("id") == args.id), None)
    if not target:
        print(f"❌ ID '{args.id}' が見つかりません")
        sys.exit(1)

    target["status"] = "superseded"
    target["superseded_at"] = datetime.now().isoformat()
    if args.reason:
        target["supersede_reason"] = args.reason

    data["decisions"] = decisions
    save_decisions(context_dir, data)
    print(f"✅ {args.id} をsupersededにマークしました")


def cmd_history(args, context_dir: Path):
    """スナップショット履歴を表示する"""
    history_dir = context_dir / "decisions_history"
    if not history_dir.exists():
        print("スナップショット履歴がありません")
        return

    snapshots = sorted(history_dir.iterdir(), reverse=True)
    print(f"\n📚 スナップショット履歴 ({len(snapshots)}件)\n")
    for snap in snapshots:
        snap_file = snap / "decisions.json"
        count = 0
        if snap_file.exists():
            try:
                with open(snap_file) as f:
                    d = json.load(f)
                    count = len([x for x in d.get("decisions", []) if x.get("status") == "active"])
            except Exception:
                pass
        print(f"  {snap.name}  (active: {count}件)")


def main():
    parser = argparse.ArgumentParser(
        description="Context Optimizer - 意思決定管理CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # add
    p_add = subparsers.add_parser("add", help="意思決定を追加")
    p_add.add_argument("title", help="意思決定のタイトル")
    p_add.add_argument("--content", "-c", help="詳細説明")
    p_add.add_argument("--category", "-cat", choices=VALID_CATEGORIES, help="カテゴリ")
    p_add.add_argument("--tags", "-t", help="タグ（カンマ区切り）")

    # list
    p_list = subparsers.add_parser("list", help="一覧表示")
    p_list.add_argument("--category", "-cat", choices=VALID_CATEGORIES)
    p_list.add_argument("--status", "-s", choices=VALID_STATUSES)

    # show
    p_show = subparsers.add_parser("show", help="詳細表示")
    p_show.add_argument("id", help="意思決定ID (例: dec_0001)")

    # update
    p_update = subparsers.add_parser("update", help="更新（バージョンアップ）")
    p_update.add_argument("id", help="更新対象のID")
    p_update.add_argument("--title", help="新しいタイトル")
    p_update.add_argument("--content", "-c", help="新しい詳細説明")
    p_update.add_argument("--category", "-cat", choices=VALID_CATEGORIES)
    p_update.add_argument("--tags", "-t", help="タグ（カンマ区切り）")

    # supersede
    p_sup = subparsers.add_parser("supersede", help="意思決定を無効化")
    p_sup.add_argument("id", help="対象のID")
    p_sup.add_argument("--reason", "-r", help="無効化の理由")

    # history
    subparsers.add_parser("history", help="スナップショット履歴を表示")

    args = parser.parse_args()
    context_dir = get_context_dir()

    if args.command == "add":
        cmd_add(args, context_dir)
    elif args.command == "list":
        cmd_list(args, context_dir)
    elif args.command == "show":
        cmd_show(args, context_dir)
    elif args.command == "update":
        cmd_update(args, context_dir)
    elif args.command == "supersede":
        cmd_supersede(args, context_dir)
    elif args.command == "history":
        cmd_history(args, context_dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
