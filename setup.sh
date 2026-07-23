#!/usr/bin/env bash
# setup.sh — 三 harness 全域接線的總入口（各 harness 的實作在 bin/setup-<harness>.sh）。
#
# 用法：bash setup.sh
#       AGENT_SKILL_HOME=/tmp/test-home bash setup.sh   # 隔離 dry-run
#
# 全有全無：先跑完三個 harness 的 preflight，全數通過才進 install。任一 preflight
# 失敗就零寫入中止——避免「Claude 接好了、agy 沒接」的半接線中間態。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_HOME="${AGENT_SKILL_HOME:-$HOME}"
HARNESSES=(claude codex agy)

python3 "$REPOSITORY_DIR/bin/validate-skill-index.py" --repo "$REPOSITORY_DIR"

for harness in "${HARNESSES[@]}"; do
  bash "$REPOSITORY_DIR/bin/setup-$harness.sh" --preflight
done

for harness in "${HARNESSES[@]}"; do
  bash "$REPOSITORY_DIR/bin/setup-$harness.sh" --install
done

python3 "$REPOSITORY_DIR/bin/validate-skill-index.py" \
  --repo "$REPOSITORY_DIR" \
  --claude-adapter "$INSTALL_HOME/.claude/skills" \
  --codex-adapter "$INSTALL_HOME/.codex/skills"

echo "🎉 Setup 完成：claude / codex / agy 全域接線就緒。"
