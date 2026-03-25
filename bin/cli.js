#!/usr/bin/env node

/**
 * claude-context-optimizer CLI
 *
 * Usage:
 *   npx claude-context-optimizer          # Initialize in current directory
 *   npx claude-context-optimizer init     # Same as above (explicit)
 *   npx claude-context-optimizer --global # Deploy to ~/.claude (shared across all projects)
 *   npx claude-context-optimizer --help
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync, readdirSync, statSync } from "fs";
import { join, dirname, resolve, relative } from "path";
import { fileURLToPath } from "url";
import { createInterface } from "readline";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const TEMPLATES_DIR = join(__dirname, "..", "templates");

// ── ANSI Colors ──────────────────────────────────────────
const c = {
  reset: "\x1b[0m",
  bold:  "\x1b[1m",
  green: "\x1b[32m",
  blue:  "\x1b[34m",
  yellow:"\x1b[33m",
  red:   "\x1b[31m",
  gray:  "\x1b[90m",
  cyan:  "\x1b[36m",
};
const ok   = (s) => `${c.green}✔${c.reset} ${s}`;
const info = (s) => `${c.blue}ℹ${c.reset} ${s}`;
const warn = (s) => `${c.yellow}⚠${c.reset} ${s}`;
const err  = (s) => `${c.red}✖${c.reset} ${s}`;
const bold = (s) => `${c.bold}${s}${c.reset}`;
const gray = (s) => `${c.gray}${s}${c.reset}`;

// ── Utilities ────────────────────────────────────────────
function ask(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

/** Recursively collect files from a directory (conflicting files are returned in a list) */
function collectFiles(srcDir, destDir, baseSrc = srcDir) {
  const files = [];
  for (const name of readdirSync(srcDir)) {
    const src  = join(srcDir, name);
    const dest = join(destDir, name);
    if (statSync(src).isDirectory()) {
      files.push(...collectFiles(src, dest, baseSrc));
    } else {
      files.push({ src, dest, rel: relative(baseSrc, src) });
    }
  }
  return files;
}

/** Safely merge JSON (existing keys are preserved, hooks arrays are merged) */
function mergeJson(existing, incoming) {
  const merged = { ...existing };
  for (const [key, val] of Object.entries(incoming)) {
    if (!(key in merged)) {
      merged[key] = val;
    } else if (key === "hooks" && typeof val === "object" && !Array.isArray(val)) {
      merged.hooks = mergeHooks(merged.hooks || {}, val);
    }
  }
  return merged;
}

/** Merge the hooks section of settings.json */
function mergeHooks(existing, incoming) {
  const merged = { ...existing };
  for (const [event, entries] of Object.entries(incoming)) {
    if (!merged[event]) {
      merged[event] = entries;
    } else {
      const existingCmds = (merged[event] || [])
        .flatMap((h) => h.hooks || [])
        .map((h) => h.command);
      const newEntries = entries.filter((entry) =>
        (entry.hooks || []).every((h) => !existingCmds.includes(h.command))
      );
      merged[event] = [...merged[event], ...newEntries];
    }
  }
  return merged;
}

/** Merge the optimizer section into CLAUDE.md (append to end if not present) */
function mergeCLAUDEmd(existingContent, incomingContent) {
  const MARKER = "<!-- CONTEXT-OPTIMIZER:START -->";
  if (existingContent.includes(MARKER)) {
    return null;
  }
  const section = incomingContent.split(MARKER).slice(1).join(MARKER);
  return existingContent.trimEnd() + "\n\n" + MARKER + section;
}

// ── Main ─────────────────────────────────────────────────
async function init(targetDir) {
  console.log();
  console.log(bold("  Claude Context Optimizer - Setup"));
  console.log(gray(`  Target: ${targetDir}`));
  console.log();

  const files = collectFiles(TEMPLATES_DIR, targetDir);
  const conflicts = [];
  const mergeTargets = [];

  for (const f of files) {
    if (!existsSync(f.dest)) continue;
    const name = f.rel;
    if (name === "CLAUDE.md" || name === ".claude/settings.json") {
      mergeTargets.push(f);
    } else {
      conflicts.push(f);
    }
  }

  if (conflicts.length > 0) {
    console.log(warn("The following files already exist:"));
    for (const f of conflicts) console.log(`  ${gray(f.rel)}`);
    const ans = await ask(`  Overwrite? ${gray("[y/N]")} `);
    if (ans.toLowerCase() !== "y") {
      console.log(info("Skipping existing files"));
    } else {
      conflicts.forEach((f) => (f.overwrite = true));
    }
  }

  let copied = 0, merged = 0, skipped = 0;

  for (const f of files) {
    mkdirSync(dirname(f.dest), { recursive: true });

    const isMerge = mergeTargets.includes(f);
    const isConflict = conflicts.includes(f);

    if (isMerge) {
      const existing = readFileSync(f.dest, "utf8");
      const incoming = readFileSync(f.src, "utf8");

      if (f.rel === "CLAUDE.md") {
        const result = mergeCLAUDEmd(existing, incoming);
        if (result === null) {
          console.log(info(`Merge not needed (section already exists): ${gray(f.rel)}`));
          skipped++;
        } else {
          writeFileSync(f.dest, result, "utf8");
          console.log(ok(`Merged: ${bold(f.rel)}`));
          merged++;
        }
      } else if (f.rel === ".claude/settings.json") {
        try {
          const existingJson = JSON.parse(existing);
          const incomingJson = JSON.parse(incoming);
          const mergedJson = mergeJson(existingJson, incomingJson);
          writeFileSync(f.dest, JSON.stringify(mergedJson, null, 2) + "\n", "utf8");
          console.log(ok(`Merged: ${bold(f.rel)}`));
          merged++;
        } catch {
          console.log(warn(`JSON merge failed, skipped: ${f.rel}`));
          skipped++;
        }
      }
      continue;
    }

    if (isConflict && !f.overwrite) {
      console.log(gray(`  Skipped: ${f.rel}`));
      skipped++;
      continue;
    }

    copyFileSync(f.src, f.dest);
    console.log(ok(`Copied: ${bold(f.rel)}`));
    copied++;
  }

  try {
    const hooksDir = join(targetDir, ".claude", "hooks");
    if (existsSync(hooksDir)) {
      for (const f of readdirSync(hooksDir)) {
        if (f.endsWith(".py")) {
          const { chmodSync } = await import("fs");
          chmodSync(join(hooksDir, f), 0o755);
        }
      }
    }
  } catch { /* ignore */ }

  console.log();
  console.log(bold("  Setup complete!"));
  console.log(`  ${gray(`Copied: ${copied} / Merged: ${merged} / Skipped: ${skipped}`)}`);
  console.log();
  console.log(bold("  Next steps:"));
  console.log(`  ${c.cyan}1.${c.reset} Start Claude Code`);
  console.log(`  ${c.cyan}2.${c.reset} Verify that CLAUDE.md is auto-updated`);
  console.log(`  ${c.cyan}3.${c.reset} Manually add decisions:`);
  console.log(`     ${gray("python3 .claude/hooks/decision_manager.py add \"Title\" --category architecture")}`);
  console.log();
}

// ── Global Mode (deploy to ~/.claude) ────────────────────
async function initGlobal() {
  const homeDir = process.env.HOME || process.env.USERPROFILE;
  if (!homeDir) {
    console.error(err("Could not determine HOME directory"));
    process.exit(1);
  }
  const globalClaudeDir = join(homeDir, ".claude");
  console.log();
  console.log(bold("  Global Mode"));
  console.log(info(`Target: ${bold(globalClaudeDir)}`));
  console.log(warn("Hooks will be applied to all projects"));
  console.log();
  const ans = await ask(`  Continue? ${gray("[y/N]")} `);
  if (ans.toLowerCase() !== "y") {
    console.log("Cancelled");
    process.exit(0);
  }

  const srcHooks    = join(TEMPLATES_DIR, ".claude", "hooks");
  const destHooks   = join(globalClaudeDir, "hooks");
  const srcSettings = join(TEMPLATES_DIR, ".claude", "settings.json");
  const destSettings= join(globalClaudeDir, "settings.json");

  mkdirSync(destHooks, { recursive: true });

  for (const f of readdirSync(srcHooks)) {
    const dest = join(destHooks, f);
    if (!existsSync(dest)) {
      copyFileSync(join(srcHooks, f), dest);
      console.log(ok(`Copied: ${bold("~/.claude/hooks/" + f)}`));
    } else {
      console.log(gray(`  Skipped (exists): ~/.claude/hooks/${f}`));
    }
  }

  if (existsSync(destSettings)) {
    try {
      const existing = JSON.parse(readFileSync(destSettings, "utf8"));
      const incoming = JSON.parse(readFileSync(srcSettings, "utf8"));
      const incomingStr = JSON.stringify(incoming)
        .replaceAll("$CLAUDE_PROJECT_DIR/.claude/hooks", `${globalClaudeDir}/hooks`);
      const incomingGlobal = JSON.parse(incomingStr);
      const merged = mergeJson(existing, incomingGlobal);
      writeFileSync(destSettings, JSON.stringify(merged, null, 2) + "\n", "utf8");
      console.log(ok(`Merged: ${bold("~/.claude/settings.json")}`));
    } catch {
      console.log(warn("Failed to merge settings.json. Please check manually."));
    }
  } else {
    const incoming = readFileSync(srcSettings, "utf8");
    const incomingGlobal = incoming
      .replaceAll("$CLAUDE_PROJECT_DIR/.claude/hooks", `${globalClaudeDir}/hooks`);
    writeFileSync(destSettings, incomingGlobal, "utf8");
    console.log(ok(`Created: ${bold("~/.claude/settings.json")}`));
  }

  console.log();
  console.log(bold("  Global setup complete!"));
  console.log(info("Hooks will be active for all projects on next Claude Code launch"));
  console.log();
}

// ── Help ─────────────────────────────────────────────────
function showHelp() {
  console.log(`
${bold("  claude-context-optimizer")} - Context optimization tool for Claude Code

${bold("  Usage:")}
    npx claude-context-optimizer          Initialize in current directory
    npx claude-context-optimizer init     Same as above (explicit)
    npx claude-context-optimizer --global Deploy to ~/.claude (all projects)
    npx claude-context-optimizer --help   Show this help

${bold("  Files deployed:")}
    .claude/hooks/session_start.py        SessionStart hook
    .claude/hooks/on_stop.py              Stop hook (auto-detect decisions)
    .claude/hooks/session_end.py          SessionEnd hook
    .claude/hooks/decision_manager.py     Decision management CLI
    .claude/settings.json                 Hooks config (merged if exists)
    .claude/context/decisions.json        Decision log
    .claude/context/context_summary.md    Session summary
    CLAUDE.md                             Template (merged if exists)

${bold("  Existing file handling:")}
    settings.json  Hooks section merged (existing settings preserved)
    CLAUDE.md      Optimizer section appended to end
    Others         Overwrite confirmation prompt
`);
}

// ── Entry point ──────────────────────────────────────────
const args = process.argv.slice(2);

if (args.includes("--help") || args.includes("-h")) {
  showHelp();
  process.exit(0);
}

if (args.includes("--global") || args.includes("-g")) {
  await initGlobal();
  process.exit(0);
}

// init or default
const targetDir = resolve(process.cwd());
await init(targetDir);
