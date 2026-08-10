#!/usr/bin/env bash
# Fixture tests for bin/skill-usage.py.
#
# Fixtures are generated at runtime rather than committed: they must contain
# absolute paths to resolve against the index, and hooks/pre-commit-audit.sh
# (correctly) refuses to let personal absolute paths into this public repo.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCANNER="$REPO/bin/skill-usage.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

CLAUDE_ROOT="$WORK/claude/projects/proj"
CODEX_ROOT="$WORK/codex/sessions/2026/08/08"
mkdir -p "$CLAUDE_ROOT" "$CODEX_ROOT"

python3 - "$REPO" "$CLAUDE_ROOT" "$CODEX_ROOT" <<'PY'
import json, sys, pathlib

repo, claude_root, codex_root = (pathlib.Path(a) for a in sys.argv[1:4])
skill = lambda rel: str(repo / "skills" / rel / "SKILL.md")
home = str(pathlib.Path.home())


def assistant(session, call_id, tool, payload, cwd, sidechain=False):
    return {
        "type": "assistant", "sessionId": session, "cwd": cwd,
        "timestamp": "2026-08-08T06:00:00.000Z", "isSidechain": sidechain,
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": call_id, "name": tool, "input": payload}]},
    }


downstream = f"{home}/WakaWaka"
claude_lines = [
    # explicit invocation, plus a verbatim replay and a sidechain copy of it
    assistant("S1", "c1", "Skill", {"skill": "code-review"}, downstream),
    assistant("S1", "c1", "Skill", {"skill": "code-review"}, downstream),
    assistant("S1", "c1", "Skill", {"skill": "code-review"}, downstream, sidechain=True),
    # a plugin skill that cannot be mapped onto this repo's index
    assistant("S1", "c2", "Skill", {"skill": "anthropic-skills:coding-workflow"}, downstream),
    # dependency read from a downstream project, and an edit of a skill package
    assistant("S1", "c3", "Read", {"file_path": skill("engineering/debug-flow")}, downstream),
    assistant("S1", "c4", "Edit", {"file_path": skill("productivity/handoff")}, downstream),
    # this mechanism's own outputs name skills without using them
    assistant("S1", "c5", "Read", {"file_path": skill("productivity/skill-review")}, downstream),
    # prose that mentions a skill path but is not a tool call
    {"type": "user", "sessionId": "S1", "cwd": downstream,
     "timestamp": "2026-08-08T06:00:00.000Z",
     "message": {"role": "user", "content": f"看一下 {skill('engineering/new-feature')} 的 Skill"}},
]
with (claude_root / "s1.jsonl").open("w", encoding="utf-8") as handle:
    for record in claude_lines:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.write('{"type":"assistant","message":{\n')  # truncated line


def item(kind, call_id, name, args, timestamp="2026-08-08T06:00:00.000Z"):
    key = "input" if kind == "custom_tool_call" else "arguments"
    return {"type": "response_item", "timestamp": timestamp,
            "payload": {"type": kind, "call_id": call_id, "name": name, key: args}}


workdir = f"{home}/lake-ui-kit"
codex_lines = [
    {"type": "session_meta", "timestamp": "2026-08-08T06:00:00.000Z",
     "payload": {"session_id": "X1", "cwd": workdir}},
    # one command reading two different skills -> two events, not one
    item("function_call", "k1", "exec_command", json.dumps(
        {"cmd": f"sed -n '1,240p' {skill('engineering/code-review')} && "
                f"sed -n '1,240p' {skill('engineering/tech-lead-mode')}",
         "workdir": workdir})),
    # the other Codex tool schema must be recognised too
    item("custom_tool_call", "k2", "exec", json.dumps(
        {"cmd": f"cat {skill('engineering/debug')}", "workdir": workdir})),
    # scanning transcripts writes skill paths into transcripts: must not count
    item("function_call", "k3", "exec_command", json.dumps(
        {"cmd": f"grep -r SKILL.md {home}/.claude/projects && cat {skill('engineering/new-feature')}",
         "workdir": workdir})),
    # a real patch against a skill package -> maintenance
    item("custom_tool_call", "k4", "apply_patch",
         f"*** Begin Patch\n*** Update File: {skill('design/wireframing')}\n"
         f"@@\n-old line\n+new line\n*** End Patch"),
    # a patch against something else whose body quotes many skill paths:
    # those are content, not targets, and must not become edit events
    item("custom_tool_call", "k5", "apply_patch",
         f"*** Begin Patch\n*** Update File: {home}/WakaWaka/AGENTS.md\n@@\n"
         f"+載入 {skill('learning/mentor-neuro')}\n"
         f"+載入 {skill('learning/mentor-science')}\n*** End Patch"),
    {"type": "response_item", "timestamp": "2026-08-08T06:00:00.000Z",
     "payload": {"type": "message", "role": "assistant",
                 "content": [{"type": "output_text", "text": f"我讀了 {skill('engineering/documentation')}"}]}},
]
with (codex_root / "rollout-a.jsonl").open("w", encoding="utf-8") as handle:
    for record in codex_lines:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

# a rollout with no session_meta and no workdir -> scope must stay unknown
with (codex_root / "rollout-nocwd.jsonl").open("w", encoding="utf-8") as handle:
    handle.write(json.dumps(item("custom_tool_call", "k9", "exec", json.dumps(
        {"cmd": f"cat {skill('productivity/rag-search')}"})), ensure_ascii=False) + "\n")
PY

echo "== scanning fixtures =="
python3 "$SCANNER" --repo "$REPO" --claude-root "$WORK/claude/projects" \
  --codex-root "$WORK/codex/sessions" --days 0 --json > "$WORK/out.json"

python3 - "$WORK/out.json" <<'PY'
import json, sys

report = json.loads(open(sys.argv[1], encoding="utf-8").read())
rows = {row["name"]: row for row in report["skills"]}
failures = []


def check(label, actual, expected):
    if actual != expected:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")


check("replayed+sidechain invocation counted once", rows["code-review"]["inv"], 1)
check("codex read of code-review", rows["code-review"]["read"], 1)
check("second skill in the same command", rows["tech-lead-mode"]["read"], 1)
check("custom_tool_call schema recognised", rows["debug"]["read"], 1)
check("read from a downstream project", rows["debug-flow"]["read"], 1)
check("edit classified as maintenance", rows["handoff"]["edit"], 1)
check("edit is not counted as usage", rows["handoff"]["read"], 0)
check("apply_patch classified as maintenance", rows["wireframing"]["edit"], 1)
check("patch body quoting a skill is not an edit", rows["mentor-neuro"]["edit"], 0)
check("patch body quoting a skill is not a read", rows["mentor-science"]["read"], 0)
check("missing workdir stays unknown", rows["rag-search"]["unknown"], 1)
check("missing workdir is not usage", rows["rag-search"]["read"], 0)
check("prose mention is not a tool call", rows["new-feature"]["read"], 0)
check("prose mention is not an invocation", rows["new-feature"]["inv"], 0)
check("codex prose mention ignored", rows["documentation"]["read"], 0)
check("skills with zero events still listed", rows["mentor-neuro"]["inv"], 0)
check("every indexed skill is present", len(report["skills"]), 38)
check("lifecycle surfaced", rows["deploy-prep"]["lifecycle"], "critical-on-demand")
check("foreign skill goes to unresolved",
      report["unresolved"].get("anthropic-skills:coding-workflow"), 1)
check("foreign skill is not invented as a row",
      "anthropic-skills:coding-workflow" in rows, False)
if report["skipped_lines"] < 1:
    failures.append("truncated line was not counted as skipped")
if report["warnings"]:
    failures.append(f"unexpected warnings: {report['warnings']}")

for failure in failures:
    print(f"FAIL: {failure}")
print(f"{'FAILED' if failures else 'PASS'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
PY

echo "== missing roots must fail loudly, not traceback =="
set +e
STDERR="$(python3 "$SCANNER" --repo "$REPO" --claude-root "$WORK/nope-a" \
  --codex-root "$WORK/nope-b" --days 0 2>&1 >/dev/null)"
STATUS=$?
set -e
if [ "$STATUS" -ne 1 ]; then echo "FAIL: expected exit 1, got $STATUS"; exit 1; fi
case "$STDERR" in
  *Traceback*) echo "FAIL: tracebacked instead of reporting"; exit 1 ;;
  *"neither transcript root exists"*) echo "PASS: missing roots reported cleanly" ;;
  *) echo "FAIL: unexpected stderr: $STDERR"; exit 1 ;;
esac

echo "ALL TESTS PASSED"
