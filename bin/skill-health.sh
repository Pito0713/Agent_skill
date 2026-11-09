#!/usr/bin/env bash
# skill-health.sh — skill 制度體檢（A 層）：唯讀跑 A1–A10，寫 Markdown 報告，與上次比對。
#
# 對應 maintenance-protocol §7 版本（2026-11 現況）：
#   第 1 查 = 四份索引（CLAUDE.md / CLAUDE.global.md / AGENTS.md / GEMINI.md）各 ≤150 行、AGENTS.md ≤16KB
#   第 2 查 = 三條全域 symlink；第 3 查 = 四個 inline 段；第 4 查 = 路由檔案存在
# 之後改 §7（例如新增第 5 查）要同步改本檔。規格：plans/skill-health-check.md §2、§3、§4 T1/T3。
#
# 用法：bash bin/skill-health.sh
# 只讀：不改 repo、不 fetch；唯一的寫入是報告目錄。體檢發現問題仍 exit 0（只出報告）。
#
# 環境變數（皆可選）：
#   SKILL_HEALTH_REPO            要檢查的 repo 根（預設：本腳本所在 repo）
#   SKILL_HEALTH_HOME            A3 symlink 與 A7 下游掃描用的 HOME（預設 $HOME）
#   SKILL_HEALTH_REPORT_DIR      報告目錄（預設 $HOME/.agent-reports/skill-health）
#   SKILL_HEALTH_DATE            報告日期 YYYY-MM-DD（預設今天；測試用）
#   SKILL_HEALTH_SKIP_DOWNSTREAM 設為 1 略過 A7
#   SKILL_HEALTH_NOTIFY          設為 off 停用通知
#   SKILL_HEALTH_NOTIFY_CMD      取代 osascript 的通知指令，以「標題 內容」兩個參數呼叫
#   SKILL_HEALTH_KEEP            保留份數（預設 26）
#
# 檢查函式慣例（在 set -e 子 shell 內跑）：stdout 首行 = 摘要、其餘 = 明細；
# return 0 = ✅、10 = ⚠️、11 = ❌；任何其他結果（含未預期失敗）= 💥 檢查失敗。

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${SKILL_HEALTH_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
HOME_DIR="${SKILL_HEALTH_HOME:-$HOME}"
REPORT_DIR="${SKILL_HEALTH_REPORT_DIR:-$HOME/.agent-reports/skill-health}"
REPORT_DATE="${SKILL_HEALTH_DATE:-$(date +%Y-%m-%d)}"
KEEP_COUNT="${SKILL_HEALTH_KEEP:-26}"
INDEX_LINE_LIMIT=150
AGENTS_BYTE_LIMIT=16384
CODE_LINE_LIMIT=300
INLINE_SECTIONS=("常駐核心規則" "核心鐵律" "記憶與交接" "溝通規範")
CHECK_IDS=(A1 A2 A3 A4 A5 A6 A7 A8 A9 A10)

log_message() { printf 'skill-health: %s\n' "$*" >&2; }

# 把工具輸出限制在合理行數，避免報告被單一工具洗版
limit_lines() { awk -v limit="${1:-20}" 'NR <= limit'; }

check_a1_index_consistency() {
  local tool="$REPO/bin/validate-skill-index.py" output rc
  [[ -f "$tool" ]] || { echo "工具不存在：$tool" >&2; return 127; }
  output=$(python3 "$tool" 2>&1) && rc=0 || rc=$?
  if [[ $rc -eq 0 ]]; then echo "validate-skill-index.py 通過"; return 0; fi
  if [[ $rc -ne 1 ]]; then echo "validate-skill-index.py 非預期 exit ${rc}：$output" >&2; return 70; fi
  echo "validate-skill-index.py exit 1（索引不一致）"
  printf '%s\n' "$output" | limit_lines 30
  return 11
}

check_a2_index_sizes() {
  local name lines bytes problems="" detail=""
  for name in CLAUDE.md CLAUDE.global.md AGENTS.md GEMINI.md; do
    lines=$(wc -l <"$REPO/$name" | tr -d ' ')
    detail="$detail$name: $lines 行"$'\n'
    [[ $lines -le $INDEX_LINE_LIMIT ]] || problems="$problems$name 超過 $INDEX_LINE_LIMIT 行（${lines}）；"
  done
  bytes=$(wc -c <"$REPO/AGENTS.md" | tr -d ' ')
  detail="${detail}AGENTS.md: $bytes bytes"
  [[ $bytes -le $AGENTS_BYTE_LIMIT ]] || problems="${problems}AGENTS.md 超過 $AGENTS_BYTE_LIMIT bytes（${bytes}）；"
  if [[ -z "$problems" ]]; then echo "四份索引皆 ≤${INDEX_LINE_LIMIT} 行，AGENTS.md ${bytes} bytes"; echo "$detail"; return 0; fi
  echo "$problems"; echo "$detail"
  return 11
}

check_a3_global_symlinks() {
  local link target problems="" link_names=(.claude/CLAUDE.md .codex/AGENTS.md .gemini/GEMINI.md)
  for link in "${link_names[@]}"; do
    if [[ ! -L "$HOME_DIR/$link" ]]; then problems="$problems~/$link 不是 symlink；"; continue; fi
    target=$(readlink "$HOME_DIR/$link")
    case "$target" in "$HOME_DIR/Agent_skill/"*) ;; *) problems="$problems~/$link 指向 ${target}（非 ~/Agent_skill/）；"; continue ;; esac
    [[ -e "$HOME_DIR/$link" ]] || problems="$problems~/$link 斷線（$target 不存在）；"
  done
  if [[ -z "$problems" ]]; then echo "三條全域 symlink 皆指向 ~/Agent_skill/ 且健在"; return 0; fi
  echo "$problems"
  return 11
}

extract_inline_section() { sed -n "/^## $1/,/^---\$/p" "$2"; }

check_a4_inline_sections() {
  local section drifted="" detail=""
  for section in "${INLINE_SECTIONS[@]}"; do
    if ! diff <(extract_inline_section "$section" "$REPO/AGENTS.md") \
              <(extract_inline_section "$section" "$REPO/GEMINI.md") >/dev/null; then
      drifted="${drifted}「${section}」"
      detail="$detail--- 段落「${section}」diff（AGENTS.md < > GEMINI.md）"$'\n'
      detail="$detail$(diff <(extract_inline_section "$section" "$REPO/AGENTS.md") \
                            <(extract_inline_section "$section" "$REPO/GEMINI.md") | limit_lines 20 || true)"$'\n'
    fi
  done
  if [[ -z "$drifted" ]]; then echo "四個 inline 段逐字相同"; return 0; fi
  echo "inline 段漂移：${drifted}（AGENTS.md 與 GEMINI.md 不同）"
  printf '%s' "$detail"
  return 11
}

check_a5_routes_exist() {
  local route missing="" total=0
  # 路由寫 ~/Agent_skill/...，對應到被檢查的 repo 根（worktree 或假 repo 也能檢查）
  while IFS= read -r route; do
    [[ -n "$route" ]] || continue
    total=$((total + 1))
    [[ -e "$REPO/${route#\~/Agent_skill/}" ]] || missing="$missing$route"$'\n'
  done < <(grep -ohE '~/Agent_skill/[a-zA-Z0-9/_.-]+\.(md|txt)' "$REPO/AGENTS.md" "$REPO/GEMINI.md" | sort -u)
  if [[ -z "$missing" ]]; then echo "路由 OK（$total 個檔案皆存在）"; return 0; fi
  echo "路由指向的檔案缺失"
  printf '%s' "$missing"
  return 11
}

check_a6_token_budget() {
  local tool="$REPO/bin/token-budget.sh" json
  [[ -f "$tool" ]] || { echo "工具不存在：$tool" >&2; return 127; }
  json=$(bash "$tool" --json) || { echo "token-budget.sh --json 失敗" >&2; return 70; }
  printf '%s' "$json" | python3 "$SCRIPT_DIR/skill_health_checks.py" budget
}

check_a7_downstream_farms() {
  local tool="$REPO/bin/scan-downstream.sh" output
  if [[ "${SKILL_HEALTH_SKIP_DOWNSTREAM:-0}" == "1" ]]; then echo "略過（SKILL_HEALTH_SKIP_DOWNSTREAM=1）"; return 0; fi
  [[ -f "$tool" ]] || { echo "工具不存在：$tool" >&2; return 127; }
  # stderr（不存在的下游目錄提示）丟棄：缺目錄不是 dangling；真失敗看 exit code
  output=$(HOME="$HOME_DIR" bash "$tool" 2>/dev/null) || { echo "scan-downstream.sh 非預期 exit" >&2; return 70; }
  if [[ "$output" == "✅ 無 dangling" ]]; then echo "下游無 dangling symlink"; return 0; fi
  echo "下游 skill farm 有 $(printf '%s\n' "$output" | wc -l | tr -d ' ') 個 dangling symlink"
  printf '%s\n' "$output" | limit_lines 30
  return 10
}

check_a8_long_code_files() {
  local file lines count=0 listing=""
  cd "$REPO"
  while IFS= read -r -d '' file; do
    lines=$(wc -l <"$file" | tr -d ' ')
    if [[ $lines -gt $CODE_LINE_LIMIT ]]; then count=$((count + 1)); listing="$listing${file}（${lines}）"$'\n'; fi
  done < <(find skills bin -type f \( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.ts' -o -name '*.tsx' \) \
             -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -not -path '*/.venv/*' -print0)
  if [[ $count -eq 0 ]]; then echo "skills/ 與 bin/ 無超過 ${CODE_LINE_LIMIT} 行的程式檔"; return 0; fi
  echo "$count 個程式檔超過 ${CODE_LINE_LIMIT} 行"
  printf '%s' "$listing" | sort
  return 10
}

check_a9_skill_path_references() {
  python3 "$SCRIPT_DIR/skill_health_checks.py" paths "$REPO"
}

# A10 只陳述不判定；只用 git status -sb（不 fetch，不寫 .git）
check_a10_repo_state() {
  local status branch_line changes
  status=$(git -C "$REPO" status -sb)
  branch_line=$(printf '%s\n' "$status" | sed -n 1p)
  changes=$(printf '%s\n' "$status" | tail -n +2 | grep -c . || true)
  echo "$branch_line · 未 commit 變更 $changes 項"
  printf '%s\n' "$status" | tail -n +2 | limit_lines 30
  return 0
}

run_check() {
  local id="$1" function_name="$2" rc
  ( set -eu -o pipefail; "$function_name" ) >"$RESULTS_DIR/$id.out" 2>"$RESULTS_DIR/$id.err"
  rc=$?
  case $rc in
    0) echo ok ;;
    10) echo warn ;;
    11) echo fail ;;
    *) echo crash; [[ -s "$RESULTS_DIR/$id.err" ]] || echo "檢查函式 exit $rc" >"$RESULTS_DIR/$id.err" ;;
  esac >"$RESULTS_DIR/$id.status"
}

run_all_checks() {
  run_check A1 check_a1_index_consistency
  run_check A2 check_a2_index_sizes
  run_check A3 check_a3_global_symlinks
  run_check A4 check_a4_inline_sections
  run_check A5 check_a5_routes_exist
  run_check A6 check_a6_token_budget
  run_check A7 check_a7_downstream_farms
  run_check A8 check_a8_long_code_files
  run_check A9 check_a9_skill_path_references
  run_check A10 check_a10_repo_state
}

# 只刪檔名符合 YYYY-MM-DD.md 的檔案，保留最新 KEEP_COUNT 份
prune_old_reports() {
  local names total excess stale
  names=$(ls "$REPORT_DIR" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' | sort || true)
  total=$(printf '%s\n' "$names" | grep -c . || true)
  excess=$((total - KEEP_COUNT))
  [[ $excess -gt 0 ]] || return 0
  for stale in $(printf '%s\n' "$names" | head -n "$excess"); do
    rm -f "$REPORT_DIR/$stale" || log_message "刪除舊報告失敗：$stale"
  done
}

# 通知失敗只記 log，不影響報告與 exit code
send_notification() {
  local message="$1" notify_log="$REPORT_DIR/notify.log"
  [[ "${SKILL_HEALTH_NOTIFY:-on}" != "off" ]] || return 0
  if [[ -n "${SKILL_HEALTH_NOTIFY_CMD:-}" ]]; then
    "$SKILL_HEALTH_NOTIFY_CMD" "Skill 體檢" "$message" 2>>"$notify_log" || log_message "通知指令失敗（詳見 ${notify_log}）"
    return 0
  fi
  osascript -e 'on run argv' -e 'display notification (item 1 of argv) with title (item 2 of argv)' -e 'end run' \
    -- "$message" "Skill 體檢" 2>>"$notify_log" || log_message "osascript 通知失敗（詳見 ${notify_log}）"
  return 0
}

main() {
  local commit summary_file report_path
  [[ $# -eq 0 ]] || { log_message "未知參數：$1（本版僅 A 層，無旗標）"; return 64; }
  RESULTS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/skill-health.XXXXXX") || return 1
  trap 'rm -rf "$RESULTS_DIR"' EXIT
  mkdir -p "$REPORT_DIR" || { log_message "無法建立報告目錄：$REPORT_DIR"; return 1; }

  commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)
  run_all_checks
  summary_file="$RESULTS_DIR/summary.txt"
  report_path="$REPORT_DIR/$REPORT_DATE.md"
  python3 "$SCRIPT_DIR/skill_health_report.py" --results "$RESULTS_DIR" --report-dir "$REPORT_DIR" \
    --date "$REPORT_DATE" --commit "$commit" --summary-out "$summary_file" || { log_message "報告產生失敗"; return 1; }

  prune_old_reports
  cat "$report_path"
  send_notification "$(cat "$summary_file") — $report_path"
  return 0
}

main "$@"
