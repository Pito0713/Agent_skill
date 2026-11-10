#!/usr/bin/env bash
# test-project-review.sh — project-review.py 與 install-project-review-schedule.sh 的測試。
# 全部用 mktemp 造假 repo / 登記表 / 交接檔，不碰真實 HOME，也不會真的跳通知。
#
# 用法：bash bin/test-project-review.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/project-review-test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
OUT=""
RC=0

pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
assert_equals() { if [[ "$1" == "$2" ]]; then pass "$3"; else fail "$3（期望 '$2'，實際 '$1'）"; fi; }
assert_contains() { if printf '%s' "$OUT" | grep -qF -- "$1"; then pass "$2"; else fail "$2（缺少：$1）"; fi; }

REPO="$SANDBOX/repo"
REPORTS="$SANDBOX/reports"
SESSIONS="$SANDBOX/sessions"
CONFIG="$SANDBOX/projects.json"
NOTIFY_LOG="$SANDBOX/notify.log"
STATUS="$REPORTS/demo/status.json"

export PROJECT_REVIEW_CONFIG="$CONFIG" PROJECT_REVIEW_REPORT_DIR="$REPORTS" PROJECT_REVIEW_SESSIONS_DIR="$SESSIONS"
export PROJECT_REVIEW_NOTIFY_CMD="$SANDBOX/fake-notify.sh"
printf '#!/usr/bin/env bash\necho "$1|$2" >>"%s"\n' "$NOTIFY_LOG" >"$PROJECT_REVIEW_NOTIFY_CMD"
chmod +x "$PROJECT_REVIEW_NOTIFY_CMD"

commit_file() {
  echo "$2" >"$REPO/$1"
  git -C "$REPO" add -- "$1" && git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm "$1"
}

# $1 = checks JSON 物件；$2 = 額外欄位（可省略）
write_config() {
  printf '{"projects":[{"name":"demo","path":"%s","checks":%s%s}]}\n' "$REPO" "$1" "${2:-}" >"$CONFIG"
}

run_review() {
  OUT=$(PROJECT_REVIEW_TODAY="$1" python3 "$SCRIPT_DIR/project-review.py" "${@:2}" 2>&1); RC=$?
}

field() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print($2)" "$STATUS"; }

mkdir -p "$REPO" "$SESSIONS/demo"
git -C "$REPO" init -q
commit_file app.txt v1

echo "== 1. 首次執行：全部通過 =="
write_config '{"test":"test -f app.txt","lint":"true"}'
run_review 2026-11-10
assert_equals "$RC" "0" "exit 0"
assert_equals "$(field x 'd["l1"]["result"]')" "pass" "L1 pass"
assert_equals "$(field x 'd["overall"]')" "ok" "overall ok"
assert_equals "$(field x 'd["changed"]')" "True" "首次視為有變更"
assert_equals "$(git -C "$REPO" worktree list | wc -l | tr -d ' ')" "1" "worktree 快照已清掉"
[[ -f "$REPORTS/demo/2026-11-10.md" ]] && pass "報告已產出" || fail "報告未產出"

echo "== 2. 同一天再跑：略過；--force 且無新 commit：idle、沿用 =="
run_review 2026-11-10
assert_contains "今天已跑過" "同日略過"
run_review 2026-11-10 --force
assert_equals "$(field x 'd["overall"]')" "idle" "無變更 → idle"
assert_equals "$(field x 'd["l1"]["carried"]')" "True" "L1 沿用上次"

echo "== 3. 未 commit 的變更不影響檢查（跑在快照上）=="
write_config '{"test":"test ! -f dirty.txt"}'
commit_file app.txt v2
echo dirty >"$REPO/dirty.txt"
run_review 2026-11-11
assert_equals "$(field x 'd["l1"]["result"]')" "pass" "快照不含工作區的 dirty.txt"
rm -f "$REPO/dirty.txt"

echo "== 4. 失敗：fail、通知；隔天無新 commit 仍是 fail（不被藏成 idle）=="
write_config '{"test":"false"}'
commit_file app.txt v3
: >"$NOTIFY_LOG"
run_review 2026-11-12
assert_equals "$(field x 'd["overall"]')" "fail" "overall fail"
assert_equals "$(field x '",".join(d["l1"]["failed"])')" "test" "failed 列出 test"
OUT=$(cat "$NOTIFY_LOG"); assert_contains "demo：測試失敗" "有發通知"
: >"$NOTIFY_LOG"
run_review 2026-11-13
assert_equals "$(field x 'd["overall"]')" "fail" "沿用的失敗仍是 fail"
assert_equals "$(wc -c <"$NOTIFY_LOG" | tr -d ' ')" "0" "沿用的失敗不重複通知"

echo "== 5. flaky：第一次失敗、重跑通過 =="
COUNTER="$SANDBOX/flaky-counter"
write_config "{\"test\":\"echo x >>$COUNTER; [ \$(wc -l <$COUNTER) -ge 2 ]\"}"
commit_file app.txt v4
run_review 2026-11-14
assert_equals "$(field x 'd["l1"]["result"]')" "flaky" "L1 flaky"
assert_equals "$(field x 'd["overall"]')" "warn" "overall warn"

echo "== 6. 逾時 → crash，基準 commit 不推進，下次重試 =="
ORPHAN_MARK="$SANDBOX/orphan-mark"
write_config "{\"test\":\"(sleep 3; touch $ORPHAN_MARK) & sleep 5\"}" ',"timeoutSeconds":1'
commit_file app.txt v5
run_review 2026-11-15
assert_equals "$(field x 'd["l1"]["result"]')" "crash" "逾時 → crash"
sleep 3
[[ ! -e "$ORPHAN_MARK" ]] && pass "逾時連子程序一起殺掉" || fail "逾時後子程序仍在跑"
write_config '{"test":"true"}'
run_review 2026-11-15
assert_equals "$(field x 'd["l1"]["result"]')" "pass" "crash 後同日可重試且重新跑檢查"

echo "== 7. 指令不存在 → crash；沒設定檢查 → none =="
write_config '{"test":"no-such-command-xyz"}'
commit_file app.txt v6
run_review 2026-11-16
assert_equals "$(field x 'd["l1"]["result"]')" "crash" "exit 127 → crash"
write_config '{}'
run_review 2026-11-16 --force
assert_equals "$(field x 'd["l1"]["result"]')" "none" "沒設定檢查 → none"

echo "== 8. 交接落後 commit 數 =="
printf '# demo\n\n> 最後更新：2000-01-01 00:00\n' >"$SESSIONS/demo/latest.md"
commit_file app.txt v7
run_review 2026-11-17
assert_equals "$(field x 'd["handoff"]["updatedAt"]')" "2000-01-01 00:00" "解析交接時間"
assert_equals "$(field x 'd["handoff"]["lagCommits"]')" "$(git -C "$REPO" rev-list --count HEAD)" "落後數 = 之後所有 commit"
[[ "$(cat "$SESSIONS/demo/latest.md")" == $'# demo\n\n> 最後更新：2000-01-01 00:00' ]] && pass "交接檔未被改寫" || fail "交接檔被改寫"

echo "== 9. 非 git 路徑 → crash；登記表壞掉 → exit 1 =="
printf '{"projects":[{"name":"demo","path":"%s","checks":{"test":"true"}}]}\n' "$SANDBOX/nope" >"$CONFIG"
run_review 2026-11-18
assert_equals "$(field x 'd["overall"]')" "crash" "非 git 路徑 → crash"
echo '{"projects":[{"name":"../x","path":"/tmp"}]}' >"$CONFIG"
run_review 2026-11-18
assert_equals "$RC" "1" "name 含 / → exit 1"
rm -f "$CONFIG"
run_review 2026-11-18
assert_equals "$RC" "1" "找不到登記表 → exit 1"

echo "== 10. installer dry-run =="
OUT=$(PROJECT_REVIEW_LAUNCH_AGENTS_DIR="$SANDBOX/agents" bash "$SCRIPT_DIR/install-project-review-schedule.sh" --dry-run 2>&1); RC=$?
assert_equals "$RC" "0" "dry-run exit 0"
assert_contains "<string>local.agent-skill.project-review</string>" "label 正確"
assert_contains "<integer>9</integer>" "每天 09 點"
[[ ! -e "$SANDBOX/agents" ]] && pass "dry-run 沒寫檔" || fail "dry-run 寫了檔"
OUT=$(HOME="$SANDBOX/home" PROJECT_REVIEW_LAUNCHCTL=true PROJECT_REVIEW_LAUNCH_AGENTS_DIR="$SANDBOX/agents" \
  bash "$SCRIPT_DIR/install-project-review-schedule.sh" 2>&1)
plutil -lint "$SANDBOX/agents/local.agent-skill.project-review.plist" >/dev/null && pass "plist 格式合法" || fail "plist 不合法"

echo
echo "PASS $PASS_COUNT / FAIL $FAIL_COUNT"
if [[ $FAIL_COUNT -eq 0 ]]; then echo "ALL TESTS PASSED"; exit 0; fi
exit 1
