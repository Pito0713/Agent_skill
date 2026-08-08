#!/usr/bin/env python3
"""Skill usage scanner — read-only, writes nothing but stdout.

Mines Claude Code transcripts and Codex rollouts for evidence that a skill was
used. Reports three metrics that are deliberately never merged into one number:

  inv   Claude `Skill` tool call    — the model explicitly chose this skill
  read  SKILL.md opened for reading — may be a dependency read, not a choice
  edit  SKILL.md written to         — maintaining the skill, not using it

Extraction lives in lib_skill_usage.py. Design, known biases and the reason `?`
exists: see plans/skill-usage-and-self-correction.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib_skill_usage import (
    ScanStats,
    aggregate,
    iter_claude_events,
    iter_codex_events,
    load_index,
)


def redact(text: str) -> str:
    """Personal absolute paths must not leave this scanner verbatim.

    Output gets pasted into reviews and (in later phases) committed to a public
    repository, where hooks/pre-commit-audit.sh would rightly reject them.
    """
    return text.replace(str(Path.home()), "~")


def build_rows(entries: list[dict], tallies: dict) -> list[dict]:
    rows = []
    for entry in entries:
        bucket = tallies["skills"].get(entry["name"])
        sessions = bucket["sessions"] if bucket else {}
        last = bucket["last_usage"] if bucket else None
        rows.append(
            {
                "name": entry["name"],
                "lifecycle": entry.get("lifecycle") or "",
                "inv": len(sessions.get("invocation:usage", ())),
                "read": len(sessions.get("read:usage", ())),
                "edit": len(sessions.get("edit:maintenance", ())),
                "unknown": len(sessions.get("read:unknown", ())),
                "last_usage": last.date().isoformat() if last else "",
                "harnesses": ",".join(sorted(bucket["harnesses"])) if bucket else "",
            }
        )
    rows.sort(key=lambda row: (-(row["inv"] * 3 + row["read"]), row["name"]))
    return rows


def render_table(rows: list[dict], tallies: dict, stats: ScanStats, window: str) -> str:
    lines = [f"# Skill usage — window: {window} (UTC)", ""]
    header = f"{'skill':<28}{'inv':>4}{'read':>6}{'edit':>6}{'?':>4}  {'last-usage':<12}{'harness':<14}lifecycle"
    lines += [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row['name']:<28}{row['inv']:>4}{row['read']:>6}{row['edit']:>6}"
            f"{row['unknown']:>4}  {row['last_usage']:<12}{row['harnesses']:<14}{row['lifecycle']}"
        )
    unresolved = tallies["unresolved"]
    lines += ["", f"## unresolved — not in skills/index.json ({len(unresolved)})"]
    for label, sessions in sorted(unresolved.items(), key=lambda item: -len(item[1]))[:15]:
        lines.append(f"  {len(sessions):>3}  {redact(label)}")
    lines += [
        "",
        "## coverage",
        "  inv  = Claude `Skill` tool call (explicit choice)",
        "  read = SKILL.md read; may be a dependency read, not a choice",
        "  edit = SKILL.md written to; maintenance, not usage",
        "  ?    = read whose workdir is missing or inside this repo — deliberately unclassified",
        "  counts are distinct sessions, not raw hits",
        "  agy (Antigravity) is NOT covered: its conversations are sqlite blobs",
    ]
    if stats.broken_lines:
        lines.append(f"  skipped {stats.broken_lines} unparsable line(s)")
    for note in stats.missing_roots:
        lines.append(f"  WARNING: {note}")
    return "\n".join(lines)


def main() -> int:
    default_repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Read-only skill usage scanner.")
    parser.add_argument("--repo", type=Path, default=default_repo)
    parser.add_argument("--claude-root", type=Path, default=Path.home() / ".claude/projects")
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".codex/sessions")
    parser.add_argument("--days", type=int, default=30, help="0 means the whole history")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    arguments = parser.parse_args()

    repository = arguments.repo.resolve()
    entries, directories = load_index(repository)
    names = {entry["name"] for entry in entries}
    stats = ScanStats()
    cutoff = datetime.now(timezone.utc) - timedelta(days=arguments.days) if arguments.days else None

    events = list(iter_claude_events(arguments.claude_root, names, directories, stats))
    events += list(iter_codex_events(arguments.codex_root, directories, stats))
    tallies = aggregate(events, repository, cutoff)
    rows = build_rows(entries, tallies)
    window = f"last {arguments.days}d" if arguments.days else "all history"

    if arguments.json:
        payload = {
            "window": window,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "skills": rows,
            "unresolved": {redact(k): len(v) for k, v in tallies["unresolved"].items()},
            "skipped_lines": stats.broken_lines,
            "warnings": stats.missing_roots,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_table(rows, tallies, stats, window))

    if len(stats.missing_roots) == 2:
        print("ERROR: neither transcript root exists; nothing was scanned", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
