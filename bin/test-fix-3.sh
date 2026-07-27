#!/usr/bin/env bash
# FIX-3 regression tests. All fixtures live under /tmp; no real farm is touched.

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FIXTURE_ROOT="$(mktemp -d /tmp/agent-skill-fix-3.XXXXXX)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

assert_contains() {
  local output="$1"
  local expected="$2"
  if [[ "$output" != *"$expected"* ]]; then
    echo "FAIL: expected output to contain: $expected" >&2
    return 1
  fi
}

legacy_project="$FIXTURE_ROOT/legacy-project"
legacy_home="$FIXTURE_ROOT/legacy-home"
mkdir -p "$legacy_project" "$legacy_home/.claude/skills"
legacy_entry="$legacy_project/CLAUDE.md"
cat > "$legacy_entry" <<'EOF'
<!-- agent-skill:begin -->
@~/.Codex/inside-managed-block.md
<!-- agent-skill:end -->

custom content
@~/.Codex/legacy.md
EOF
before_checksum="$(shasum "$legacy_entry")"
warning_output="$(
  AGENT_SKILL_PROJECT_DIR="$legacy_project" \
    AGENT_SKILL_HOME="$legacy_home" \
    bash "$REPOSITORY_DIR/bin/inject-claude.sh" --preflight 2>&1
)"
after_checksum="$(shasum "$legacy_entry")"
assert_contains "$warning_output" "$legacy_entry:6: @~/.Codex/legacy.md"
assert_contains "$warning_output" "疑似舊代殘留，請人工確認後手動移除"
[[ "$warning_output" != *"inside-managed-block"* ]]
[[ "$before_checksum" == "$after_checksum" ]]

dangling_project="$FIXTURE_ROOT/dangling-project"
clean_project="$FIXTURE_ROOT/clean-project"
mkdir -p "$dangling_project/.claude/skills" "$clean_project/.codex/skills" "$FIXTURE_ROOT/target"
ln -s "$FIXTURE_ROOT/missing-target" "$dangling_project/.claude/skills/old-skill"
ln -s "$FIXTURE_ROOT/target" "$clean_project/.codex/skills/current-skill"

dangling_output="$(bash "$REPOSITORY_DIR/bin/scan-downstream.sh" "$dangling_project")"
assert_contains "$dangling_output" "dangling-project:claude:old-skill -> $FIXTURE_ROOT/missing-target"
clean_output="$(bash "$REPOSITORY_DIR/bin/scan-downstream.sh" "$clean_project")"
assert_contains "$clean_output" "✅ 無 dangling"

echo "PASS: legacy warning is read-only and excludes managed block"
echo "PASS: downstream scanner reports dangling and clean farms"
