# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-25

### Added
- `session_start.py` — SessionStart hook: injects active decisions into CLAUDE.md on every session start
- `on_stop.py` — Stop hook: auto-detects decisions from conversation transcripts and saves to `decisions.json`
- `session_end.py` — SessionEnd hook: saves versioned snapshots and updates `context_summary.md`
- `decision_manager.py` — CLI tool for manual decision management (add / list / update / supersede / history)
- `npx claude-context-optimizer` installer with smart merge for existing `settings.json` and `CLAUDE.md`
- `--global` flag to install hooks into `~/.claude` for all projects
- Version-controlled decisions with `superseded` status tracking
- Auto-categorization of decisions (architecture / tech_stack / api / ui_ux / infrastructure / policy / business)
- Snapshot history with automatic cleanup (keeps latest 30)
