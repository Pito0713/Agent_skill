#!/usr/bin/env bash
# migrate-downstream-paths.sh — 把下游專案 CLAUDE.md 的舊 skill 路徑改寫成新架構路徑。
#
# 用法：bash bin/migrate-downstream-paths.sh <專案路徑> [--apply]
#       預設 dry-run，加 --apply 才真的寫入。
#
# 背景：skill 從 skills/<category>/<name>.md 改為 package，且 link farm 是**扁平**的
# （沒有 engineering/ 這層），舊的 @~/.claude/skills/<category>/<name>.md 全部斷鏈，
# 而 Claude Code 對不存在的 @ 路徑靜默略過——不修就是無聲失效。
#
# 兩類路徑刻意不動：
#   - rules/*.md：setup-claude.sh 掛回 rules entry 後即自動復活，目錄結構未變
#   - governance/*.md：同上
#
# 註解掉的 `# @` 按需載入項目也一併改寫——使用者隨時可能取消註解，屆時才發現斷鏈
# 就太晚了（本腳本第一版只處理常駐 6 條，漏掉 11 條按需項，教訓見 lessons）。

set -euo pipefail

PROJECT_DIR="${1:-}"
APPLY_FLAG="${2:-}"
FARM_ROOT="${AGENT_SKILL_HOME:-$HOME}/.claude/skills"

if [[ -z "$PROJECT_DIR" ]]; then
  echo "用法：$0 <專案路徑> [--apply]" >&2
  exit 2
fi

TARGET_FILE="$PROJECT_DIR/CLAUDE.md"
if [[ ! -f "$TARGET_FILE" ]]; then
  echo "⚠️  找不到 $TARGET_FILE" >&2
  exit 1
fi

# 分隔符一律用 #：ERE 的 alternation 也是 |，用 | 當分隔符會讓 sed 在第一個
# alternation 處就認定 regex 結束，報 "parentheses not balanced"。

# 歷次改名：舊 skill 名 → 新 skill 名（在路徑改寫之前先套用）
# 規則**依序**套用形成改名鏈（gemini-assist → agy-assist → cli-delegate），
# 下游停在任一舊名都能一路遷到現名——新增改名時必須 append 在陣列尾端。
# 扁平化前（<category>/<name>.md）與扁平化後（<name>/SKILL.md）兩種形態都要收。
RENAME_RULES=(
  's#/gemini-assist\.md#/agy-assist.md#g'
  's#/agy-assist\.md#/cli-delegate.md#g'
  's#/agy-assist/SKILL\.md#/cli-delegate/SKILL.md#g'
)

# 扁平化：<category>/<name>.md → <name>/SKILL.md。rules / governance 不在白名單內。
FLATTEN_RULE='s#@~/\.claude/skills/(engineering|productivity|learning|design|investing)/([a-z0-9-]+)\.md#@~/.claude/skills/\2/SKILL.md#g'

# -E 必須排在所有 -e 之前：BSD sed 對 flag 順序敏感，放後面會讓前面的規則以 BRE 解析
SED_ARGS=(-E)
for rule in "${RENAME_RULES[@]}"; do
  SED_ARGS+=(-e "$rule")
done
SED_ARGS+=(-e "$FLATTEN_RULE")

if ! rewritten="$(sed "${SED_ARGS[@]}" "$TARGET_FILE")"; then
  echo "⚠️  改寫失敗：$TARGET_FILE" >&2
  exit 1
fi

# 改寫後逐條驗證：新路徑必須在 farm 下真的存在，否則不寫入。
# （@ 路徑不存在時 Claude Code 靜默略過，沒有這道檢查就驗不出改錯。）
broken_paths=()
while read -r reference; do
  [[ -n "$reference" ]] || continue
  relative_path="${reference#@\~/.claude/skills/}"
  [[ -e "$FARM_ROOT/$relative_path" ]] || broken_paths+=("$reference")
done < <(printf '%s\n' "$rewritten" | grep -oE '@~/\.claude/skills/[^ )`]+' | sort -u)

if [[ ${#broken_paths[@]} -gt 0 ]]; then
  echo "⚠️  改寫後仍有 ${#broken_paths[@]} 條路徑在 $FARM_ROOT 下不存在，未寫入：" >&2
  printf '   %s\n' "${broken_paths[@]}" >&2
  echo "   → 先確認已執行 setup.sh，或該 skill 是否已下架" >&2
  exit 1
fi

if [[ "$rewritten" == "$(cat "$TARGET_FILE")" ]]; then
  echo "✅ $TARGET_FILE 無舊路徑，不需遷移（所有引用皆可 resolve）"
  exit 0
fi

echo "─── 將變更 $TARGET_FILE ───"
diff <(cat "$TARGET_FILE") <(printf '%s\n' "$rewritten") || true
echo "─── 改寫後所有引用皆已驗證存在於 $FARM_ROOT ───"

if [[ "$APPLY_FLAG" != "--apply" ]]; then
  echo ""
  echo "ℹ️  dry-run；確認無誤後加 --apply 寫入"
  exit 0
fi

cp "$TARGET_FILE" "$TARGET_FILE.pre-migrate.bak"
printf '%s\n' "$rewritten" > "$TARGET_FILE"
echo "✅ 已寫入；原檔備份於 $TARGET_FILE.pre-migrate.bak"
