# claude-context-optimizer

[![CI](https://github.com/gajumaru4444/claude-context-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/gajumaru4444/claude-context-optimizer/actions/workflows/ci.yml)
[![npm version](https://img.shields.io/npm/v/claude-context-optimizer)](https://www.npmjs.com/package/claude-context-optimizer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

> Claude Code sessions tend to forget earlier decisions as conversations grow long.  
> This tool hooks into Claude Code's lifecycle to **automatically record decisions, inject them back into context, and version-control them** — so nothing gets lost.

## How it works

```
SessionStart  →  Read decisions.json → Inject into CLAUDE.md  (every session)
     ↓
  Claude works...
     ↓
Stop          →  Parse transcript → Detect decisions → Append to decisions.json
     ↓
SessionEnd    →  Save versioned snapshot → Update context_summary.md
```

On every session start, your active decisions are injected into `CLAUDE.md` automatically, so Claude always knows what has been decided — even in a brand-new session.

## Quick start

```bash
# Set up in your current project
npx claude-context-optimizer

# Or for all projects at once (~/.claude)
npx claude-context-optimizer --global
```

That's it. Open Claude Code and the hooks are active.

## What gets installed

```
.claude/
├── settings.json              ← Hook registrations (merged if exists)
├── hooks/
│   ├── session_start.py       ← Injects decisions → CLAUDE.md
│   ├── on_stop.py             ← Auto-detects decisions from transcript
│   ├── session_end.py         ← Snapshots + summary update
│   └── decision_manager.py    ← Manual CLI
└── context/
    ├── decisions.json          ← Versioned decision log
    ├── decisions_history/      ← Snapshots (latest 30 kept)
    └── context_summary.md      ← Human-readable summary
CLAUDE.md                       ← Optimizer section appended (merged if exists)
```

**Existing files are never destroyed.** `settings.json` hooks are merged, `CLAUDE.md` gets a new section appended.

## Automatic decision detection

Just speak naturally in your session. Patterns like these are auto-detected:

- 「〜を採用します」「〜に決めました」「〜方針で進めます」（Japanese）
- "decided to ...", "going with ...", "we'll use ..." (English)

Detected decisions are saved to `decisions.json` with a version number and category.

## Manual management (CLI)

```bash
# Add a decision
python3 .claude/hooks/decision_manager.py add "Use PostgreSQL" \
  --content "RLS-based multi-tenancy" \
  --category tech_stack

# List active decisions
python3 .claude/hooks/decision_manager.py list
python3 .claude/hooks/decision_manager.py list --category architecture

# Version-up an existing decision (old one becomes 'superseded')
python3 .claude/hooks/decision_manager.py update dec_0001 \
  --title "Use PostgreSQL + PGVector" \
  --content "Added vector search requirement"

# Mark a decision as no longer valid
python3 .claude/hooks/decision_manager.py supersede dec_0002 \
  --reason "Requirements changed"

# View snapshot history
python3 .claude/hooks/decision_manager.py history
```

## decisions.json schema

```json
{
  "version": "1.0.0",
  "last_updated": "2026-03-25T12:00:00",
  "decisions": [
    {
      "id": "dec_0001",
      "version": "v1",
      "title": "Use PostgreSQL",
      "content": "RLS-based multi-tenancy",
      "category": "tech_stack",
      "status": "active",
      "timestamp": "2026-03-25T12:00:00",
      "supersedes": null,
      "tags": []
    }
  ]
}
```

### Status values

| status | meaning |
|---|---|
| `active` | Currently valid decision |
| `superseded` | Replaced by a newer version |
| `archived` | Manually retired |

### Categories

`architecture` · `tech_stack` · `api` · `ui_ux` · `infrastructure` · `policy` · `business` · `general`

## Customization

### Add detection patterns (`on_stop.py`)

```python
DECISION_PATTERNS = [
    (r"(.{5,80})(?:で行く|でいく)", "decision"),  # add your own
    ...
]
```

### Change what's injected into CLAUDE.md (`session_start.py`)

Edit `format_decisions_for_context()` to control how decisions appear in every session.

## Requirements

- Claude Code (any recent version)
- Node.js ≥ 18 (for `npx`)
- Python ≥ 3.8 (stdlib only, no pip installs needed)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for ideas, dev setup, and test procedures.

## License

[MIT](./LICENSE) © 2026 gajumaru4444
