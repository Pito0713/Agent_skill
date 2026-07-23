#!/usr/bin/env bash
# setup-codex.sh — Codex 的全域接線（skill farm + 全域 AGENTS.md）。
#
# 用法：bash bin/setup-codex.sh [--preflight|--install|--all]
#
# ⚠️ 開放項：官方 manual 記載的穩定 discovery roots 是 $HOME/.agents/skills 與
#    repo .agents/skills；本機 Codex v0.145.0 實測亦支援目前使用的 $CODEX_HOME/skills。
#    未來遷往官方 roots 時**只需改本檔**，不影響 Claude / agy——這正是拆分的目的。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPOSITORY_DIR/bin/lib-skill-farm.sh"

INSTALL_HOME="${AGENT_SKILL_HOME:-$HOME}"
CODEX_FARM="$INSTALL_HOME/.codex/skills"
GLOBAL_ENTRY="$INSTALL_HOME/.codex/AGENTS.md"

run_preflight() {
  load_skill_index "$REPOSITORY_DIR"
  preflight_farm "$CODEX_FARM"
  preflight_file_link "$GLOBAL_ENTRY" "$REPOSITORY_DIR/AGENTS.md"
}

run_install() {
  load_skill_index "$REPOSITORY_DIR"
  install_farm "$CODEX_FARM"
  install_file_link "$REPOSITORY_DIR/AGENTS.md" "$GLOBAL_ENTRY"
  echo "✅ Codex farm：${#SKILL_NAMES[@]} skills → $CODEX_FARM"
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
