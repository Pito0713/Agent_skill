#!/usr/bin/env bash
# skill_health_review.sh — skill-health.sh 的 B 層（模型審查），由 skill-health.sh source 進來。
# 規格：plans/skill-health-check.md §2 B 層、§4 T2。
#
# 需要呼叫端已定義：REPO、SCRIPT_DIR、REPORT_DIR、REPORT_DATE、RESULTS_DIR、log_message。
# 環境變數（皆可選）：
#   SKILL_HEALTH_CLAUDE_CMD       claude 指令（預設 claude；測試用假指令）
#   SKILL_HEALTH_REVIEW_TIMEOUT   逾時秒數（預設 600）
#
# 模型只給 Read/Grep/Glob；git diff 與 skill-usage 由本檔先算好塞進 prompt。
# 結果寫到 $RESULTS_DIR/B.status（ok|crash）、B.out（模型輸出）、B.err（失敗原因）。
# 失敗一律標 crash（報告顯示 💥），不得當通過或靜默略過。

REVIEW_PROMPT_TEMPLATE="$SCRIPT_DIR/skill-health-review.md"
REVIEW_DEFAULT_TIMEOUT=600
REVIEW_DIFF_MAX_LINES=300
REVIEW_FALLBACK_LESSON_LINES=80
REVIEW_USAGE_MAX_LINES=150
REVIEW_ALLOWED_TOOLS="Read,Grep,Glob"

# 上一份報告（日期早於今天）記錄的 commit；沒有或不合法就不輸出
find_previous_report_commit() {
  local previous
  previous=$(ls "$REPORT_DIR" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' | sort \
    | awk -v today="$REPORT_DATE.md" '$0 < today' | tail -n 1)
  [[ -n "$previous" ]] || return 0
  sed -n 's/.*"commit": "\([0-9a-f]\{4,40\}\)".*/\1/p' "$REPORT_DIR/$previous" | head -n 1
}

emit_recent_lessons() {
  local lessons="$REPO/governance/lessons.md"
  if [[ -f "$lessons" ]]; then tail -n "$REVIEW_FALLBACK_LESSON_LINES" "$lessons"; else echo "（governance/lessons.md 不存在）"; fi
}

emit_lessons_context() {
  local commit diff
  commit=$(find_previous_report_commit)
  if [[ -z "$commit" ]]; then
    echo "（首次執行或上份報告無可用 commit：改提供 governance/lessons.md 最近 ${REVIEW_FALLBACK_LESSON_LINES} 行）"
    emit_recent_lessons; return 0
  fi
  if ! git -C "$REPO" cat-file -e "${commit}^{commit}" 2>/dev/null; then
    echo "（上份報告的 commit ${commit} 在本 repo 找不到：改提供 governance/lessons.md 最近 ${REVIEW_FALLBACK_LESSON_LINES} 行）"
    emit_recent_lessons; return 0
  fi
  diff=$(git -C "$REPO" diff "$commit" -- governance/lessons.md | head -n "$REVIEW_DIFF_MAX_LINES")
  echo "（上份報告基準 commit：${commit}；以下為 governance/lessons.md 自該 commit 起的 git diff，最多 ${REVIEW_DIFF_MAX_LINES} 行）"
  if [[ -n "$diff" ]]; then printf '%s\n' "$diff"; else echo "（無新增或變更）"; fi
}

emit_usage_context() {
  local tool="$REPO/bin/skill-usage.py" output
  if [[ ! -f "$tool" ]]; then echo "（無觀測資料：bin/skill-usage.py 不存在）"; return 0; fi
  if output=$(python3 "$tool" --days 28 2>&1); then
    printf '%s\n' "$output" | head -n "$REVIEW_USAGE_MAX_LINES"
  else
    echo "（無觀測資料：skill-usage.py 執行失敗）"; printf '%s\n' "$output" | head -n 10
  fi
}

# 模板 + 外層算好的資料 → prompt 檔
build_review_prompt() {
  local prompt_file="$1"
  [[ -f "$REVIEW_PROMPT_TEMPLATE" ]] || { echo "找不到 prompt 模板：$REVIEW_PROMPT_TEMPLATE" >&2; return 1; }
  {
    cat "$REVIEW_PROMPT_TEMPLATE"
    printf '\n---\n\n# 外層提供的資料（唯讀；repo 根目錄：%s）\n\n## B2 輸入\n\n' "$REPO"
    emit_lessons_context
    printf '\n## B3 輸入\n\n'
    emit_usage_context
  } >"$prompt_file"
}

# 背景執行 + 輪詢逾時（macOS 沒有 GNU timeout）。逾時回 124。
run_with_timeout() {
  local seconds="$1" prompt_file="$2" out_file="$3" err_file="$4" pid elapsed=0 rc
  shift 4
  "$@" <"$prompt_file" >"$out_file" 2>"$err_file" &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if [[ $elapsed -ge $seconds ]]; then
      kill -TERM "$pid" 2>/dev/null; sleep 1; kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 1; elapsed=$((elapsed + 1))
  done
  wait "$pid"; rc=$?
  return "$rc"
}

mark_review_failed() {
  echo crash >"$RESULTS_DIR/B.status"
  printf '%s\n' "$1" >"$RESULTS_DIR/B.err"
  [[ -z "${2:-}" ]] || printf '%s\n' "$2" | tail -n 10 >>"$RESULTS_DIR/B.err"
  log_message "B 層失敗：$1"
}

run_review_layer() {
  local command_name="${SKILL_HEALTH_CLAUDE_CMD:-claude}" seconds="${SKILL_HEALTH_REVIEW_TIMEOUT:-$REVIEW_DEFAULT_TIMEOUT}"
  local command_path prompt_file="$RESULTS_DIR/B.prompt" out_file="$RESULTS_DIR/B.out" err_file="$RESULTS_DIR/B.stderr" rc=0
  case "$seconds" in ''|*[!0-9]*) mark_review_failed "SKILL_HEALTH_REVIEW_TIMEOUT 不是正整數：$seconds"; return 0 ;; esac
  command_path=$(command -v "$command_name") || { mark_review_failed "找不到 ${command_name} 指令（不在 PATH）"; return 0; }
  build_review_prompt "$prompt_file" 2>"$err_file" || { mark_review_failed "無法產生 prompt" "$(cat "$err_file")"; return 0; }
  ( cd "$REPO" && run_with_timeout "$seconds" "$prompt_file" "$out_file" "$err_file" \
      "$command_path" -p --allowedTools "$REVIEW_ALLOWED_TOOLS" ) || rc=$?
  if [[ $rc -eq 124 ]]; then mark_review_failed "逾時（超過 ${seconds} 秒，已終止）" "$(cat "$err_file")"; return 0; fi
  if [[ $rc -ne 0 ]]; then mark_review_failed "claude 指令非 0 exit（${rc}）" "$(cat "$err_file")"; return 0; fi
  if ! grep -q '[^[:space:]]' "$out_file"; then mark_review_failed "claude 指令輸出為空" "$(cat "$err_file")"; return 0; fi
  echo ok >"$RESULTS_DIR/B.status"
}
