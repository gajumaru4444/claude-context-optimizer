# Contributing

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/gajumaru4444/claude-context-optimizer.git
cd claude-context-optimizer

# Test the CLI locally
node bin/cli.js --help
node bin/cli.js        # run against current directory
```

No build step or dependencies required — pure Node.js + Python.

## Project Structure

```
bin/
  cli.js                  # npx entry point (Node.js)
templates/
  .claude/
    hooks/
      session_start.py    # SessionStart hook
      on_stop.py          # Stop hook
      session_end.py      # SessionEnd hook
      decision_manager.py # Manual CLI tool
    settings.json         # Hook registration template
    context/
      decisions.json      # Initial empty decisions store
      context_summary.md  # Initial summary template
  CLAUDE.md               # CLAUDE.md template
```

## How to Contribute

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feat/your-feature`
3. **Make changes** and test manually
4. **Open a Pull Request** with a clear description

## Testing

Manual test procedure:

```bash
# Test on a fresh directory
mkdir /tmp/test-fresh && cd /tmp/test-fresh
node /path/to/cli.js

# Test on a directory with existing files
mkdir /tmp/test-existing && cd /tmp/test-existing
echo '{"hooks":{"PostToolUse":[]}}' > .claude/settings.json
node /path/to/cli.js

# Test decision_manager
CLAUDE_PROJECT_DIR=$(pwd) python3 .claude/hooks/decision_manager.py add "Test decision"
CLAUDE_PROJECT_DIR=$(pwd) python3 .claude/hooks/decision_manager.py list

# Test session_start hook
echo '{"session_id":"test","trigger":"startup"}' | \
  CLAUDE_PROJECT_DIR=$(pwd) python3 .claude/hooks/session_start.py
```

## Ideas for Contributions

- [ ] Interactive mode for `decision_manager.py` (fzf-style picker)
- [ ] `PreCompact` hook to rescue critical context before Claude compresses
- [ ] Claude API-powered decision extraction (higher accuracy than regex)
- [ ] VS Code extension integration
- [ ] Web UI for browsing decision history
- [ ] Export to Markdown / Notion / Confluence

## Code Style

- Python: follow PEP 8, use type hints where practical
- JavaScript: ES modules, no external dependencies in `bin/cli.js`
- Keep hooks dependency-free (stdlib only) so they work without `npm install`

## Reporting Issues

Please include:
- Claude Code version (`claude --version`)
- OS and Python version (`python3 --version`)
- The content of `.claude/settings.json`
- Steps to reproduce
