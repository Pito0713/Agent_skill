#!/usr/bin/env bash
# inject-codex.sh — 在下游專案建立 Codex 的 skill adapter 與薄入口。
#
# 用法：bash bin/inject-codex.sh [--preflight|--install|--all]
#
# 與 Claude 的差異（刻意保留，不要「統一」掉）：
#   - Codex 沒有 `@` 常駐語法，AGENTS.md 是整份載入且有 32KiB 上限，因此規範只能寫成
#     **文字要求**（軟性），強制力弱於 Claude 的 @ 常駐。此不對等已記入 ADR-013。
#   - .codex/hooks.json 不分發：hook 契約未穩定，避免覆蓋下游設定。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPOSITORY_DIR/bin/lib-skill-farm.sh"

PROJECT_DIR="${AGENT_SKILL_PROJECT_DIR:-$(pwd)}"
INSTALL_HOME="${AGENT_SKILL_HOME:-$HOME}"
CODEX_ADAPTER="$PROJECT_DIR/.codex/skills"
PROJECT_ENTRY="$PROJECT_DIR/AGENTS.md"

read -r -d '' MANAGED_BLOCK <<'BLOCK' || true
## Agent Skill adapter（codex）

**開工必讀**（安全底線，不得略過）：`~/Agent_skill/rules/coding-standards.md`、
`~/Agent_skill/rules/security.md`

其餘 skill 優先使用 native discovery（`.codex/skills/`）；未命中時讀取
`~/Agent_skill/skills/index.json` 查 package 路徑，再完整載入對應 `SKILL.md`。
BLOCK

run_preflight() {
  load_skill_index "$REPOSITORY_DIR"
  if [[ ! -d "$INSTALL_HOME/.codex/skills" ]]; then
    echo "⚠️  尚未安裝全域 Codex adapter；請先執行 setup.sh。" >&2
    return 1
  fi
  preflight_farm "$CODEX_ADAPTER"
  preflight_markers "$PROJECT_ENTRY"
}

run_install() {
  load_skill_index "$REPOSITORY_DIR"
  install_farm "$CODEX_ADAPTER"
  write_managed_block "$PROJECT_ENTRY" "$MANAGED_BLOCK"
  echo "✅ Codex adapter：${#SKILL_NAMES[@]} skills → $CODEX_ADAPTER"
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
