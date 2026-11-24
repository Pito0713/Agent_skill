#!/usr/bin/env bash
# test-pre-commit-audit.sh — hooks/pre-commit-audit.sh 的回歸測試。
# 每個案例在 mktemp -d 的臨時 repo 裡 stage 一行內容，直接執行 hook 檢查 exit code 與輸出。
# run_case 的臨時 repo 沒有 skills/index.json，只跑到 index 檢查之前的各段；TEST_MAP 段另用 run_map_case 建 stub。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../hooks/pre-commit-audit.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

# hermetic：不吃使用者的全域 / 系統 git 設定（例如 core.excludesFile 忽略 *.py 會讓 fixture stage 不進去）
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

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
  git init -q "$repo" || { echo "fixture 失敗：git init $1" >&2; exit 2; }
  printf '%s\n' "$3" >"$repo/$2"
  git -C "$repo" add "$2" || { echo "fixture 失敗：git add $1" >&2; exit 2; }
  git -C "$repo" diff --cached --quiet && { echo "fixture 失敗：$1 沒有 staged 內容" >&2; exit 2; }
  OUT=$(cd "$repo" && bash "$HOOK" 2>&1)
  RC=$?
}

expect() {
  local description="$1" expected_rc="$2" pattern="$3" should_match="$4"
  [[ "$RC" == "$expected_rc" ]] || { fail "${description}（exit ${RC}，預期 ${expected_rc}）"; return; }
  if [[ "$should_match" == yes ]]; then
    grep -qF -- "$pattern" <<<"$OUT" && pass "$description" || fail "${description}（輸出缺「${pattern}」）"
  else
    grep -qF -- "$pattern" <<<"$OUT" && fail "${description}（輸出不應含「${pattern}」）" || pass "$description"
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

echo "[顯示：多位元組截斷]"
LONG_ZH=$(printf '%.0s暫' $(seq 1 60))
# 前綴 9 bytes（"# " + 4 + " ab"）讓第 100 byte 落在中文字元中間；前綴 7 bytes 會剛好對齊而驗不到
run_case utf8 a.py "# ${DEFERRED_WORD} ab${LONG_ZH}"
printf '%s' "$OUT" | iconv -f UTF-8 -t UTF-8 >/dev/null 2>&1 && pass "長中文行截斷後仍是合法 UTF-8" || fail "長中文行截斷後仍是合法 UTF-8"
expect "長中文行仍正常提醒" 0 "延後註解" yes

echo "[shell 變數緊接多位元組字元（W2）]"
# 用 printf 組字串，避免本檔自身的新增行觸發這條提醒
DOLLAR='$'
ZH_COMMA=$(printf '\357\274\214')   # 全形逗號「，」的 UTF-8 bytes
run_case bare-hit a.sh "echo \"${DOLLAR}hp${ZH_COMMA}略過\""
expect "裸 \$VAR 後接全形標點 → 提醒但 exit 0" 0 "shell 變數後面緊接多位元組字元" yes
run_case braced a.sh "echo \"${DOLLAR}{hp}${ZH_COMMA}略過\""
expect "\${VAR} 大括號寫法 → 無提醒" 0 "shell 變數後面緊接多位元組字元" no
run_case comment a.sh "# 例：${DOLLAR}hp${ZH_COMMA}會崩"
expect "註解行 → 無提醒" 0 "shell 變數後面緊接多位元組字元" no
run_case escaped a.sh "echo \"\\${DOLLAR}HOME${ZH_COMMA}字面\""
expect "跳脫的字面 \\\$ → 無提醒" 0 "shell 變數後面緊接多位元組字元" no
run_case ascii a.sh "echo \"${DOLLAR}hp, ok\"	${DOLLAR}x	y"
expect "後接 ASCII 標點或 tab → 無提醒" 0 "shell 變數後面緊接多位元組字元" no
run_case not-shell a.py "print(\"${DOLLAR}hp${ZH_COMMA}\")"
expect "非 shell 檔 → 不檢查" 0 "shell 變數後面緊接多位元組字元" no
run_case double-backslash a.sh "echo \"\\\\${DOLLAR}hp${ZH_COMMA}會崩\""
expect "偶數個反斜線（\\\\\$VAR 仍會展開）→ 照樣提醒" 0 "shell 變數後面緊接多位元組字元" yes

echo "[改到哪支跑哪支測試（W3 段 1）]"
# 臨時 repo 要有 skills/index.json 與可執行的 validator 才會走到 TEST_MAP 段；validator 用 stub
# run_map_case <名稱> <假測試的 exit code> <要 stage 的檔>：bin/test-codex-ro.sh 是假測試，會留下執行標記
run_map_case() {
  local repo="$SANDBOX/$1"
  git init -q "$repo" || { echo "fixture 失敗：git init $1" >&2; exit 2; }
  mkdir -p "$repo/skills" "$repo/bin"
  printf '{"skills": []}\n' >"$repo/skills/index.json"
  printf '#!/bin/sh\nexit 0\n' >"$repo/bin/validate-skill-index.py"; chmod +x "$repo/bin/validate-skill-index.py"
  printf 'touch "%s/ran"\necho "  FAIL  假測試案例"\nexit %s\n' "$repo" "$2" >"$repo/bin/test-codex-ro.sh"
  mkdir -p "$repo/$(dirname "$3")"; echo x >"$repo/$3"
  git -C "$repo" add "$3" || { echo "fixture 失敗：git add $1" >&2; exit 2; }
  OUT=$(cd "$repo" && bash "$HOOK" 2>&1); RC=$?
  RAN=$([[ -e "$repo/ran" ]] && echo yes || echo no)
}
run_map_case map-fail 1 bin/codex-ro.sh
expect "對應測試失敗 → 擋下並指出哪支" 1 "相關測試失敗 bin/test-codex-ro.sh" yes
run_map_case map-pass 0 bin/codex-ro.sh
expect "對應測試通過 → 放行並回報" 0 "bin/test-codex-ro.sh 通過" yes
[[ "$RAN" == yes ]] && pass "對應測試真的被執行" || fail "對應測試真的被執行"
run_map_case map-unrelated 1 bin/other.sh
expect "沒碰到對照表的檔 → 不跑測試、放行" 0 "相關測試失敗" no
[[ "$RAN" == no ]] && pass "無關檔案不觸發測試" || fail "無關檔案不觸發測試"

echo "[skill 裡直接寫 codex exec（skill 體檢 B2）]"
# 跟 TEST_MAP 段一樣要有 skills/index.json 與 validator stub 才會走到本段；stage 的是 skills/ 檔，
# hook 會用 python3 真的執行 validator，所以 stub 要是合法 Python
# run_codex_case <名稱> <檔名> <內容>
CODEX_EXEC=$(printf '%s %s' 'codex' 'exec')
run_codex_case() {
  local repo="$SANDBOX/$1"
  git init -q "$repo" || { echo "fixture 失敗：git init $1" >&2; exit 2; }
  mkdir -p "$repo/skills" "$repo/bin" "$repo/$(dirname "$2")"
  printf '{"skills": []}\n' >"$repo/skills/index.json"
  printf 'import sys\nsys.exit(0)\n' >"$repo/bin/validate-skill-index.py"; chmod +x "$repo/bin/validate-skill-index.py"
  printf '%s\n' "$3" >"$repo/$2"
  git -C "$repo" add "$2" || { echo "fixture 失敗：git add $1" >&2; exit 2; }
  OUT=$(cd "$repo" && bash "$HOOK" 2>&1); RC=$?
}
run_codex_case codex-pipe skills/x/SKILL.md "git diff | ${CODEX_EXEC} -s read-only \"審查\""
expect "skill 內 pipe 給 codex exec → 擋" 1 "直接寫 codex exec" yes
run_codex_case codex-template governance/delegation-templates.md "${CODEX_EXEC} \"prompt\""
expect "派工模板直接呼叫 → 擋" 1 "直接寫 codex exec" yes
run_codex_case codex-eol skills/x/SKILL.md "最後跑 ${CODEX_EXEC}"
expect "行尾的 codex exec（沒有反引號）→ 擋" 1 "直接寫 codex exec" yes
run_codex_case codex-backtick skills/x/SKILL.md "**不要直接寫 \`${CODEX_EXEC}\`**，一律呼叫 wrapper"
expect "反引號包住的說明文字 → 放行" 0 "直接寫 codex exec" no
run_codex_case codex-bypass skills/x/SKILL.md "${CODEX_EXEC} -s read-only  # audit-ok"
expect "audit-ok 標記 → 放行" 0 "直接寫 codex exec" no
run_codex_case codex-wrapper skills/x/SKILL.md "git diff | ~/Agent_skill/bin/codex-ro.sh --stdin -- \"審查\""
expect "經 wrapper 呼叫 → 放行" 0 "直接寫 codex exec" no
run_codex_case codex-outside governance/model-orchestration.md "${CODEX_EXEC} -s read-only \"x\""
expect "範圍外的制度檔 → 不檢查" 0 "直接寫 codex exec" no

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
