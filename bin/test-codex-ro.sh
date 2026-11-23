#!/usr/bin/env bash
# test-codex-ro.sh — bin/codex-ro.sh 的測試。用假 codex 記錄參數與 stdin，不會真的呼叫 codex。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/codex-ro.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
check() { [[ "$2" == "$3" ]] && pass "$1" || fail "${1}（實際：${2}）"; }

# 假 codex：參數一行一個寫到 args.txt，stdin 寫到 stdin.txt（讀到 EOF；被卡住就會被外層逾時抓到）
FAKE="$SANDBOX/fake-codex"
cat >"$FAKE" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >"$SANDBOX/args.txt"
cat >"$SANDBOX/stdin.txt"
exit 7
EOF
chmod +x "$FAKE"

# run <stdin 來源> <args…>：stdin 來源為 none（不接、模擬背景執行繼承一條永不關閉的 pipe）或資料字串
run() {
  local input="$1"; shift
  rm -f "$SANDBOX/args.txt" "$SANDBOX/stdin.txt"
  if [[ "$input" == none ]]; then
    # 一條寫端不關閉的 FIFO：若 wrapper 沒接 </dev/null，假 codex 的 cat 會永遠等
    mkfifo "$SANDBOX/fifo"; sleep 30 >"$SANDBOX/fifo" & local holder=$!
    CODEX_RO_COMMAND="$FAKE" bash "$TOOL" "$@" <"$SANDBOX/fifo" 2>"$SANDBOX/err" & local pid=$!
    local waited=0; while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 50 ]]; do sleep 0.1; waited=$((waited + 1)); done
    if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null; RC=hang; else wait "$pid"; RC=$?; fi
    kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null; rm -f "$SANDBOX/fifo"
  else
    printf '%s' "$input" | CODEX_RO_COMMAND="$FAKE" bash "$TOOL" "$@" 2>"$SANDBOX/err"; RC=$?
  fi
  ARGS=$(cat "$SANDBOX/args.txt" 2>/dev/null)
}
has_arg_pair() { awk -v a="$1" -v b="$2" 'prev==a && $0==b {found=1} {prev=$0} END {exit !found}' "$SANDBOX/args.txt"; }

echo "[stdin]"
run none "審查這個"
check "沒寫 --stdin：stdin 不繼承、不會卡住（回傳 codex 的 exit 7）" "$RC" 7
check "沒寫 --stdin：codex 收到的 stdin 是空的" "$(cat "$SANDBOX/stdin.txt" 2>/dev/null)" ""
run "diff 內容" --stdin "審查 <stdin>"
check "--stdin：資料完整傳給 codex" "$(cat "$SANDBOX/stdin.txt")" "diff 內容"

echo "[安全旗標]"
run none "p"
has_arg_pair -s read-only && pass "每次都帶 -s read-only" || fail "每次都帶 -s read-only"
has_arg_pair -c project_doc_max_bytes=0 && pass "每次都帶 project_doc_max_bytes=0" || fail "每次都帶 project_doc_max_bytes=0"
check "第一個參數是 exec" "$(head -n 1 "$SANDBOX/args.txt")" exec
check "prompt 是最後一個參數" "$(tail -n 1 "$SANDBOX/args.txt")" p
check "prompt 前一定是 --（codex 不會把 prompt 當旗標解析）" "$(tail -n 2 "$SANDBOX/args.txt" | head -n 1)" --
grep -qx 'tools.web_search=true' <<<"$ARGS" && fail "沒寫 --web 不開網搜" || pass "沒寫 --web 不開網搜"
run none --web "搜尋 X"
has_arg_pair -c tools.web_search=true && pass "--web 才開網搜" || fail "--web 才開網搜"
run none -o "$SANDBOX/out.md" --skip-git-repo-check "p"
has_arg_pair -o "$SANDBOX/out.md" && pass "-o 原樣傳給 codex" || fail "-o 原樣傳給 codex"

echo "[拒絕]"
for flag in "-s" "--sandbox" "--dangerously-bypass-approvals-and-sandbox" "--full-auto" "-m"; do
  run none "$flag" x "p"
  check "拒絕旗標 ${flag} → exit 2 且沒呼叫 codex" "$RC:$([[ -e "$SANDBOX/args.txt" ]] && echo called)" "2:"
done
run none
check "缺 prompt → exit 2" "$RC" 2
run none "a" "b"
check "兩段 prompt → exit 2" "$RC" 2
for injected in "--dangerously-bypass-approvals-and-sandbox" "-cproject_doc_max_bytes=99999"; do
  run none -- "$injected"
  check "以 - 開頭的 prompt（${injected}）在 codex 端前面有 --、只當文字" "$RC:$(tail -n 2 "$SANDBOX/args.txt" | paste -sd' ' -)" "7:-- ${injected}"
done
run none first -- second
check "first -- second → exit 2（不靜默丟掉 first）" "$RC" 2
run none "" second
check "空字串也算一個 prompt：'' second → exit 2" "$RC" 2
run none ""
check "只有空 prompt → exit 2" "$RC" 2
OUT=$(CODEX_RO_COMMAND="$SANDBOX/no-such-codex" bash "$TOOL" "p" 2>&1 </dev/null); RC=$?
check "找不到 codex → exit 127 並指向 fallback" "$RC:$(grep -c 'Fallback' <<<"$OUT")" "127:1"

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
