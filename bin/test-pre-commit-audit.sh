#!/usr/bin/env bash
# test-pre-commit-audit.sh — hooks/pre-commit-audit.sh 的回歸測試。
# 每個案例在 mktemp -d 的臨時 repo 裡 stage 一行內容，直接執行 hook 檢查 exit code 與輸出。
# 臨時 repo 沒有 skills/index.json，所以只會跑到「路徑 lint」與「延後註解提醒」兩段。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../hooks/pre-commit-audit.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }

# 用 printf 組字串，避免本檔自身的新增行觸發 hook
PERSONAL_PATH=$(printf '/%s/%s/project' 'Users' 'someone')
DEFERRED_WORD=$(printf '%s%s' 'TO' 'DO')
DEFERRED_ZH=$(printf '%s%s' '暫' '時')
DEFERRED_FOR_NOW=$(printf '%s %s' 'For' 'now')

# run_case <名稱> <檔名> <內容>：建新 repo、stage 內容、跑 hook，結果在 RC / OUT
run_case() {
  local repo="$SANDBOX/$1"
  git init -q "$repo"
  printf '%s\n' "$3" >"$repo/$2"
  git -C "$repo" add "$2"
  OUT=$(cd "$repo" && bash "$HOOK" 2>&1)
  RC=$?
}

expect() {
  local description="$1" expected_rc="$2" pattern="$3" should_match="$4"
  [[ "$RC" == "$expected_rc" ]] || { fail "$description（exit ${RC}，預期 ${expected_rc}）"; return; }
  if [[ "$should_match" == yes ]]; then
    grep -qF -- "$pattern" <<<"$OUT" && pass "$description" || fail "$description（輸出缺「${pattern}」）"
  else
    grep -qF -- "$pattern" <<<"$OUT" && fail "$description（輸出不應含「${pattern}」）" || pass "$description"
  fi
}

echo "[路徑 lint 回歸]"
run_case path-hit a.sh "cd ${PERSONAL_PATH}"
expect "個人絕對路徑 → 擋下" 1 "staged 內容含個人絕對路徑" yes
run_case path-bypass a.sh "cd ${PERSONAL_PATH}  # audit-ok"
expect "路徑加 audit-ok → 放行" 0 "個人絕對路徑" no
run_case path-substring a.sh "cd ${PERSONAL_PATH}  # audit-oklahoma"
expect "audit-oklahoma 不算旁路 → 擋下" 1 "staged 內容含個人絕對路徑" yes

echo "[延後註解提醒]"
run_case todo-hit a.py "# ${DEFERRED_WORD}: 之後再處理錯誤"
expect "英文延後關鍵字 → 提醒但 exit 0" 0 "延後註解" yes
run_case zh-hit a.py "# ${DEFERRED_ZH}跳過驗證"
expect "中文延後關鍵字 → 提醒" 0 "延後註解" yes
run_case fornow-hit a.py "# ${DEFERRED_FOR_NOW} just return None"
expect "英文片語不分大小寫 → 提醒" 0 "延後註解" yes
run_case clean a.py "return parse_config(path)"
expect "一般程式碼 → 無提醒" 0 "延後註解" no
run_case word-boundary a.py "todolist = load_${DEFERRED_WORD}S()"
expect "關鍵字只是更長識別字的一部分 → 無提醒" 0 "延後註解" no
run_case todo-bypass a.py "# ${DEFERRED_WORD}: known  audit-ok"
expect "延後註解加 audit-ok → 無提醒" 0 "延後註解" no
run_case both a.py "# ${DEFERRED_WORD} cd ${PERSONAL_PATH}"
expect "同行含路徑與延後註解 → 路徑優先擋下" 1 "staged 內容含個人絕對路徑" yes

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
