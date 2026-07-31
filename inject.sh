#!/usr/bin/env bash
# inject.sh — 下游專案注入的總入口（各 harness 的實作在 bin/inject-<harness>.sh）。
#
# 用法：cd ~/my-project && bash ~/Agent_skill/inject.sh
#
# 全有全無：先跑完所有 harness 的 preflight，全數通過才進 install。
# agy 沒有下游 adapter（只吃全域 GEMINI.md），因此不在此列。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${AGENT_SKILL_PROJECT_DIR:-$(pwd)}"
HARNESSES=(claude codex)

python3 "$REPOSITORY_DIR/bin/validate-skill-index.py" --repo "$REPOSITORY_DIR"

for harness in "${HARNESSES[@]}"; do
  bash "$REPOSITORY_DIR/bin/inject-$harness.sh" --preflight
done
# git hook 與 harness 無關（三家共用同一份 .git/hooks），故不放進 inject-<harness>.sh
bash "$REPOSITORY_DIR/bin/install-git-hooks.sh" --preflight

for harness in "${HARNESSES[@]}"; do
  bash "$REPOSITORY_DIR/bin/inject-$harness.sh" --install
done
bash "$REPOSITORY_DIR/bin/install-git-hooks.sh" --install

python3 "$REPOSITORY_DIR/bin/validate-skill-index.py" \
  --repo "$REPOSITORY_DIR" \
  --claude-adapter "$PROJECT_DIR/.claude/skills" \
  --codex-adapter "$PROJECT_DIR/.codex/skills"

echo "✅ 注入完成：既有內容與第三方 entries 保留。"
echo "ℹ️  .codex/hooks.json 不分發；agy 不需下游 adapter（吃全域 GEMINI.md）。"
