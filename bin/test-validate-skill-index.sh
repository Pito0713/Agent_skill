#!/usr/bin/env bash
# test-validate-skill-index.sh — bin/validate-skill-index.py 的改名一致性檢查（工單 W1）。
# fixture：把本 repo 的 skills/ 複製到 mktemp -d，再製造「name 已改、目錄沒改」的情境。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATOR="$SCRIPT_DIR/validate-skill-index.py"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }

# new_fixture <名稱>：FIXTURE 指向一份可通過 validator 的 repo 複本
new_fixture() {
  FIXTURE="$SANDBOX/$1"
  mkdir -p "$FIXTURE"
  cp -R "$REPO_ROOT/skills" "$FIXTURE/skills" || { echo "fixture 失敗：複製 skills/" >&2; exit 2; }
}

run_validator() { OUT=$(python3 "$VALIDATOR" --repo "$FIXTURE" 2>&1); RC=$?; }

# 把 index.json 與 llms.txt 裡某 skill 的 path 改到新目錄（模擬「目錄搬了、name 沒改」）
move_package() {
  local old_dir="$1" new_dir="$2"
  mv "$FIXTURE/skills/$old_dir" "$FIXTURE/skills/$new_dir"
  OLD="skills/$old_dir/SKILL.md" NEW="skills/$new_dir/SKILL.md" python3 - "$FIXTURE" <<'PY'
import os, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ("skills/index.json", "skills/llms.txt"):
    path = root / name
    path.write_text(path.read_text().replace(os.environ["OLD"], os.environ["NEW"]))
PY
}

echo "[基準]"
new_fixture baseline
run_validator
[[ "$RC" == 0 ]] && pass "原樣複本通過 validator" || fail "原樣複本通過 validator（${OUT}）"

echo "[目錄名 ≠ name]"
new_fixture renamed
move_package productivity/version-log productivity/version-log-old
run_validator
[[ "$RC" == 1 ]] && pass "目錄名與 name 不一致 → exit 1" || fail "目錄名與 name 不一致 → exit 1（exit ${RC}）"
grep -q "package directory name mismatch: skills/productivity/version-log-old/SKILL.md" <<<"$OUT" \
  && pass "錯誤訊息指出是哪個 package" || fail "錯誤訊息指出是哪個 package（${OUT}）"
grep -q "frontmatter name mismatch" <<<"$OUT" \
  && fail "frontmatter 沒動，不應報 frontmatter 錯" || pass "只報目錄名錯，不誤報 frontmatter"

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
