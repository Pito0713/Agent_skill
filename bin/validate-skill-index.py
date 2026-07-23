#!/usr/bin/env python3
"""Validate the canonical skill index and both harness discovery adapters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_index(repository: Path) -> list[dict[str, str]]:
    index_path = repository / "skills/index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    skills = payload.get("skills")
    if not isinstance(skills, list):
        raise ValueError("skills/index.json: skills must be a list")
    return skills


def frontmatter_name(skill_path: Path) -> str:
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{skill_path}: missing frontmatter")
    declared_name: str | None = None
    frontmatter_lines: list[str] = []
    for line in lines[1:]:
        if line == "---":
            break
        frontmatter_lines.append(line)
        if line.startswith("name:"):
            declared_name = line.split(":", 1)[1].strip()
    else:
        raise ValueError(f"{skill_path}: unclosed frontmatter")
    required_prefixes = ("description:", "metadata:")
    for prefix in required_prefixes:
        if not any(line.startswith(prefix) for line in frontmatter_lines):
            raise ValueError(f"{skill_path}: missing {prefix.removesuffix(':')}")
    if declared_name:
        return declared_name
    raise ValueError(f"{skill_path}: missing frontmatter name")


def llms_entries(repository: Path) -> dict[str, dict[str, str]]:
    lines = (repository / "skills/llms.txt").read_text(encoding="utf-8").splitlines()
    entries: dict[str, dict[str, str]] = {}
    current_name: str | None = None
    for line in lines:
        if line.startswith("name: "):
            current_name = line.removeprefix("name: ")
            entries[current_name] = {"name": current_name}
            continue
        if not current_name:
            continue
        for field in ("path", "triggers", "description"):
            prefix = f"{field}: "
            if line.startswith(prefix):
                entries[current_name][field] = line.removeprefix(prefix)
    return entries


def validate_entries(repository: Path, skills: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    names = [entry.get("name", "") for entry in skills]
    paths = [entry.get("path", "") for entry in skills]
    if len(names) != len(set(names)):
        errors.append("duplicate skill name")
    if len(paths) != len(set(paths)):
        errors.append("duplicate skill path")
    human_entries = llms_entries(repository)
    indexed_entries = {entry["name"]: entry for entry in skills}
    if indexed_entries != human_entries:
        errors.append("skills/index.json and skills/llms.txt routing metadata differ")
    for entry in skills:
        skill_path = repository / entry["path"]
        if skill_path.name != "SKILL.md" or not skill_path.is_file():
            errors.append(f"invalid package path: {entry['path']}")
            continue
        if frontmatter_name(skill_path) != entry["name"]:
            errors.append(f"frontmatter name mismatch: {entry['path']}")
    canonical_paths = {
        path.relative_to(repository).as_posix()
        for path in (repository / "skills").rglob("SKILL.md")
    }
    if canonical_paths != set(paths):
        errors.append("canonical package coverage and index differ")
    return errors


def validate_adapter(
    adapter: Path, repository: Path, skills: list[dict[str, str]]
) -> list[str]:
    if not adapter.is_dir():
        return [f"missing adapter directory: {adapter}"]
    errors: list[str] = []
    discovered = list(adapter.glob("*/SKILL.md"))
    expected_names = {entry["name"] for entry in skills}
    discovered_names = {path.parent.name for path in discovered}
    missing_names = expected_names - discovered_names
    if missing_names:
        errors.append(f"{adapter}: missing indexed names: {sorted(missing_names)}")
    indexed_targets = {
        entry["name"]: (repository / entry["path"]).parent.resolve() for entry in skills
    }
    for skill_name in expected_names:
        adapter_entry = adapter / skill_name
        if not adapter_entry.is_symlink():
            errors.append(f"{adapter_entry}: expected managed symlink")
            continue
        if adapter_entry.resolve() != indexed_targets[skill_name]:
            errors.append(f"{adapter_entry}: target differs from canonical package")
    errors.extend(orphan_entries(adapter, repository, expected_names))
    return errors


def orphan_entries(
    adapter: Path, repository: Path, expected_names: set[str]
) -> list[str]:
    """Managed entries no longer in the index.

    Only entries resolving inside the canonical skills/ tree are managed: extra
    entries such as Claude's rules/governance links and any third-party entry
    resolve elsewhere and are deliberately left alone.
    """
    canonical_root = (repository / "skills").resolve()
    errors: list[str] = []
    for entry in sorted(adapter.iterdir()):
        if not entry.is_symlink() or entry.name in expected_names:
            continue
        if not entry.resolve().is_relative_to(canonical_root):
            continue
        errors.append(f"{entry}: orphan managed entry (not in skills/index.json)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--claude-adapter", type=Path)
    parser.add_argument("--codex-adapter", type=Path)
    arguments = parser.parse_args()
    repository = arguments.repo.resolve()
    skills = load_index(repository)
    errors = validate_entries(repository, skills)
    for adapter in (arguments.claude_adapter, arguments.codex_adapter):
        if adapter:
            errors.extend(validate_adapter(adapter, repository, skills))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {len(skills)} indexed skill packages are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
