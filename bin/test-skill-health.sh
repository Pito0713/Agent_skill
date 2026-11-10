#!/usr/bin/env bash
# test-skill-health.sh — skill-health.sh 的測試。全部用 mktemp 造假 repo / HOME / 報告目錄，
# 不碰真實 HOME，也不會真的跳通知（一律 SKILL_HEALTH_NOTIFY=off 或替換通知指令）。
#
# 用法：bash bin/test-skill-health.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/skill-health-test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
OUT=""
RC=0

pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }

assert_contains() {
  if printf '%s' "$OUT" | grep -qF -- "$1"; then pass "$2"; else fail "$2（缺少：$1）"; fi
}
assert_not_contains() {
  if printf '%s' "$OUT" | grep -qF -- "$1"; then fail "$2（不該出現：$1）"; else pass "$2"; fi
}
assert_equals() {
  if [[ "$1" == "$2" ]]; then pass "$3"; else fail "$3（期望 '$2'，實際 '$1'）"; fi
}

# 造一份最小但完整、全綠的假 repo + 假 HOME
build_fake_world() {
  local world="$1" section name
  FAKE_REPO="$world/repo"; FAKE_HOME="$world/home"; FAKE_REPORTS="$world/reports"
  mkdir -p "$FAKE_REPO/bin" "$FAKE_REPO/skills/demo" "$FAKE_REPO/governance" "$FAKE_HOME/Agent_skill" "$FAKE_REPORTS"
  for name in CLAUDE.md CLAUDE.global.md; do echo "# $name" >"$FAKE_REPO/$name"; done
  for name in AGENTS.md GEMINI.md; do
    {
      echo "# index"; echo "路由 ~/Agent_skill/governance/rules.md"
      for section in 常駐核心規則 核心鐵律 記憶與交接 溝通規範; do printf '## %s\n內容\n---\n' "$section"; done
    } >"$FAKE_REPO/$name"
  done
  echo "rules" >"$FAKE_REPO/governance/rules.md"
  printf -- '---\nname: demo\n---\n參考 governance/rules.md\n' >"$FAKE_REPO/skills/demo/SKILL.md"
  # 假工具：由旗標檔控制結果，方便造 ❌ / 💥
  cat >"$FAKE_REPO/bin/validate-skill-index.py" <<'EOF'
import os, sys
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists(os.path.join(repo, ".flag-a1-fail")):
    print("MISMATCH demo"); sys.exit(1)
if os.path.exists(os.path.join(repo, ".flag-a1-crash")):
    sys.exit(3)
print("PASS")
EOF
  cat >"$FAKE_REPO/bin/token-budget.sh" <<'EOF'
#!/usr/bin/env bash
echo '{"fixed_startup_cost":{"subtotal_bytes":100,"budget_bytes":30000,"over_budget":false},"description_threshold":{"limit_bytes":400,"over":[],"stale_waivers":[]}}'
EOF
  cp "$REAL_REPO/bin/scan-downstream.sh" "$FAKE_REPO/bin/scan-downstream.sh"
  mkdir -p "$FAKE_HOME/.claude" "$FAKE_HOME/.codex" "$FAKE_HOME/.gemini"
  for name in CLAUDE.md AGENTS.md GEMINI.md; do echo "x" >"$FAKE_HOME/Agent_skill/$name"; done
  ln -s "$FAKE_HOME/Agent_skill/CLAUDE.md" "$FAKE_HOME/.claude/CLAUDE.md"
  ln -s "$FAKE_HOME/Agent_skill/AGENTS.md" "$FAKE_HOME/.codex/AGENTS.md"
  ln -s "$FAKE_HOME/Agent_skill/GEMINI.md" "$FAKE_HOME/.gemini/GEMINI.md"
  git -C "$FAKE_REPO" init -q
  git -C "$FAKE_REPO" add -A
  git -C "$FAKE_REPO" -c user.name=t -c user.email=t@example.com commit -q -m init
}

# run_health <日期> [額外 env ...]：結果在 OUT / RC
run_health() {
  local report_date="$1"; shift
  OUT=$(env SKILL_HEALTH_REPO="$FAKE_REPO" SKILL_HEALTH_HOME="$FAKE_HOME" SKILL_HEALTH_REPORT_DIR="$FAKE_REPORTS" \
    SKILL_HEALTH_DATE="$report_date" SKILL_HEALTH_NOTIFY=off "$@" bash "$SCRIPT_DIR/skill-health.sh" 2>/dev/null)
  RC=$?
}

new_world() { WORLD="$SANDBOX/world-$1"; mkdir -p "$WORLD"; build_fake_world "$WORLD"; }

test_all_green() {
  echo "[全部通過]"
  new_world green; run_health 2026-11-10
  assert_equals "$RC" 0 "exit 0"
  assert_contains "全部通過" "單行綠色摘要"
  assert_contains "（二）" "標題含星期"
  assert_equals "$(grep -c . "$FAKE_REPORTS/2026-11-10.md")" 2 "報告本體只有一行 + 機器可讀註解"
  assert_contains "skill-health-json" "stdout 含機器可讀 JSON"
}

test_single_failure() {
  echo "[單項 ❌]"
  new_world fail; touch "$FAKE_REPO/.flag-a1-fail"; run_health 2026-11-10
  assert_equals "$RC" 0 "發現問題仍 exit 0（只出報告）"
  assert_contains "❌ A1" "A1 標 ❌"
  assert_contains "A 層 ✅ 9 / ⚠️ 0 / ❌ 1 / 💥 0" "摘要行計數正確"
  assert_contains "B 層 略過（未啟用 --with-review）" "B 層固定略過"
  assert_contains "B-LAYER-INSERTION-POINT" "預留 B 層插入點"
}

test_single_crash() {
  echo "[單項 💥]"
  new_world crash; touch "$FAKE_REPO/.flag-a1-crash"; rm "$FAKE_REPO/bin/token-budget.sh"; run_health 2026-11-10
  assert_contains "💥 檢查失敗 A1" "非預期 exit → 💥（不是 ✅ 也不是 ❌）"
  assert_contains "💥 檢查失敗 A6" "工具不存在 → 💥"
  assert_contains "✅ A2" "其他檢查不中斷"
  assert_contains "A 層 ✅ 8 / ⚠️ 0 / ❌ 0 / 💥 2" "💥 計數正確"
}

test_other_checks_flag_problems() {
  echo "[A3/A4/A5/A7/A8/A9 各自能抓到問題]"
  new_world others
  rm "$FAKE_HOME/.gemini/GEMINI.md"; ln -s "$FAKE_HOME/Agent_skill/missing.md" "$FAKE_HOME/.gemini/GEMINI.md"
  perl -i -pe "s/^內容\$/不同/" "$FAKE_REPO/GEMINI.md"
  echo "路由 ~/Agent_skill/governance/ghost.md" >>"$FAKE_REPO/AGENTS.md"
  mkdir -p "$FAKE_HOME/WakaWaka/.claude/skills"; ln -s /nonexistent/skill "$FAKE_HOME/WakaWaka/.claude/skills/broken"
  seq 1 301 >"$FAKE_REPO/skills/demo/long.py"
  echo "見 rules/nope.md" >>"$FAKE_REPO/skills/demo/SKILL.md"
  run_health 2026-11-10
  assert_contains "❌ A3" "A3 斷線 → ❌"
  assert_contains "❌ A4" "A4 漂移 → ❌"
  assert_contains "❌ A5" "A5 缺檔 → ❌"
  assert_contains "⚠️ A7" "A7 dangling → ⚠️"
  assert_contains "⚠️ A8" "A8 超過 300 行 → ⚠️"
  assert_contains "⚠️ A9" "A9 引用不存在 → ⚠️"
  assert_contains "skills/demo/long.py（301）" "A8 列出檔案與行數"
}

test_a9_excludes_inbox() {
  echo "[A9 排除 skills/_inbox/ 收件匣]"
  new_world inbox
  printf '讀取 skills/_inbox/ 中的檔案\nmv skills/_inbox/new.md skills/_inbox\n' >>"$FAKE_REPO/skills/demo/SKILL.md"
  run_health 2026-11-10
  assert_contains '"A9": {"status": "ok"' "引用不存在的 skills/_inbox/ 不算缺檔"
  new_world inbox-mixed
  printf '讀取 skills/_inbox/ 中的檔案\n見 skills/ghost/SKILL.md\n' >>"$FAKE_REPO/skills/demo/SKILL.md"
  run_health 2026-11-10
  assert_contains "⚠️ A9" "_inbox 以外的缺檔仍標 ⚠️"
  assert_contains "引用 skills/ghost/SKILL.md" "_inbox 以外的缺檔仍列出"
  assert_not_contains "引用 skills/_inbox" "_inbox 不列入缺檔清單"
}

test_empty_data_not_false_green() {
  echo "[A4/A5/A8 空資料與工具失敗不得誤判通過]"
  new_world a4missing; rm "$FAKE_REPO/GEMINI.md"; run_health 2026-11-10
  assert_contains "💥 檢查失敗 A4" "A4：缺 GEMINI.md → 💥"
  assert_contains "💥 檢查失敗 A5" "A5：缺 GEMINI.md → 💥"
  new_world a4section; sed -i.bak '/^## 核心鐵律/,/^---$/d' "$FAKE_REPO/AGENTS.md" "$FAKE_REPO/GEMINI.md"; run_health 2026-11-10
  assert_contains "❌ A4" "A4：兩檔都缺「核心鐵律」→ ❌（不因兩邊相同而通過）"
  assert_contains "AGENTS.md 缺「核心鐵律」" "A4：列出 AGENTS.md 缺哪段"
  assert_contains "GEMINI.md 缺「核心鐵律」" "A4：列出 GEMINI.md 缺哪段"
  new_world a4one; sed -i.bak '/^## 溝通規範/,/^---$/d' "$FAKE_REPO/GEMINI.md"; run_health 2026-11-10
  assert_contains "GEMINI.md 缺「溝通規範」" "A4：只有一檔缺段 → ❌ 並列出"
  new_world a5zero; sed -i.bak '/Agent_skill\/governance/d' "$FAKE_REPO/AGENTS.md" "$FAKE_REPO/GEMINI.md"; run_health 2026-11-10
  assert_contains "💥 檢查失敗 A5" "A5：0 個路由 → 💥"
  new_world a8find; rm -rf "$FAKE_REPO/skills"; run_health 2026-11-10
  assert_contains "💥 檢查失敗 A8" "A8：find 失敗 → 💥"
}

test_a1_traceback_is_crash() {
  echo "[A1：Python 例外 exit 1 不得標 ❌]"
  new_world a1trace
  printf 'raise RuntimeError("boom")\n' >"$FAKE_REPO/bin/validate-skill-index.py"; run_health 2026-11-10
  assert_contains "💥 檢查失敗 A1" "A1：exit 1 含 Traceback → 💥"
  assert_not_contains "❌ A1" "A1：不標 ❌"
}

test_comparison() {
  echo "[與上次相比：新增／已解決／連續次數]"
  new_world compare
  touch "$FAKE_REPO/.flag-a1-fail"; run_health 2026-11-03
  assert_contains "首次執行" "第一份：無上次報告可比"
  run_health 2026-11-04
  assert_contains "新增：無" "第二份沒有新增"
  assert_contains "仍未處理：A1（第 2 次出現）" "連續第 2 次"
  assert_not_contains "連續 2 次未處理" "未達 3 次不醒目標出"
  seq 1 301 >"$FAKE_REPO/skills/demo/long.py"; run_health 2026-11-05
  assert_contains "新增：A8" "新增項目被列出"
  assert_contains "仍未處理：A1（第 3 次出現） 🔥 **連續 3 次未處理" "連續 ≥3 次醒目標出"
  rm "$FAKE_REPO/.flag-a1-fail"; run_health 2026-11-06
  assert_contains "已解決：A1" "已解決被列出"
  assert_contains "仍未處理：A8（第 2 次出現）" "A8 連續次數累計"
  rm "$FAKE_REPO/skills/demo/long.py"; run_health 2026-11-07
  assert_contains "已解決：A8" "全綠時單行仍帶已解決資訊"
  run_health 2026-11-07
  assert_equals "$(ls "$FAKE_REPORTS" | grep -c '\.md$')" 5 "同日重跑覆寫、不新增檔案"
}

test_previous_report_unusable() {
  echo "[上一份報告損壞或缺少機器可讀段]"
  new_world corrupt
  echo "# 舊報告
<!-- skill-health-json: {not json -->" >"$FAKE_REPORTS/2026-11-01.md"
  run_health 2026-11-02
  assert_equals "$RC" 0 "損壞的上一份不中斷"
  assert_contains "全部通過" "仍產出報告"
  echo "# 沒有 JSON 的舊報告" >"$FAKE_REPORTS/2026-11-03.md"
  touch "$FAKE_REPO/.flag-a1-fail"; run_health 2026-11-04
  assert_contains "缺少機器可讀結果，無法比對" "缺少 JSON 的處理訊息"
  echo "# 舊報告
<!-- skill-health-json: {not json -->" >"$FAKE_REPORTS/2026-11-04.md"
  run_health 2026-11-05
  assert_contains "損壞" "損壞 JSON 的處理訊息"
}

test_retention() {
  echo "[保留 26 份]"
  new_world retention
  local day
  for day in $(seq 1 30); do printf '# old\n' >"$FAKE_REPORTS/$(printf '2025-06-%02d' "$day").md"; done
  echo keep >"$FAKE_REPORTS/notes.md"; echo keep >"$FAKE_REPORTS/2025-06-01.md.bak"; echo keep >"$FAKE_REPORTS/notify.log"
  run_health 2026-11-10
  assert_equals "$(ls "$FAKE_REPORTS" | grep -cE '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$')" 26 "報告剛好 26 份"
  [[ ! -e "$FAKE_REPORTS/2025-06-01.md" && ! -e "$FAKE_REPORTS/2025-06-05.md" ]] && pass "最舊的 5 份被刪" || fail "最舊的 5 份被刪"
  [[ -e "$FAKE_REPORTS/2025-06-06.md" && -e "$FAKE_REPORTS/2026-11-10.md" ]] && pass "較新的與今天的保留" || fail "較新的與今天的保留"
  [[ -e "$FAKE_REPORTS/notes.md" && -e "$FAKE_REPORTS/2025-06-01.md.bak" && -e "$FAKE_REPORTS/notify.log" ]] \
    && pass "檔名不符格式的檔案不刪" || fail "檔名不符格式的檔案不刪"
}

test_notification() {
  echo "[通知]"
  new_world notify
  cat >"$WORLD/notify-ok.sh" <<EOF
#!/usr/bin/env bash
printf '%s|%s' "\$1" "\$2" >"$WORLD/notify-args.txt"
EOF
  printf '#!/usr/bin/env bash\necho "boom" >&2\nexit 1\n' >"$WORLD/notify-fail.sh"
  chmod +x "$WORLD/notify-ok.sh" "$WORLD/notify-fail.sh"
  run_health 2026-11-10 SKILL_HEALTH_NOTIFY=on SKILL_HEALTH_NOTIFY_CMD="$WORLD/notify-ok.sh"
  local args; args=$(cat "$WORLD/notify-args.txt")
  OUT="$args"
  assert_contains "Skill 體檢|" "通知標題"
  assert_contains "A 層 ✅ 10" "通知內容含摘要行"
  assert_contains "$FAKE_REPORTS/2026-11-10.md" "通知內容含報告路徑"
  run_health 2026-11-11 SKILL_HEALTH_NOTIFY=on SKILL_HEALTH_NOTIFY_CMD="$WORLD/notify-fail.sh"
  assert_equals "$RC" 0 "通知失敗 exit 仍為 0"
  [[ -f "$FAKE_REPORTS/2026-11-11.md" ]] && pass "通知失敗報告仍寫出" || fail "通知失敗報告仍寫出"
  grep -q boom "$FAKE_REPORTS/notify.log" && pass "失敗訊息記入 notify.log" || fail "失敗訊息記入 notify.log"
}

test_read_only() {
  echo "[唯讀：不改 repo]"
  new_world readonly; touch "$FAKE_REPO/.flag-a1-fail"
  local before after
  before=$(git -C "$FAKE_REPO" status --porcelain; git -C "$FAKE_REPO" rev-parse HEAD)
  run_health 2026-11-10
  after=$(git -C "$FAKE_REPO" status --porcelain; git -C "$FAKE_REPO" rev-parse HEAD)
  assert_equals "$after" "$before" "跑完 repo 狀態不變"
}

test_all_green
test_single_failure
test_single_crash
test_other_checks_flag_problems
test_a9_excludes_inbox
test_empty_data_not_false_green
test_a1_traceback_is_crash
test_comparison
test_previous_report_unusable
test_retention
test_notification
test_read_only

# B 層與排程安裝腳本的測試（沿用上面的 helper）
source "$SCRIPT_DIR/test-skill-health-b.sh"

echo
echo "結果：$PASS_COUNT passed, $FAIL_COUNT failed"
[[ $FAIL_COUNT -eq 0 ]]
