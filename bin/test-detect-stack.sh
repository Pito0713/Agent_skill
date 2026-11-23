#!/usr/bin/env bash
# test-detect-stack.sh — bin/detect-stack.sh 的測試，含「script 與 SKILL.md Phase 0 表」的防漂移檢查。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/detect-stack.sh"
SKILL="$SCRIPT_DIR/../skills/engineering/coding-workflow-core/SKILL.md"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
check() { [[ "$2" == "$3" ]] && pass "$1" || fail "${1}（實際：${2//$'\n'/ | }）"; }

# fixture <名稱> <相對路徑:內容>…：建一個專案目錄，回傳 detect-stack 的輸出（rules 名稱，空白分隔）
fixture() {
  local dir="$SANDBOX/$1" spec; shift
  mkdir -p "$dir"
  for spec in "$@"; do mkdir -p "$dir/$(dirname "${spec%%:*}")"; printf '%s\n' "${spec#*:}" >"$dir/${spec%%:*}"; done
  bash "$TOOL" "$dir" | sed -E 's|.*/rules/||; s|\.md$||' | paste -sd' ' -
}

echo "[Phase 0 表每一列]"
check "tsconfig.json → typescript" "$(fixture ts tsconfig.json:{})" typescript
check "*.ts → typescript" "$(fixture tsfile src/a.ts:x)" typescript
check "package.json 含 react → react + frontend-security" "$(fixture react 'package.json:{"dependencies":{"react":"18"}}')" "react frontend-security"
check "next.config.* → nextjs" "$(fixture next next.config.js:x)" nextjs
check "pyproject.toml → python" "$(fixture py pyproject.toml:x)" python
check "*.py → python" "$(fixture pyfile app/main.py:x)" python
check "*.test.* → testing" "$(fixture jest src/a.test.js:x)" testing
check "pytest.ini → testing" "$(fixture pytest pytest.ini:x)" testing
check "package.json 含 vue → 只有 frontend-security" "$(fixture vue 'package.json:{"dependencies":{"vue":"3"}}')" frontend-security
check "*.tsx → typescript" "$(fixture tsx src/App.tsx:x)" typescript
check "requirements.txt → python" "$(fixture req requirements.txt:x)" python
check "*.spec.* → testing" "$(fixture spec src/a.spec.js:x)" testing
check "jest.config.* → testing" "$(fixture jestcfg jest.config.cjs:x)" testing
check "package.json 只含 next → frontend-security" "$(fixture nextonly 'package.json:{"dependencies":{"next":"14"}}')" frontend-security

echo "[組合與排除]"
check "Next + TS + 測試：依表順序輸出" \
  "$(fixture combo tsconfig.json:{} next.config.mjs:x src/a.spec.ts:x 'package.json:{"dependencies":{"next":"14","react":"18"}}')" \
  "typescript react nextjs testing frontend-security"
check "monorepo：frontend/package.json 含 react 也算" "$(fixture mono 'package.json:{"name":"root"}' 'frontend/package.json:{"dependencies":{"react":"18"}}')" "react frontend-security"
check "node_modules 裡的 package.json 不算" "$(fixture depspkg 'node_modules/x/package.json:{"dependencies":{"react":"18"}}')" ""
check "node_modules 裡的檔案不算" "$(fixture deps node_modules/x/index.ts:x node_modules/x/a.test.js:x)" ""
check "venv / .venv / dist / vendor / third_party / .pnpm-store 裡的檔案不算" \
  "$(fixture skipdirs venv/lib/a.py:x .venv/lib/a.py:x dist/index.d.ts:x vendor/p/a.test.js:x third_party/x/setup.py:x .pnpm-store/v3/a.ts:x)" ""
check "三層 monorepo：apps/web 的 react 與 next.config 一起偵測到" \
  "$(fixture apps 'package.json:{"name":"root"}' 'apps/web/package.json:{"dependencies":{"react":"18","next":"14"}}' apps/web/next.config.js:x)" \
  "react nextjs frontend-security"
check "package.json 只在描述裡提到 react 不算" "$(fixture mention 'package.json:{"description":"not a react app"}')" ""
check "空目錄 → 無輸出" "$(fixture empty)" ""
bash "$TOOL" "$SANDBOX/nope" >/dev/null 2>&1
check "目錄不存在 → exit 2" "$?" 2

echo "[與 SKILL.md Phase 0 表一致（防漂移）]"
table_rules=$(sed -n '/^## Phase 0/,/^\*\*偵測方式/p' "$SKILL" | grep -oE '@rules/[a-z-]+\.md' | sed -E 's|@rules/||; s|\.md||' | grep -vx git | sort -u)
# 只算非註解行的 emit（註解裡寫 emit python 不能冒充實作）
script_rules=$(grep -vE '^[[:space:]]*#' "$TOOL" | grep -oE 'emit [a-z-]+$' | awk '{print $2}' | sort -u)
check "表裡的 rules（git 除外）= script 會輸出的 rules" "$(paste -sd' ' - <<<"$script_rules")" "$(paste -sd' ' - <<<"$table_rules")"
# 條件層級：表裡每個偵測條件（反引號內，去掉引號）都要出現在 script 的非註解行——表加了 "svelte" 而 script 沒跟上就紅
script_code=$(grep -vE '^[[:space:]]*#' "$TOOL")
missing=$(sed -n '/^## Phase 0/,/^\*\*偵測方式/p' "$SKILL" | grep '^| `' | grep -v '@rules/git\.md' | cut -d'|' -f2 \
  | grep -oE '`[^`]+`' | tr -d '`"' | sort -u | while IFS= read -r condition; do
      [[ "$condition" == .git/ ]] && continue
      grep -qF -- "$condition" <<<"$script_code" || echo "$condition"
    done | paste -sd' ' -)
check "表裡每個偵測條件都出現在 script" "$missing" ""
grep -qF 'detect-stack.sh' "$SKILL" && pass "SKILL.md fallback 呼叫 detect-stack.sh" || fail "SKILL.md fallback 呼叫 detect-stack.sh"

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
