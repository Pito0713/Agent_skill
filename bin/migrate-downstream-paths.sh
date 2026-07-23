#!/usr/bin/env bash
# migrate-downstream-paths.sh — 把下游專案 CLAUDE.md 的舊 skill 路徑改寫成新架構路徑。
#
# 用法：bash bin/migrate-downstream-paths.sh <專案路徑> [--apply]
#       預設 dry-run，加 --apply 才真的寫入。
#
# 背景：skill 從 skills/<category>/<name>.md 改為 package，且 link farm 是**扁平**的
# （沒有 engineering/ 這層），舊的 @~/.claude/skills/<category>/<name>.md 全部斷鏈，
# 而 Claude Code 對不存在的 @ 路徑靜默略過——不修就是無聲失效。
# rules/ 三條不在此列：setup-claude.sh 掛回 rules entry 後即自動復活。

set -euo pipefail

PROJECT_DIR="${1:-}"
APPLY_FLAG="${2:-}"

if [[ -z "$PROJECT_DIR" ]]; then
  echo "用法：$0 <專案路徑> [--apply]" >&2
  exit 2
fi

TARGET_FILE="$PROJECT_DIR/CLAUDE.md"
if [[ ! -f "$TARGET_FILE" ]]; then
  echo "⚠️  找不到 $TARGET_FILE" >&2
  exit 1
fi

# 舊路徑 → 新扁平路徑
REWRITE_RULES=(
  's|@~/.claude/skills/engineering/coding-workflow-core\.md|@~/.claude/skills/coding-workflow-core/SKILL.md|g'
  's|@~/.claude/skills/productivity/handoff\.md|@~/.claude/skills/handoff/SKILL.md|g'
  's|@~/.claude/skills/productivity/version-log\.md|@~/.claude/skills/version-log/SKILL.md|g'
  's|@~/.claude/skills/engineering/agy-assist\.md|@~/.claude/skills/agy-assist/SKILL.md|g'
  's|@~/.claude/skills/engineering/coding-workflow-ref\.md|@~/.claude/skills/coding-workflow-ref/SKILL.md|g'
)

SED_ARGS=()
for rule in "${REWRITE_RULES[@]}"; do
  SED_ARGS+=(-e "$rule")
done

if ! rewritten="$(sed "${SED_ARGS[@]}" "$TARGET_FILE")"; then
  echo "⚠️  改寫失敗：$TARGET_FILE" >&2
  exit 1
fi

if [[ "$rewritten" == "$(cat "$TARGET_FILE")" ]]; then
  echo "✅ $TARGET_FILE 無舊路徑，不需遷移"
  exit 0
fi

echo "─── 將變更 $TARGET_FILE ───"
diff <(cat "$TARGET_FILE") <(printf '%s\n' "$rewritten") || true

if [[ "$APPLY_FLAG" != "--apply" ]]; then
  echo ""
  echo "ℹ️  dry-run；確認無誤後加 --apply 寫入"
  exit 0
fi

cp "$TARGET_FILE" "$TARGET_FILE.pre-migrate.bak"
printf '%s\n' "$rewritten" > "$TARGET_FILE"
echo "✅ 已寫入；原檔備份於 $TARGET_FILE.pre-migrate.bak"
