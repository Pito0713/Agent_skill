#!/usr/bin/env bash
# knowledge-grep.sh — knowledge-search skill Phase 2 的確定性搜尋（計劃書 agent-env-trust-pyramid T6 C2）
#
# 用法：knowledge-grep.sh [--source knowledge|vault|both] [--top N] 關鍵字 [關鍵字…]
# 輸出：命中檔案路徑，一行一個，依「命中的關鍵字數」由多到少排序，同分依路徑排序
# exit：0 有命中 / 1 無命中 / 2 參數、設定或讀取錯誤（有命中但部分檔案讀不到 → exit 0 + stderr 警告）
#
# 為什麼抽成 script：原本內嵌在 SKILL.md 的寫法用 `($(…))` 與 `awk '{print $2}'`
# 取檔名，遇到含空格的檔名會被切斷（Obsidian 筆記檔名常含空格，2026-11-22 實測）。
# 關鍵字一律當字面字串（grep -F），避免 C++、a.b 這類詞被當成 regex。
# 已知限制：路徑以換行分隔，檔名本身含換行字元時會被拆成兩筆（刻意接受，實務上不會出現）。
#
# 環境變數：
#   OBSIDIAN_VAULT_PATH        vault 根目錄（--source vault / both 用）
#   KNOWLEDGE_GREP_REPO_ROOT   取代 repo 的 knowledge/ 根目錄（測試用）

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KNOWLEDGE_ROOT="${KNOWLEDGE_GREP_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)/knowledge}"
DEFAULT_TOP=5

usage_error() {
  echo "knowledge-grep: $1" >&2
  echo "用法：knowledge-grep.sh [--source knowledge|vault|both] [--top N] 關鍵字 [關鍵字…]" >&2
  exit 2
}

# 依 source 把要搜的根目錄寫到 stdout，一行一個
resolve_roots() {
  local source="$1" vault="${OBSIDIAN_VAULT_PATH:-}"
  if [[ "$source" != vault ]]; then
    [[ -d "$KNOWLEDGE_ROOT" ]] || usage_error "找不到 knowledge 目錄：${KNOWLEDGE_ROOT}"
    echo "$KNOWLEDGE_ROOT"
  fi
  [[ "$source" == knowledge ]] && return 0
  if [[ -z "$vault" ]]; then
    [[ "$source" == vault ]] && usage_error "OBSIDIAN_VAULT_PATH 未設定"
    echo "knowledge-grep: OBSIDIAN_VAULT_PATH 未設定，只搜 knowledge/" >&2
    return 0
  fi
  [[ -d "$vault" ]] || usage_error "找不到 vault 目錄：${vault}"
  echo "$vault"
}

source_name=both
top="$DEFAULT_TOP"
keywords=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || usage_error "--source 缺值"; source_name="$2"; shift 2 ;;
    --top) [[ $# -ge 2 ]] || usage_error "--top 缺值"; top="$2"; shift 2 ;;
    --) shift; keywords+=("$@"); break ;;
    -*) usage_error "未知參數：$1" ;;
    *) keywords+=("$1"); shift ;;
  esac
done

case "$source_name" in knowledge|vault|both) ;; *) usage_error "--source 只能是 knowledge / vault / both" ;; esac
# 上限 4 位數：macOS head 不接受 00 這類寫法，也不接受過大的數字
case "$top" in [1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]) ;; *) usage_error "--top 必須是 1–9999 的整數" ;; esac
[[ ${#keywords[@]} -gt 0 ]] || usage_error "至少要一個關鍵字"

# resolve_roots 的 usage_error 在 subshell 內 exit，必須用回傳值把錯誤帶回主程式
root_list=$(resolve_roots "$source_name") || exit 2
roots=()
while IFS= read -r root; do [[ -n "$root" ]] && roots+=("$root"); done <<<"$root_list"
[[ ${#roots[@]} -gt 0 ]] || exit 2

# 每個 (根目錄, 關鍵字) 的 grep -l 對同一檔只列一次 → 同一路徑出現幾次 = 命中幾個關鍵字
# grep 的讀取錯誤（權限等）不能吞掉：吞掉會把「搜不完整」偽裝成「無命中」
error_file=$(mktemp)
trap 'rm -f "$error_file"' EXIT
results=$(
  for root in "${roots[@]}"; do
    for keyword in "${keywords[@]}"; do
      grep -rliF --include='*.md' -- "$keyword" "$root" 2>>"$error_file"
    done
  done | sort | uniq -c | sed -E 's/^ *([0-9]+) /\1	/' | sort -t '	' -k1,1nr -k2,2 | cut -f2- | head -n "$top"
)

if [[ -s "$error_file" ]]; then
  echo "knowledge-grep: 部分檔案無法讀取，結果可能不完整：" >&2
  head -n 5 "$error_file" >&2
  [[ -n "$results" ]] || exit 2
fi
[[ -n "$results" ]] || exit 1
printf '%s\n' "$results"
