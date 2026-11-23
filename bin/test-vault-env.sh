#!/usr/bin/env bash
# test-vault-env.sh — bin/vault-env.sh 的測試。.env 與 vault 全在 mktemp -d，不讀真實 ~/Agent_skill/.env。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/vault-env.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
check() { [[ "$2" == "$3" ]] && pass "$1" || fail "${1}（實際：${2}）"; }

ENV_FILE="$SANDBOX/.env"
# 沒引號的值遇到空格會被 source 截斷，所以無引號案例用 PLAIN；含空格的路徑只出現在引號 / 跳脫案例
VAULT="$SANDBOX/plain-vault"
SPACED="$SANDBOX/My Vault"
mkdir -p "$VAULT" "$SPACED" "$SANDBOX/home/notes"
VAULT_REAL=$(cd "$VAULT" && pwd)
SPACED_REAL=$(cd "$SPACED" && pwd)

# run <.env 內容或 NONE> [--optional]：結果在 OUT / RC / ERR
run() {
  rm -f "$ENV_FILE"
  [[ "$1" == NONE ]] || printf '%s\n' "$1" >"$ENV_FILE"
  shift
  OUT=$(env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" bash "$TOOL" "$@" 2>"$SANDBOX/err"); RC=$?
  ERR=$(cat "$SANDBOX/err")
}

echo "[解析]"
run "OBSIDIAN_VAULT_PATH=$VAULT"
check "一般寫法 → 印絕對路徑 exit 0" "$RC:$OUT" "0:$VAULT_REAL"
run "OBSIDIAN_VAULT_PATH=\"$SPACED\""
check "雙引號包住（路徑含空格）" "$OUT" "$SPACED_REAL"
run "OBSIDIAN_VAULT_PATH='$SPACED'"
check "單引號包住（路徑含空格）" "$OUT" "$SPACED_REAL"
run "OBSIDIAN_VAULT_PATH=$SPACED"
check "沒引號又含空格 → 跟 source 一樣在空格截斷 → 找不到 exit 1" "$RC" 1
run "export OBSIDIAN_VAULT_PATH=$VAULT"
check "export 前綴" "$OUT" "$VAULT_REAL"
run "OBSIDIAN_VAULT_PATH=~/notes"
check "開頭的 ~ 展開成 HOME" "$OUT" "$(cd "$SANDBOX/home/notes" && pwd)"
run "$(printf 'OBSIDIAN_VAULT_PATH=%s\r' "$VAULT")"
check "Windows 換行（CRLF）" "$OUT" "$VAULT_REAL"
run "$(printf '# 註解\nOBSIDIAN_VAULT_PATH=/old\nOBSIDIAN_VAULT_PATH=%s' "$VAULT")"
check "重複定義取最後一個（同 source 語意）" "$OUT" "$VAULT_REAL"

echo "[解析：與 source 一致（codex/subagent 審查補案例）]"
# 對照組：同一份 .env 用真的 source 解析，結果必須相同
source_value() { env -i HOME="$SANDBOX/home" /bin/bash -c 'source "$1" 2>/dev/null; printf %s "$OBSIDIAN_VAULT_PATH"' _ "$ENV_FILE"; }
mkdir -p "$SANDBOX/home/n" "$SANDBOX/My Vault2"
for content in \
  "OBSIDIAN_VAULT_PATH=$VAULT_REAL # 行內註解" \
  "OBSIDIAN_VAULT_PATH=\"$VAULT_REAL\" # 引號後註解" \
  "OBSIDIAN_VAULT_PATH=$VAULT_REAL   " \
  "$(printf 'OBSIDIAN_VAULT_PATH=%s\t' "$VAULT_REAL")" \
  "OBSIDIAN_VAULT_PATH=\"$VAULT_REAL\"   " \
  "$(printf 'OBSIDIAN_VAULT_PATH=%s # c\r' "$VAULT_REAL")" \
  'OBSIDIAN_VAULT_PATH=$HOME/n' \
  'OBSIDIAN_VAULT_PATH="${HOME}/n"' \
  "OBSIDIAN_VAULT_PATH=${SANDBOX}/My\\ Vault2"; do
  run "$content"
  expected=$(source_value); expected_real=""
  [[ -n "$expected" ]] && expected_real=$(cd "$expected" 2>/dev/null && pwd)
  check "與 source 一致：$(printf '%s' "${content#OBSIDIAN_VAULT_PATH=}" | tr '\t\r' 'TR' | sed "s|$SANDBOX|…|g")" "$OUT" "$expected_real"
done
run "OBSIDIAN_VAULT_PATH='\$HOME/n'"
check "單引號內的 \$HOME 不展開（同 source）" "$RC" 1
run 'OBSIDIAN_VAULT_PATH="~/n"'
check "引號內的 ~ 不展開（同 source）" "$RC" 1
printf 'OBSIDIAN_VAULT_PATH=%s' "$VAULT" >"$ENV_FILE"
OUT=$(env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" bash "$TOOL" 2>/dev/null)
check "最後一行沒有換行" "$OUT" "$VAULT_REAL"

echo "[跳脫與邊界：與 source 一致（C1 codex 審查）]"
# 字面的 $HOME / ~ 目錄真的存在，展開錯了就會選到另一個目錄
mkdir -p "$SANDBOX/cwd2/\$HOME/n" "$SANDBOX/cwd2/~/n" "$SANDBOX/cwd2/a\"b"
for content in \
  'OBSIDIAN_VAULT_PATH=\$HOME/n' \
  'OBSIDIAN_VAULT_PATH="\$HOME/n"' \
  'OBSIDIAN_VAULT_PATH=\~/n' \
  'OBSIDIAN_VAULT_PATH="a\"b"' \
  'OBSIDIAN_VAULT_PATH="$HOME"/n' ; do
  rm -f "$ENV_FILE"; printf '%s\n' "$content" >"$ENV_FILE"
  OUT=$(cd "$SANDBOX/cwd2" && env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" bash "$TOOL" 2>/dev/null); RC=$?
  expected=$(cd "$SANDBOX/cwd2" && source_value); expected_real=$(cd "$SANDBOX/cwd2" && cd "$expected" 2>/dev/null && pwd)
  if [[ "$content" == *'"/n' ]]; then
    check "引號接字串（${content}）→ 不猜、拒絕" "$RC" 1
  else
    check "與 source 一致：${content#OBSIDIAN_VAULT_PATH=}" "$RC:$OUT" "0:$expected_real"
  fi
done

echo "[不支援的寫法：拒絕，不回傳另一個存在的目錄]"
# 每個案例的「錯誤解讀」都指向真的存在的目錄：舊版會成功回傳它
mkdir -p "$SANDBOX/tmpx" "$SANDBOX/home/n_BACKUP" "$SANDBOX/My"
mkdir -p "$SANDBOX/home_BACKUP/n"
for content in \
  "OBSIDIAN_VAULT_PATH=\"$SANDBOX/tmpx\"/notes" \
  "OBSIDIAN_VAULT_PATH='$SANDBOX/tmpx'/notes" \
  'OBSIDIAN_VAULT_PATH=$HOME_BACKUP/n' \
  "OBSIDIAN_VAULT_PATH=$SANDBOX/My Vault" \
  'OBSIDIAN_VAULT_PATH=$OTHER/n' \
  'OBSIDIAN_VAULT_PATH="`pwd`"' \
  'OBSIDIAN_VAULT_PATH="unterminated' ; do
  run "$content"
  check "拒絕：$(printf '%s' "${content#OBSIDIAN_VAULT_PATH=}" | sed "s|$SANDBOX|…|g")" "$RC:$OUT:$(grep -c '格式不支援' <<<"$ERR")" "1::1"
  run "$content" --optional
  check "拒絕 + --optional → 靜默" "$RC:$OUT:$ERR" "0::"
done

echo "[環境變數與權限]"
OUT=$(OBSIDIAN_VAULT_PATH="$VAULT" HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$SANDBOX/none" bash "$TOOL" --optional 2>/dev/null)
check ".env 不存在但環境變數有設 → 沿用（同 source 2>/dev/null）" "$OUT" "$VAULT_REAL"
printf 'OTHER=1\n' >"$ENV_FILE"
OUT=$(OBSIDIAN_VAULT_PATH="$VAULT" HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" bash "$TOOL" 2>/dev/null)
check ".env 沒定義這個變數 → 沿用環境變數" "$OUT" "$VAULT_REAL"
printf 'OBSIDIAN_VAULT_PATH=%s\n' "$VAULT" >"$ENV_FILE"; chmod 000 "$ENV_FILE"
OUT=$(env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" bash "$TOOL" 2>&1); RC=$?
check ".env 讀不到 → exit 1 並指出權限問題" "$RC:$(grep -c '無法讀取' <<<"$OUT")" "1:1"
OUT=$(env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" bash "$TOOL" --optional 2>&1); RC=$?
check ".env 讀不到 + --optional → 真的靜默" "$RC:$OUT" "0:"
chmod 644 "$ENV_FILE"
mkdir -p "$SANDBOX/cwd/-P"
OUT=$(cd "$SANDBOX/cwd" && env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$SANDBOX/dash.env" bash -c 'printf "OBSIDIAN_VAULT_PATH=-P\n" >"$AGENT_SKILL_ENV_FILE"; bash "$1"' _ "$TOOL" 2>/dev/null)
check "值以 - 開頭 → 不被 cd 當成選項" "$OUT" "$(cd "$SANDBOX/cwd/-P" && pwd)"

echo "[呼叫端寫法（SKILL.md 契約）]"
SKILLS_ROOT="$SCRIPT_DIR/../skills"
grep -qF 'VAULT_PATH=$(~/Agent_skill/bin/vault-env.sh) || exit 1' "$SKILLS_ROOT/productivity/obsidian-save/SKILL.md" \
  && pass "obsidian-save：必須有、缺設定就停" || fail "obsidian-save：必須有、缺設定就停"
# knowledge-search：不只看字串在不在，直接執行 SKILL.md 的前置＋Phase 2 兩段 bash，串到 knowledge-grep.sh
KS_SKILL="$SKILLS_ROOT/productivity/knowledge-search/SKILL.md"
ks_block() {   # 取出含指定字串的那個 ```bash 區塊
  awk -v key="$1" '/^```bash/{buf=""; on=1; next} /^```/{if(on && index(buf,key)) printf "%s", buf; on=0; next} on{buf=buf $0 "\n"}' "$KS_SKILL"
}
KS_SCRIPT="$SANDBOX/ks.sh"
{ echo 'set -u'
  ks_block 'vault-env.sh' | sed "s|~/Agent_skill/bin/|$SCRIPT_DIR/|g"
  ks_block 'knowledge-grep.sh' | sed "s|~/Agent_skill/bin/|$SCRIPT_DIR/|g; s|^KEYWORDS=.*|KEYWORDS=(needle)|"
  echo 'echo "EXIT=$GREP_EXIT"; printf "HIT=%s\n" "${UNIQUE_FILES[@]+"${UNIQUE_FILES[@]}"}"'
} >"$KS_SCRIPT"
mkdir -p "$SANDBOX/kn" && echo needle >"$SANDBOX/kn/k.md" && echo needle >"$VAULT/v.md"
ks_run() {   # ks_run <SOURCE> <.env 內容或 NONE>
  rm -f "$ENV_FILE"; [[ "$2" == NONE ]] || printf '%s\n' "$2" >"$ENV_FILE"
  OUT=$(env -u OBSIDIAN_VAULT_PATH HOME="$SANDBOX/home" AGENT_SKILL_ENV_FILE="$ENV_FILE" KNOWLEDGE_GREP_REPO_ROOT="$SANDBOX/kn" \
    SOURCE="$1" bash "$KS_SCRIPT" 2>"$SANDBOX/kserr"); RC=$?
}
ks_run vault "OBSIDIAN_VAULT_PATH=$VAULT"
check "knowledge-search vault：串到 knowledge-grep 找到 vault 筆記" "$RC:$(grep -c "HIT=.*v.md" <<<"$OUT")" "0:1"
ks_run vault NONE
check "knowledge-search vault：缺設定 → 停下（exit 1）並有設定步驟" "$RC:$(grep -c '設定步驟' "$SANDBOX/kserr")" "1:1"
ks_run both NONE
check "knowledge-search both：缺設定 → 降級只搜 knowledge，不停" "$RC:$(grep -c 'HIT=.*k.md' <<<"$OUT"):$(grep -c 'v.md' <<<"$OUT")" "0:1:0"
ks_run both "OBSIDIAN_VAULT_PATH=$VAULT"
check "knowledge-search both：有設定 → 兩邊都搜到" "$(grep -c 'HIT=' <<<"$OUT")" 2
for f in learning/_shared/mentor-protocol.md lifestyle/cooking-flow/SKILL.md; do
  grep -qF 'vault-env.sh --optional' "$SKILLS_ROOT/$f" && pass "${f}：選用（靜默降級）" || fail "${f}：選用（靜默降級）"
done
! grep -rqE 'source[^\n]*Agent_skill/\.env' "$SKILLS_ROOT" && pass "skills/ 已無 source .env" || fail "skills/ 已無 source .env"

echo "[不執行 .env]"
MARK="$SANDBOX/executed"
run "$(printf 'touch %s\nOBSIDIAN_VAULT_PATH=%s' "$MARK" "$VAULT")"
[[ ! -e "$MARK" ]] && pass ".env 裡的指令不會被執行" || fail ".env 裡的指令不會被執行"
run "OBSIDIAN_VAULT_PATH=\$(touch $MARK)"
[[ ! -e "$MARK" ]] && pass "值裡的 \$(...) 不會被執行" || fail "值裡的 \$(...) 不會被執行"
check "值裡的 \$(...) 當成路徑 → 目錄不存在 exit 1" "$RC" 1

echo "[缺設定：必須有]"
run NONE
check ".env 不存在 → exit 1" "$RC:$(grep -c '找不到' <<<"$ERR")" "1:1"
grep -q '設定步驟' <<<"$ERR" && pass "附設定步驟" || fail "附設定步驟"
run "OBSIDIAN_VAULT_PATH="
check "未填 → exit 1" "$RC:$(grep -c '尚未填入' <<<"$ERR")" "1:1"
run "OTHER=1"
check "沒有這個變數 → exit 1" "$RC" 1
run "OBSIDIAN_VAULT_PATH=$SANDBOX/missing"
check "目錄不存在 → exit 1" "$RC:$(grep -c '找不到 vault 目錄' <<<"$ERR")" "1:1"

echo "[缺設定：--optional 靜默降級]"
for content in NONE "OBSIDIAN_VAULT_PATH=" "OTHER=1" "OBSIDIAN_VAULT_PATH=$SANDBOX/missing"; do
  run "$content" --optional
  check "--optional：$( [[ $content == NONE ]] && echo '.env 不存在' || echo "${content:0:24}" ) → 無輸出 exit 0" "$RC:$OUT:$ERR" "0::"
done
run "OBSIDIAN_VAULT_PATH=$VAULT" --optional
check "--optional 有設定時照常輸出" "$OUT" "$VAULT_REAL"
run NONE --bogus
check "未知參數 → exit 2" "$RC" 2

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
