#!/usr/bin/env node

/**
 * claude-context-optimizer CLI
 *
 * Usage:
 *   npx claude-context-optimizer          # カレントディレクトリにinit
 *   npx claude-context-optimizer init     # 同上（明示的）
 *   npx claude-context-optimizer --global # ~/.claude に展開（全プロジェクト共通）
 *   npx claude-context-optimizer --help
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync, readdirSync, statSync } from "fs";
import { join, dirname, resolve, relative } from "path";
import { fileURLToPath } from "url";
import { createInterface } from "readline";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const TEMPLATES_DIR = join(__dirname, "..", "templates");

// ── ANSI カラー ──────────────────────────────────────────
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

// ── ユーティリティ ───────────────────────────────────────
function ask(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

/** ディレクトリを再帰的にコピー（衝突ファイルはリストで返す） */
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

/** JSON を安全にマージ（既存キーは上書きしない・hooksは配列をマージ） */
function mergeJson(existing, incoming) {
  const merged = { ...existing };
  for (const [key, val] of Object.entries(incoming)) {
    if (!(key in merged)) {
      merged[key] = val;
    } else if (key === "hooks" && typeof val === "object" && !Array.isArray(val)) {
      merged.hooks = mergeHooks(merged.hooks || {}, val);
    }
    // その他のキーは既存を優先（上書きしない）
  }
  return merged;
}

/** settings.json の hooks セクション専用マージ */
function mergeHooks(existing, incoming) {
  const merged = { ...existing };
  for (const [event, entries] of Object.entries(incoming)) {
    if (!merged[event]) {
      merged[event] = entries;
    } else {
      // 既存エントリに同じコマンドがなければ追記
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

/** CLAUDE.md の optimizer セクションをマージ（なければ末尾に追記） */
function mergeCLAUDEmd(existingContent, incomingContent) {
  const MARKER = "<!-- CONTEXT-OPTIMIZER:START -->";
  if (existingContent.includes(MARKER)) {
    // 既にセクションあり → そのまま（session_start.pyが更新するので触らない）
    return null; // null = 変更なし
  }
  // セクションを末尾に追記
  const section = incomingContent.split(MARKER).slice(1).join(MARKER);
  return existingContent.trimEnd() + "\n\n" + MARKER + section;
}

// ── メイン処理 ───────────────────────────────────────────
async function init(targetDir) {
  console.log();
  console.log(bold("  Claude Context Optimizer - セットアップ"));
  console.log(gray(`  ターゲット: ${targetDir}`));
  console.log();

  const files = collectFiles(TEMPLATES_DIR, targetDir);
  const conflicts = [];
  const mergeTargets = [];

  // 衝突チェック
  for (const f of files) {
    if (!existsSync(f.dest)) continue;
    const name = f.rel;
    if (name === "CLAUDE.md" || name === ".claude/settings.json") {
      mergeTargets.push(f);
    } else {
      conflicts.push(f);
    }
  }

  // 通常ファイルの衝突確認
  if (conflicts.length > 0) {
    console.log(warn("以下のファイルが既に存在します:"));
    for (const f of conflicts) console.log(`  ${gray(f.rel)}`);
    const ans = await ask(`  上書きしますか？ ${gray("[y/N]")} `);
    if (ans.toLowerCase() !== "y") {
      console.log(info("既存ファイルはスキップします"));
    } else {
      // overwrite フラグ
      conflicts.forEach((f) => (f.overwrite = true));
    }
  }

  let copied = 0, merged = 0, skipped = 0;

  for (const f of files) {
    mkdirSync(dirname(f.dest), { recursive: true });

    const isMerge = mergeTargets.includes(f);
    const isConflict = conflicts.includes(f);

    // ── マージ対象 ──
    if (isMerge) {
      const existing = readFileSync(f.dest, "utf8");
      const incoming = readFileSync(f.src, "utf8");

      if (f.rel === "CLAUDE.md") {
        const result = mergeCLAUDEmd(existing, incoming);
        if (result === null) {
          console.log(info(`マージ不要（既にセクションあり）: ${gray(f.rel)}`));
          skipped++;
        } else {
          writeFileSync(f.dest, result, "utf8");
          console.log(ok(`マージ: ${bold(f.rel)}`));
          merged++;
        }
      } else if (f.rel === ".claude/settings.json") {
        try {
          const existingJson = JSON.parse(existing);
          const incomingJson = JSON.parse(incoming);
          const mergedJson = mergeJson(existingJson, incomingJson);
          writeFileSync(f.dest, JSON.stringify(mergedJson, null, 2) + "\n", "utf8");
          console.log(ok(`マージ: ${bold(f.rel)}`));
          merged++;
        } catch {
          console.log(warn(`JSON マージ失敗、スキップ: ${f.rel}`));
          skipped++;
        }
      }
      continue;
    }

    // ── 衝突で上書きスキップ ──
    if (isConflict && !f.overwrite) {
      console.log(gray(`  スキップ: ${f.rel}`));
      skipped++;
      continue;
    }

    // ── 通常コピー ──
    copyFileSync(f.src, f.dest);
    console.log(ok(`コピー: ${bold(f.rel)}`));
    copied++;
  }

  // 実行権限（hooksディレクトリのpyファイル）
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

  // 完了メッセージ
  console.log();
  console.log(bold("  ✅ セットアップ完了"));
  console.log(`  ${gray(`コピー: ${copied}件 / マージ: ${merged}件 / スキップ: ${skipped}件`)}`);
  console.log();
  console.log(bold("  次のステップ:"));
  console.log(`  ${c.cyan}1.${c.reset} Claude Code を起動する`);
  console.log(`  ${c.cyan}2.${c.reset} CLAUDE.md が自動更新されることを確認`);
  console.log(`  ${c.cyan}3.${c.reset} 意思決定の手動追加:`);
  console.log(`     ${gray("python3 .claude/hooks/decision_manager.py add \"タイトル\" --category architecture")}`);
  console.log();
}

// ── グローバルモード（~/.claude に展開）───────────────────
async function initGlobal() {
  const homeDir = process.env.HOME || process.env.USERPROFILE;
  if (!homeDir) {
    console.error(err("HOME ディレクトリが取得できません"));
    process.exit(1);
  }
  const globalClaudeDir = join(homeDir, ".claude");
  console.log();
  console.log(bold("  グローバルモード"));
  console.log(info(`展開先: ${bold(globalClaudeDir)}`));
  console.log(warn("全プロジェクトに共通のHooksが適用されます"));
  console.log();
  const ans = await ask(`  続行しますか？ ${gray("[y/N]")} `);
  if (ans.toLowerCase() !== "y") {
    console.log("キャンセルしました");
    process.exit(0);
  }

  // グローバルは hooks/ と settings.json のみ（CLAUDE.mdは展開しない）
  const srcHooks    = join(TEMPLATES_DIR, ".claude", "hooks");
  const destHooks   = join(globalClaudeDir, "hooks");
  const srcSettings = join(TEMPLATES_DIR, ".claude", "settings.json");
  const destSettings= join(globalClaudeDir, "settings.json");

  mkdirSync(destHooks, { recursive: true });

  // hooks コピー
  for (const f of readdirSync(srcHooks)) {
    const dest = join(destHooks, f);
    if (!existsSync(dest)) {
      copyFileSync(join(srcHooks, f), dest);
      console.log(ok(`コピー: ${bold("~/.claude/hooks/" + f)}`));
    } else {
      console.log(gray(`  スキップ（既存）: ~/.claude/hooks/${f}`));
    }
  }

  // settings.json マージ
  if (existsSync(destSettings)) {
    try {
      const existing = JSON.parse(readFileSync(destSettings, "utf8"));
      const incoming = JSON.parse(readFileSync(srcSettings, "utf8"));
      // グローバル用: $CLAUDE_PROJECT_DIR パスを ~/.claude/hooks に書き換え
      const incomingStr = JSON.stringify(incoming)
        .replaceAll("$CLAUDE_PROJECT_DIR/.claude/hooks", `${globalClaudeDir}/hooks`);
      const incomingGlobal = JSON.parse(incomingStr);
      const merged = mergeJson(existing, incomingGlobal);
      writeFileSync(destSettings, JSON.stringify(merged, null, 2) + "\n", "utf8");
      console.log(ok(`マージ: ${bold("~/.claude/settings.json")}`));
    } catch {
      console.log(warn("settings.json のマージに失敗しました。手動で確認してください。"));
    }
  } else {
    const incoming = readFileSync(srcSettings, "utf8");
    const incomingGlobal = incoming
      .replaceAll("$CLAUDE_PROJECT_DIR/.claude/hooks", `${globalClaudeDir}/hooks`);
    writeFileSync(destSettings, incomingGlobal, "utf8");
    console.log(ok(`作成: ${bold("~/.claude/settings.json")}`));
  }

  console.log();
  console.log(bold("  ✅ グローバルセットアップ完了"));
  console.log(info("次回 Claude Code 起動時から全プロジェクトに適用されます"));
  console.log();
}

// ── ヘルプ ───────────────────────────────────────────────
function showHelp() {
  console.log(`
${bold("  claude-context-optimizer")} - Claude Codeコンテキスト最適化ツール

${bold("  使い方:")}
    npx claude-context-optimizer          カレントディレクトリにセットアップ
    npx claude-context-optimizer init     同上（明示的）
    npx claude-context-optimizer --global 全プロジェクト共通（~/.claude）にセットアップ
    npx claude-context-optimizer --help   このヘルプを表示

${bold("  展開されるファイル:")}
    .claude/hooks/session_start.py        SessionStart hook
    .claude/hooks/on_stop.py              Stop hook（意思決定の自動検出）
    .claude/hooks/session_end.py          SessionEnd hook
    .claude/hooks/decision_manager.py     手動管理CLI
    .claude/settings.json                 Hooks設定（既存があればマージ）
    .claude/context/decisions.json        意思決定ログ
    .claude/context/context_summary.md    セッションサマリー
    CLAUDE.md                             テンプレート（既存があればマージ）

${bold("  既存ファイルの扱い:")}
    settings.json → hooks セクションをマージ（既存設定は保持）
    CLAUDE.md     → optimizer セクションを末尾に追記
    その他        → 上書き確認あり
`);
}

// ── エントリーポイント ────────────────────────────────────
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
