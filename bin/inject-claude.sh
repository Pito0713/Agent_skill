#!/usr/bin/env bash
# inject-claude.sh — 在下游專案建立 Claude 的 skill adapter 與薄入口。
#
# 用法：bash bin/inject-claude.sh [--preflight|--install|--all]
#       專案目錄取自 $AGENT_SKILL_PROJECT_DIR，未設則用 $PWD

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPOSITORY_DIR/bin/lib-skill-farm.sh"

PROJECT_DIR="${AGENT_SKILL_PROJECT_DIR:-$(pwd)}"
INSTALL_HOME="${AGENT_SKILL_HOME:-$HOME}"
CLAUDE_ADAPTER="$PROJECT_DIR/.claude/skills"
PROJECT_ENTRY="$PROJECT_DIR/CLAUDE.md"

# 常駐載入：安全底線不靠模型自覺（CLAUDE.md 鐵律 7「安全底線不得放寬」）。
# 這兩條路徑依賴 setup-claude.sh 掛好的 rules extra entry，故 setup 必須先跑。
read -r -d '' MANAGED_BLOCK <<BLOCK || true
## Agent Skill adapter（claude）

@~/.claude/skills/rules/coding-standards.md
@~/.claude/skills/rules/security.md

其餘 skill 優先使用 native discovery（\`.claude/skills/\`）；未命中時讀取
\`~/Agent_skill/skills/index.json\` 查 package 路徑，再完整載入對應 \`SKILL.md\`。
BLOCK

run_preflight() {
  load_skill_index "$REPOSITORY_DIR"
  if [[ ! -d "$INSTALL_HOME/.claude/skills" ]]; then
    echo "⚠️  尚未安裝全域 Claude adapter；請先執行 setup.sh。" >&2
    return 1
  fi
  preflight_farm "$CLAUDE_ADAPTER"
  preflight_markers "$PROJECT_ENTRY"
}

run_install() {
  load_skill_index "$REPOSITORY_DIR"
  install_farm "$CLAUDE_ADAPTER"
  write_managed_block "$PROJECT_ENTRY" "$MANAGED_BLOCK"
  echo "✅ Claude adapter：${#SKILL_NAMES[@]} skills → $CLAUDE_ADAPTER"
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
