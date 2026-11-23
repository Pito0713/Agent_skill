#!/usr/bin/env bash
# test-knowledge-grep.sh — bin/knowledge-grep.sh 的測試。fixture 全在 mktemp -d，不讀真實 knowledge/ 或 vault。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/knowledge-grep.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }

check() {
  local description="$1" actual="$2" expected="$3"
  [[ "$actual" == "$expected" ]] && pass "$description" || fail "${description}（實際：${actual//$'\n'/ | }）"
}

KNOWLEDGE="$SANDBOX/knowledge"
VAULT="$SANDBOX/vault with space"
mkdir -p "$KNOWLEDGE/tech" "$VAULT/notes"
printf 'docker env container\n' >"$KNOWLEDGE/tech/docker env.md"
printf 'docker only\n' >"$KNOWLEDGE/tech/docker.md"
printf 'nothing here\n' >"$KNOWLEDGE/tech/other.md"
printf 'Docker in vault, C++ too\n' >"$VAULT/notes/My Note.md"
printf 'docker\n' >"$KNOWLEDGE/tech/ignored.txt"

# run <args…>：結果在 OUT / RC
run() { OUT=$(KNOWLEDGE_GREP_REPO_ROOT="$KNOWLEDGE" OBSIDIAN_VAULT_PATH="$VAULT" bash "$TOOL" "$@" 2>"$SANDBOX/err"); RC=$?; }
run_without_vault() { OUT=$(KNOWLEDGE_GREP_REPO_ROOT="$KNOWLEDGE" OBSIDIAN_VAULT_PATH='' bash "$TOOL" "$@" 2>"$SANDBOX/err"); RC=$?; }

echo "[排序與空格檔名]"
run --source knowledge docker env container
check "命中關鍵字多的排前面" "$OUT" "$KNOWLEDGE/tech/docker env.md
$KNOWLEDGE/tech/docker.md"
check "有命中 exit 0" "$RC" 0
run --source vault docker
check "vault 路徑與檔名含空格不被切斷" "$OUT" "$VAULT/notes/My Note.md"
run docker
check "both：兩個根目錄都搜、只搜 .md" "$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')" 3
run --top 1 docker
check "--top 限制筆數" "$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')" 1

echo "[比對方式]"
run --source vault DOCKER
check "不分大小寫" "$OUT" "$VAULT/notes/My Note.md"
run --source vault 'C++'
check "關鍵字當字面字串（不當 regex）" "$OUT" "$VAULT/notes/My Note.md"
run --source knowledge 'd.cker'
check "regex 字元不會模糊比對 → 無命中 exit 1" "$RC" 1

echo "[錯誤處理]"
run_without_vault --source vault docker
check "vault 未設定且 --source vault → exit 2" "$RC" 2
run_without_vault docker
check "both 且 vault 未設定 → 只搜 knowledge 並提醒" "$RC:$(grep -c '只搜 knowledge' "$SANDBOX/err")" "0:1"
run --source nowhere docker
check "--source 不合法 → exit 2" "$RC" 2
run --top 0 docker
check "--top 0 → exit 2" "$RC" 2
run --source knowledge
check "沒有關鍵字 → exit 2" "$RC" 2
OUT=$(KNOWLEDGE_GREP_REPO_ROOT="$KNOWLEDGE" OBSIDIAN_VAULT_PATH="$SANDBOX/missing" bash "$TOOL" --source vault docker 2>/dev/null); RC=$?
check "vault 目錄不存在 → exit 2" "$RC" 2

run --top 00 docker
check "--top 00 → exit 2（macOS head 不接受）" "$RC" 2
run --top 10000 docker
check "--top 超過 4 位數 → exit 2" "$RC" 2

echo "[讀取錯誤]"
LOCKED="$SANDBOX/locked"
mkdir -p "$LOCKED/sub" && printf 'secret\n' >"$LOCKED/sub/a.md" && chmod 000 "$LOCKED/sub"
OUT=$(KNOWLEDGE_GREP_REPO_ROOT="$LOCKED" bash "$TOOL" --source knowledge secret 2>"$SANDBOX/err"); RC=$?
check "讀不到且無命中 → exit 2 並警告（不偽裝成無命中）" "$RC:$(grep -c '無法讀取' "$SANDBOX/err")" "2:1"
printf 'secret\n' >"$LOCKED/b.md"
OUT=$(KNOWLEDGE_GREP_REPO_ROOT="$LOCKED" bash "$TOOL" --source knowledge secret 2>"$SANDBOX/err"); RC=$?
check "部分可讀有命中 → exit 0 + 警告" "$RC:$(grep -c '無法讀取' "$SANDBOX/err")" "0:1"
chmod 755 "$LOCKED/sub"

echo "[SKILL.md 呼叫方式]"
# 模擬 Phase 0：source .env 只設 shell 變數、不 export；SKILL 要明確傳入才收得到
SKILL_OUT=$(env -u OBSIDIAN_VAULT_PATH bash -c '
  OBSIDIAN_VAULT_PATH="$1"; SOURCE=vault
  HITS=$(OBSIDIAN_VAULT_PATH="$OBSIDIAN_VAULT_PATH" "$2" --source "$SOURCE" --top 5 docker); GREP_EXIT=$?
  UNIQUE_FILES=(); while IFS= read -r f; do [ -n "$f" ] && UNIQUE_FILES+=("$f"); done <<< "$HITS"
  echo "$GREP_EXIT:${#UNIQUE_FILES[@]}:${UNIQUE_FILES[0]}"' _ "$VAULT" "$TOOL" 2>/dev/null)
check "未 export 的 vault 變數經明確傳入可用，空格路徑完整" "$SKILL_OUT" "0:1:$VAULT/notes/My Note.md"
SKILL_OUT=$(env -u OBSIDIAN_VAULT_PATH bash -c '
  HITS=$(OBSIDIAN_VAULT_PATH="" "$1" --source vault docker); GREP_EXIT=$?; echo "$GREP_EXIT"' _ "$TOOL" 2>/dev/null)
check "設定錯誤時 GREP_EXIT 保留 2（不被 while 迴圈吃掉）" "$SKILL_OUT" 2

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
