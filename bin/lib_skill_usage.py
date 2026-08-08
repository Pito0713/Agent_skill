"""Transcript mining for bin/skill-usage.py — extraction and aggregation only.

Mines Claude Code transcripts and Codex rollouts for evidence that a skill was
used. Reports three metrics that are deliberately never merged into one number:

  inv   Claude `Skill` tool call    — the model explicitly chose this skill
  read  SKILL.md opened for reading — may be a dependency read, not a choice
  edit  SKILL.md written to         — maintaining the skill, not using it

Design, known biases and the reason `?` exists: see
plans/skill-usage-and-self-correction.md
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Analysing transcripts writes skill paths into new transcripts. A scan that read
# those back would count its own output, so drop any call touching a log root.
ANALYSIS_MARKERS = (".codex/sessions", ".claude/projects")
# Plan drafts and this mechanism's own products name skills without using them.
EXCLUDED_TARGET_MARKERS = ("/plans/", "skill-usage", "skill-feedback", "skill-review")

SKILL_PATH_PATTERN = re.compile(r"[\w./~-]*skills/[\w./-]+/SKILL\.md")
WORKDIR_PATTERN = re.compile(r'"(?:workdir|cwd)"\s*:\s*"([^"]+)"')
APPLY_PATCH_TARGET = re.compile(r"\*\*\*\s+(?:Update|Add|Delete) File:\s*(\S+)")
CODEX_CALL_TYPES = {"function_call", "custom_tool_call", "local_shell_call"}
READ_TOOLS = {"Read", "NotebookRead"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


@dataclass(frozen=True)
class Event:
    harness: str
    session_id: str
    call_id: str
    moment: datetime | None
    kind: str  # invocation | read | edit
    skill: str | None  # None means it did not resolve to an indexed skill
    label: str  # canonical name, or the raw value for unresolved events
    workdir: str | None


@dataclass
class ScanStats:
    broken_lines: int = 0
    missing_roots: list[str] = field(default_factory=list)


def load_index(repository: Path) -> tuple[list[dict], dict[Path, str]]:
    """Return index entries plus a lookup from resolved package dir to skill name."""
    payload = json.loads((repository / "skills/index.json").read_text(encoding="utf-8"))
    entries = payload["skills"]
    directories = {
        (repository / entry["path"]).parent.resolve(): entry["name"] for entry in entries
    }
    return entries, directories


def read_jsonl(path: Path, stats: ScanStats):
    """Yield parsed records, skipping truncated or corrupt lines rather than dying."""
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        stats.broken_lines += 1
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                stats.broken_lines += 1
                continue
            if isinstance(record, dict):
                yield record


def parse_moment(raw: str | None) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def resolve_skill(raw_path: str, workdir: str | None, directories: dict[Path, str]) -> str | None:
    """Map a path to an indexed skill name; None when it points outside the index."""
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        if not workdir:
            return None
        candidate = Path(workdir).expanduser() / candidate
    try:
        return directories.get(candidate.resolve().parent)
    except OSError:
        return None


def build_claude_event(record: dict, block: dict, names: set[str], directories) -> Event | None:
    tool = block.get("name")
    payload = block.get("input") if isinstance(block.get("input"), dict) else {}
    common = dict(
        harness="claude",
        session_id=str(record.get("sessionId") or record.get("session_id") or "?"),
        call_id=str(block.get("id") or ""),
        moment=parse_moment(record.get("timestamp")),
        workdir=record.get("cwd"),
    )
    if tool == "Skill":
        raw = str(payload.get("skill") or "").strip()
        if not raw:
            return None
        return Event(kind="invocation", skill=raw if raw in names else None, label=raw, **common)
    if tool not in READ_TOOLS | WRITE_TOOLS:
        return None
    target = str(payload.get("file_path") or "")
    if not target.endswith("SKILL.md") or any(m in target for m in EXCLUDED_TARGET_MARKERS):
        return None
    skill = resolve_skill(target, common["workdir"], directories)
    kind = "read" if tool in READ_TOOLS else "edit"
    return Event(kind=kind, skill=skill, label=skill or target, **common)


def iter_claude_events(root: Path, names: set[str], directories, stats: ScanStats):
    if not root.is_dir():
        stats.missing_roots.append(f"claude transcripts not found: {root}")
        return
    for transcript in sorted(root.rglob("*.jsonl")):
        for record in read_jsonl(transcript, stats):
            if record.get("type") != "assistant":
                continue
            message = record.get("message")
            blocks = message.get("content") if isinstance(message, dict) else None
            for block in blocks or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                event = build_claude_event(record, block, names, directories)
                if event:
                    yield event


def extract_workdir(arguments: str) -> str | None:
    match = WORKDIR_PATTERN.search(arguments)
    return match.group(1) if match else None


def codex_target_paths(arguments: str, is_patch: bool) -> list[str]:
    """The paths a call actually acted on.

    For apply_patch only the `*** ... File:` headers are targets. Every other
    path inside the patch is body content — a diff that rewrites an index or a
    downstream entry file quotes dozens of SKILL.md paths it never touches.
    """
    if is_patch:
        return [t for t in APPLY_PATCH_TARGET.findall(arguments) if t.endswith("SKILL.md")]
    return SKILL_PATH_PATTERN.findall(arguments)


def build_codex_events(record: dict, payload: dict, session_id: str, session_cwd, directories):
    arguments = payload.get("arguments") or payload.get("input") or ""
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False)
    if any(marker in arguments for marker in ANALYSIS_MARKERS):
        return  # self-contamination guard: this call was analysing logs, not using skills
    workdir = extract_workdir(arguments) or session_cwd
    is_patch = payload.get("name") == "apply_patch" or "apply_patch" in arguments
    moment = parse_moment(record.get("timestamp"))
    call_id = str(payload.get("call_id") or payload.get("id") or "")
    seen: set[str] = set()
    for raw_path in codex_target_paths(arguments, is_patch):
        if any(marker in raw_path for marker in EXCLUDED_TARGET_MARKERS):
            continue
        skill = resolve_skill(raw_path, workdir, directories)
        label = skill or raw_path
        if label in seen:
            continue  # one command reading the same file twice is one event
        seen.add(label)
        yield Event(
            harness="codex",
            session_id=session_id,
            call_id=call_id,
            moment=moment,
            kind="edit" if is_patch else "read",
            skill=skill,
            label=label,
            workdir=workdir,
        )


def iter_codex_events(root: Path, directories, stats: ScanStats):
    if not root.is_dir():
        stats.missing_roots.append(f"codex rollouts not found: {root}")
        return
    for rollout in sorted(root.rglob("*.jsonl")):
        session_id, session_cwd = rollout.stem, None
        for record in read_jsonl(rollout, stats):
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            if record.get("type") == "session_meta":
                session_id = str(payload.get("session_id") or session_id)
                session_cwd = payload.get("cwd")
                continue
            if payload.get("type") not in CODEX_CALL_TYPES:
                continue
            yield from build_codex_events(record, payload, session_id, session_cwd, directories)


def classify_scope(event: Event, repository: Path) -> str:
    """usage / maintenance / unknown — never guess when the evidence is missing."""
    if event.kind == "edit":
        return "maintenance"
    if event.kind == "invocation":
        return "usage"  # an explicit choice counts even inside this repository
    if not event.workdir:
        return "unknown"
    try:
        inside_repo = Path(event.workdir).expanduser().resolve().is_relative_to(repository)
    except OSError:
        return "unknown"
    # A read inside this repo may be authoring or genuine use; refuse to decide.
    return "unknown" if inside_repo else "usage"


def aggregate(events, repository: Path, cutoff: datetime | None) -> dict:
    buckets: dict[str, dict] = defaultdict(
        lambda: {"sessions": defaultdict(set), "harnesses": set(), "last_usage": None,
                 "last_maintenance": None}
    )
    unresolved: dict[str, set] = defaultdict(set)
    seen_calls: set[tuple] = set()
    for event in events:
        fingerprint = (event.harness, event.call_id, event.label, event.kind)
        if event.call_id and fingerprint in seen_calls:
            continue  # transcript replay, sidechain copy or forked session
        seen_calls.add(fingerprint)
        if cutoff and event.moment and event.moment < cutoff:
            continue
        scope = classify_scope(event, repository)
        if event.skill is None:
            unresolved[event.label].add(event.session_id)
            continue
        bucket = buckets[event.skill]
        bucket["sessions"][f"{event.kind}:{scope}"].add(event.session_id)
        bucket["harnesses"].add(event.harness)
        field_name = "last_maintenance" if scope == "maintenance" else "last_usage"
        if event.moment and (bucket[field_name] is None or event.moment > bucket[field_name]):
            bucket[field_name] = event.moment
    return {"skills": buckets, "unresolved": unresolved}
