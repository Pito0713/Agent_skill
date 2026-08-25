#!/usr/bin/env bash
# Fixture tests for machine-readable description waivers.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$REPO/bin/token_budget_report.py"
VALIDATOR="$REPO/bin/validate-skill-index.py"
# 這是預算守門；成本偏離此基準就應讓測試紅掉、逼人決定，而非自動接受新現況。
BASELINE="$REPO/plans/baselines/20260825T033010412935+0000-55b6d87-dirty.json"
STATUS_BEFORE="$(git -C "$REPO" status --porcelain)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [[ ! -f "$BASELINE" ]]; then
  echo "FIXME: 基準 baseline 不存在，請確認 plans/baselines/: $BASELINE" >&2
  exit 1
fi

FIXTURE="$WORK/repo"
mkdir -p "$FIXTURE"
cp "$REPO/CLAUDE.md" "$FIXTURE/CLAUDE.md"
cp -R "$REPO/rules" "$FIXTURE/rules"
cp -R "$REPO/skills" "$FIXTURE/skills"

report_fixture() {
  python3 "$REPORT" "$FIXTURE" --json > "$WORK/report.json"
}

mutate_index() {
  python3 - "$FIXTURE/skills/index.json" "$1" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
payload = json.loads(path.read_text(encoding="utf-8"))
entries = {entry["name"]: entry for entry in payload["skills"]}
if mode == "remove":
    entries["mentor-invest"].pop("description_waiver")
elif mode == "stale":
    entries["debug-flow"]["description_waiver"] = "2026-08-07 wits 核准：fixture waiver"
elif mode == "empty":
    entries["mentor-invest"]["description_waiver"] = ""
elif mode == "non-string":
    entries["mentor-invest"]["description_waiver"] = 7
elif mode == "invalid-format":
    entries["mentor-invest"]["description_waiver"] = "x"
elif mode == "missing-approval":
    entries["mentor-invest"]["description_waiver"] = "2026-08-07 wits 承載跨 skill 分流條款"
elif mode == "invalid-date-shape":
    entries["mentor-invest"]["description_waiver"] = "2026-8-7 wits 核准：理由"
elif mode == "invalid-calendar-date":
    entries["mentor-invest"]["description_waiver"] = "2026-99-99 wits 核准：理由"
elif mode == "empty-reason":
    entries["mentor-invest"]["description_waiver"] = "2026-08-07 wits 核准："
elif mode == "blank-reason":
    entries["mentor-invest"]["description_waiver"] = "2026-08-07 wits 核准：   "
else:
    raise ValueError(f"unknown mode: {mode}")
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

echo "== current waiver classification and baseline costs =="
report_fixture
python3 - "$WORK/report.json" "$BASELINE" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
baseline = json.load(open(sys.argv[2], encoding="utf-8"))
threshold = report["description_threshold"]
shared_waiver = "2026-08-07 wits 核准：承載跨 skill 分流條款——六個 mentor 系 skill 互相競爭路由，壓縮會惡化已知的觸發詞重疊（計劃書 §4 目標 C）"
expected_waived = {
    "mentor-invest": (655, shared_waiver),
    "mentor-neuro": (536, shared_waiver),
    "mentor-science": (509, shared_waiver),
    "mentor-tech": (601, shared_waiver),
    "tw-stock-tracker": (586, "2026-08-07 wits 核准：description 承載與 mentor-invest 的「操作層 vs 概念層」分流條款（計劃書 §4 目標 C）"),
    "unknown-matrix-navigation": (613, "2026-08-07 wits 核准：計劃書 v1 即點名的合理例外，description 承載三種未知類型的分流判準（計劃書 §4 目標 C）"),
}
actual_waived = {
    row["name"]: (row["bytes"], row["waiver"])
    for row in threshold["waived"]
}
assert threshold["over"] == [], threshold["over"]
assert actual_waived == expected_waived, actual_waived
assert threshold["stale_waivers"] == [], threshold["stale_waivers"]
assert threshold["pass"] == 22, threshold["pass"]
checks = (
    ("fixed_startup_cost", "resident_rules_bytes"),
    ("fixed_startup_cost", "descriptions_bytes"),
    ("maintenance_inventory", "body_bytes"),
)
for section, key in checks:
    assert report[section][key] == baseline[section][key], (section, key)
print("PASS: over=0, waived=6, stale_waivers=0, pass=22; three cost classes match baseline")
PY

bash "$REPO/bin/token-budget.sh" > "$WORK/current-render.txt"
python3 - "$WORK/current-render.txt" <<'PY'
import sys

output = open(sys.argv[1], encoding="utf-8").read()
threshold = output.split("【description 門檻】", 1)[1].split("\n* token 為", 1)[0]
waiver_heading = threshold.index("【已核准 waiver】")
expected_names = {
    "mentor-invest", "mentor-neuro", "mentor-science",
    "mentor-tech", "tw-stock-tracker", "unknown-matrix-navigation",
}
assert "無未核准超標" in threshold, threshold
assert all(threshold.index(name) > waiver_heading for name in expected_names), threshold
assert not any("⚠️" in line for line in threshold.splitlines()), threshold
assert "23,171 / 30,000 bytes (77.2%)" in output, output
print("PASS: real entrypoint renders no unapproved overages and all 6 waivers after heading")
PY
bash "$REPO/bin/token-budget.sh" --strict > "$WORK/current-strict.txt"
echo "PASS: real repository passes --strict"

echo "== wrapper forwards arguments and preserves the Python exit code =="
set +e
python3 "$REPORT" "$REPO" --nosuchflag > "$WORK/python-unknown.log" 2>&1
PYTHON_UNKNOWN_STATUS=$?
bash "$REPO/bin/token-budget.sh" --nosuchflag > "$WORK/wrapper-unknown.log" 2>&1
WRAPPER_UNKNOWN_STATUS=$?
set -e
if [[ "$PYTHON_UNKNOWN_STATUS" -eq 0 || "$WRAPPER_UNKNOWN_STATUS" -eq 0 ]]; then
  echo "FAIL: unknown flag unexpectedly succeeded"
  exit 1
fi
grep -qF "未知旗標 ['--nosuchflag']" "$WORK/wrapper-unknown.log"
if [[ "$WRAPPER_UNKNOWN_STATUS" -ne "$PYTHON_UNKNOWN_STATUS" ]]; then
  echo "FAIL: wrapper exit $WRAPPER_UNKNOWN_STATUS != Python exit $PYTHON_UNKNOWN_STATUS"
  exit 1
fi
cmp "$WORK/python-unknown.log" "$WORK/wrapper-unknown.log"
echo "PASS: wrapper forwarded --nosuchflag and preserved Python exit $PYTHON_UNKNOWN_STATUS"

echo "== missing waiver becomes over =="
cp "$REPO/skills/index.json" "$FIXTURE/skills/index.json"
mutate_index remove
report_fixture
python3 - "$WORK/report.json" <<'PY'
import json
import sys

threshold = json.load(open(sys.argv[1], encoding="utf-8"))["description_threshold"]
assert [row["name"] for row in threshold["over"]] == ["mentor-invest"]
print("PASS: mentor-invest appears in over")
PY
python3 "$REPORT" "$FIXTURE" > "$WORK/remove-render.txt"
grep -E '⚠️.*mentor-invest' "$WORK/remove-render.txt"
echo "PASS: renderer shows mentor-invest warning"
python3 "$REPORT" "$FIXTURE" > /dev/null
echo "PASS: missing waiver remains exit 0 without --strict"
if python3 "$REPORT" "$FIXTURE" --strict > /dev/null 2> "$WORK/remove-strict.err"; then
  echo "FAIL: missing waiver passed --strict"
  exit 1
fi
grep -F -- "--strict 失敗——未核准超標 1 筆、失效 waiver 0 筆" "$WORK/remove-strict.err"
echo "PASS: missing waiver exits 1 with --strict"
if python3 "$REPORT" "$FIXTURE" --json --strict \
    > "$WORK/remove-strict.json" 2> "$WORK/remove-json-strict.err"; then
  echo "FAIL: missing waiver passed --json --strict"
  exit 1
fi
python3 -m json.tool "$WORK/remove-strict.json" > /dev/null
grep -qF -- "--strict 失敗——未核准超標 1 筆、失效 waiver 0 筆" \
  "$WORK/remove-json-strict.err"
echo "PASS: --json --strict emits valid JSON and exits 1"

echo "== waiver below threshold becomes stale =="
cp "$REPO/skills/index.json" "$FIXTURE/skills/index.json"
mutate_index stale
report_fixture
python3 - "$WORK/report.json" <<'PY'
import json
import sys

threshold = json.load(open(sys.argv[1], encoding="utf-8"))["description_threshold"]
assert [row["name"] for row in threshold["stale_waivers"]] == ["debug-flow"]
print("PASS: debug-flow appears in stale_waivers")
PY
python3 "$REPORT" "$FIXTURE" > "$WORK/stale-render.txt"
grep -F "waiver 已失效" "$WORK/stale-render.txt"
grep -F "debug-flow" "$WORK/stale-render.txt"
echo "PASS: renderer shows expired debug-flow waiver"
python3 "$REPORT" "$FIXTURE" > /dev/null
echo "PASS: stale waiver remains exit 0 without --strict"
if python3 "$REPORT" "$FIXTURE" --strict > /dev/null 2> "$WORK/stale-strict.err"; then
  echo "FAIL: stale waiver passed --strict"
  exit 1
fi
grep -F -- "--strict 失敗——未核准超標 0 筆、失效 waiver 1 筆" "$WORK/stale-strict.err"
echo "PASS: stale waiver exits 1 with --strict"

echo "== fixed startup cost over budget is advisory =="
cp "$REPO/skills/index.json" "$FIXTURE/skills/index.json"
python3 "$REPORT" "$FIXTURE" --json > "$WORK/pre-over-budget.json"
# 補到剛好越過門檻再加 1000，而非寫死 5000——固定開場成本會隨 skill 增減變動，
# 寫死的 padding 在成本下降時會靜默失效（2026-08-25 停用 12 個 skill 時實際踩到）。
python3 - "$FIXTURE/rules/coding-standards.md" "$WORK/pre-over-budget.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
subtotal = json.load(open(sys.argv[2], encoding="utf-8"))["fixed_startup_cost"]["subtotal_bytes"]
with path.open("ab") as handle:
    handle.write(b"x" * (30000 - subtotal + 1000))
PY
python3 "$REPORT" "$FIXTURE" > "$WORK/over-budget.txt"
grep -F "固定開場成本超過預算" "$WORK/over-budget.txt"
python3 "$REPORT" "$FIXTURE" --strict > /dev/null
python3 "$REPORT" "$FIXTURE" --json > "$WORK/over-budget.json"
python3 - "$WORK/over-budget.json" <<'PY'
import json
import sys

fixed = json.load(open(sys.argv[1], encoding="utf-8"))["fixed_startup_cost"]
assert fixed["over_budget"] is True, fixed
assert fixed["budget_bytes"] == 30000, fixed
print("PASS: over_budget=true and budget_bytes=30000; exit 0 with and without --strict")
PY

echo "== invalid waiver values fail report and validation =="
for mode in invalid-format missing-approval invalid-date-shape invalid-calendar-date \
    empty-reason blank-reason empty non-string; do
  cp "$REPO/skills/index.json" "$FIXTURE/skills/index.json"
  mutate_index "$mode"
  if python3 "$REPORT" "$FIXTURE" > "$WORK/report-$mode.log" 2>&1; then
    echo "FAIL: report accepted $mode description_waiver without --strict"
    exit 1
  fi
  grep -qF "mentor-invest: description_waiver" "$WORK/report-$mode.log"
  if python3 "$VALIDATOR" --repo "$FIXTURE" > "$WORK/validator-$mode.log" 2>&1; then
    echo "FAIL: validator accepted $mode description_waiver"
    exit 1
  fi
  grep -qF "mentor-invest: description_waiver" "$WORK/validator-$mode.log"
  case "$mode" in
    empty) grep -qF "不得為空" "$WORK/validator-$mode.log" ;;
    non-string) grep -qF "必須是字串" "$WORK/validator-$mode.log" ;;
    invalid-calendar-date) grep -qF "日期不存在：2026-99-99" "$WORK/validator-$mode.log" ;;
    blank-reason) grep -qF "理由不得為空白" "$WORK/validator-$mode.log" ;;
    *) grep -qF "格式不符" "$WORK/validator-$mode.log" ;;
  esac
  echo "  rejected by report and validator: $mode"
done
echo "PASS: malformed formats, nonexistent date, blank reason, empty and non-string waivers fail both paths"

STATUS_AFTER="$(git -C "$REPO" status --porcelain)"
if [[ "$STATUS_AFTER" != "$STATUS_BEFORE" ]]; then
  echo "FAIL: test polluted repository status"
  diff -u <(printf '%s\n' "$STATUS_BEFORE") <(printf '%s\n' "$STATUS_AFTER") || true
  exit 1
fi
echo "PASS: repository status unchanged"
echo "ALL TESTS PASSED"
