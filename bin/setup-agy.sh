#!/usr/bin/env bash
# setup-agy.sh — Antigravity（agy）的全域接線。
#
# 用法：bash bin/setup-agy.sh [--preflight|--install|--all]
#
# agy 目前沒有 native skill discovery，只吃全域 GEMINI.md（內含路由表，用到才讀正本），
# 因此本檔僅一條 symlink。日後 agy 支援 skill farm 時，在此比照 setup-claude.sh 加掛。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPOSITORY_DIR/bin/lib-skill-farm.sh"

INSTALL_HOME="${AGENT_SKILL_HOME:-$HOME}"
GLOBAL_ENTRY="$INSTALL_HOME/.gemini/GEMINI.md"

MODE="${1:---all}"
case "$MODE" in
  --preflight | --install | --all) ;;
  *)
    echo "用法：$0 [--preflight|--install|--all]" >&2
    exit 2
    ;;
esac

[[ "$MODE" == "--install" ]] || preflight_file_link "$GLOBAL_ENTRY" "$REPOSITORY_DIR/GEMINI.md"
[[ "$MODE" == "--preflight" ]] || install_file_link "$REPOSITORY_DIR/GEMINI.md" "$GLOBAL_ENTRY"
