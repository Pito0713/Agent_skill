#!/usr/bin/env bash
# codex-ro.sh — codex 唯讀委派的唯一入口（計劃書 plans/t6-bash-extraction.md C4）
#
# 用法：codex-ro.sh [--web] [--stdin] [-o 輸出檔] [-C 目錄] [--skip-git-repo-check] [--] "<prompt>"
#   --web     開網路搜尋（cli-delegate 模式 A）
#   --stdin   把本程式的 stdin 餵給 codex（例：git diff | codex-ro.sh --stdin "審查 <stdin> …"）
#   -o FILE   只把最後一則訊息寫到 FILE（codex --output-last-message）
#
# 為什麼要有這支：安全旗標是逐次帶的，每處手寫都可能漏；沒給 stdin 的非互動呼叫會卡在
# 「Reading additional input from stdin...」（lessons 2026-11-22，背景並行時卡 40 分鐘）。
# 本程式讓兩件事都不可能發生：
#   - 固定帶 -s read-only 與 -c project_doc_max_bytes=0（不載 AGENTS.md，見 cli-delegate Step 2）
#   - 沒寫 --stdin 一律接 </dev/null。用顯式旗標不用偵測：背景執行時 [ -t 0 ] 判不準
# 其他 codex 旗標一律拒絕（-s、--dangerously-*、--full-auto 等）——要放寬權限不該經過這裡。
#
# exit：codex 本身的 exit code；2 = 參數錯誤；127 = 找不到 codex（改走 cli-delegate 的 Claude subagent fallback）

set -u

CODEX_COMMAND="${CODEX_RO_COMMAND:-codex}"   # 測試用：換成假 codex

usage_error() {
  echo "codex-ro: $1" >&2
  echo "用法：codex-ro.sh [--web] [--stdin] [-o 輸出檔] [-C 目錄] [--skip-git-repo-check] [--] \"<prompt>\"" >&2
  exit 2
}

use_web=false
use_stdin=false
passthrough=()
prompt=""
prompt_count=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --web) use_web=true; shift ;;
    --stdin) use_stdin=true; shift ;;
    -o|-C) [[ $# -ge 2 ]] || usage_error "$1 缺值"; passthrough+=("$1" "$2"); shift 2 ;;
    --skip-git-repo-check) passthrough+=("$1"); shift ;;
    --) shift; [[ $# -eq 1 ]] || usage_error "-- 之後必須剛好一個 prompt"; prompt="$1"; prompt_count=$((prompt_count + 1)); shift ;;
    -*) usage_error "不接受的旗標：$1（本程式只做唯讀委派，放寬權限不該經過這裡）" ;;
    *) prompt="$1"; prompt_count=$((prompt_count + 1)); shift ;;
  esac
done
# 用計數不用「是否為空」判斷：'' 也算一個 prompt，first -- second 也不能靜默丟掉 first
[[ $prompt_count -eq 1 ]] || usage_error "必須剛好一個 prompt（目前 ${prompt_count} 個；多段文字請用引號包成一個）"
[[ -n "$prompt" ]] || usage_error "prompt 是空的"

command -v "$CODEX_COMMAND" >/dev/null 2>&1 || {
  echo "codex-ro: 找不到 ${CODEX_COMMAND}——改走 cli-delegate 的 Claude Subagent Fallback（交叉驗證不得跳過）" >&2
  exit 127
}

arguments=(exec -s read-only -c project_doc_max_bytes=0)
$use_web && arguments+=(-c tools.web_search=true)
[[ ${#passthrough[@]} -gt 0 ]] && arguments+=("${passthrough[@]}")
# prompt 前一律加 --：否則以 - 開頭的 prompt 會被 codex 當成旗標（例：--dangerously-*、-cproject_doc_max_bytes=…）
arguments+=(-- "$prompt")

if $use_stdin; then
  exec "$CODEX_COMMAND" "${arguments[@]}"
fi
exec "$CODEX_COMMAND" "${arguments[@]}" </dev/null
