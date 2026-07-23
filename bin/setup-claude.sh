#!/usr/bin/env bash
# setup-claude.sh — Claude Code 的全域接線（skill farm + governance + 全域 CLAUDE.md）。
#
# 用法：bash bin/setup-claude.sh [--preflight|--install|--all]
#   --preflight  只檢查，零寫入（供 setup.sh 做跨 harness 全有全無）
#   --install    只安裝（呼叫端須先確認 preflight 全過）
#   --all        預設，兩者依序執行

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPOSITORY_DIR/bin/lib-skill-farm.sh"

INSTALL_HOME="${AGENT_SKILL_HOME:-$HOME}"
CLAUDE_FARM="$INSTALL_HOME/.claude/skills"
GOVERNANCE_LINK="$INSTALL_HOME/.claude/governance"
GLOBAL_ENTRY="$INSTALL_HOME/.claude/CLAUDE.md"

# Claude 特有：`@` 常駐語法只認 ~/.claude/skills/ 前綴，rules 與 governance 不是
# skill package，必須額外掛進 farm，否則 @~/.claude/skills/rules/*.md 全部斷鏈。
# Codex / agy 走絕對路徑讀正本，不需要這兩條。
EXTRA_ENTRIES=(
  "rules:$REPOSITORY_DIR/rules"
  "governance:$REPOSITORY_DIR/governance"
)

run_preflight() {
  load_skill_index "$REPOSITORY_DIR"
  preflight_farm "$CLAUDE_FARM" "${EXTRA_ENTRIES[@]}"
  preflight_file_link "$GOVERNANCE_LINK" "$REPOSITORY_DIR/governance"
  preflight_file_link "$GLOBAL_ENTRY" "$REPOSITORY_DIR/CLAUDE.global.md"
}

run_install() {
  load_skill_index "$REPOSITORY_DIR"
  install_farm "$CLAUDE_FARM" "${EXTRA_ENTRIES[@]}"
  install_file_link "$REPOSITORY_DIR/governance" "$GOVERNANCE_LINK"
  install_file_link "$REPOSITORY_DIR/CLAUDE.global.md" "$GLOBAL_ENTRY"
  echo "✅ Claude farm：${#SKILL_NAMES[@]} skills + ${#EXTRA_ENTRIES[@]} extra entries → $CLAUDE_FARM"
}

MODE="${1:---all}"
case "$MODE" in
  --preflight | --install | --all) ;;
  *)
    echo "用法：$0 [--preflight|--install|--all]" >&2
    exit 2
    ;;
esac

[[ "$MODE" == "--install" ]] || run_preflight
[[ "$MODE" == "--preflight" ]] || run_install
