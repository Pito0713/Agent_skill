#!/usr/bin/env python3
"""Validate the canonical skill index and both harness discovery adapters."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_budget_spec import (  # noqa: E402
    SpecError, extract_description, split_frontmatter,
)

# Fields that must stay identical between index.json and llms.txt. Anything else
# in index.json is non-routing metadata that llms.txt deliberately does not carry.
ROUTING_FIELDS = ("name", "path", "triggers", "description")
# Structural reasons a skill is not expected to show up in usage statistics.
LIFECYCLE_VALUES = {"resident", "reference", "meta", "critical-on-demand"}
SEPARATOR = " 觸發："
HOOK_CANONICAL = "hooks/pre-commit-audit.sh"


def frontmatter_description_errors(
    repository: Path, skills: list[dict[str, str]]
) -> list[str]:
    """index.json ↔ frontmatter description 三向同步的第三向。

    既有檢查只涵蓋 index.json ↔ llms.txt；路由實際依據的 frontmatter
    完全沒有防漂移保護，正是計劃書目標 D' 要補的那一處。
    """
    errors: list[str] = []
    for entry in skills:
        name = entry.get("name", "?")
        for field in ("description", "triggers"):
            if SEPARATOR.strip() in entry.get(field, ""):
                errors.append(f"{name}: index.json 的 {field} 含分隔符「觸發：」")
        expected = f"{entry.get('description', '')}{SEPARATOR}{entry.get('triggers', '')}"
        try:
            data = (repository / entry["path"]).read_bytes()
            frontmatter, _ = split_frontmatter(data, entry["path"])
            actual = extract_description(frontmatter, entry["path"])
        except (SpecError, OSError) as error:
            errors.append(f"{entry['path']}: {error}")
            continue
        if actual != expected:
            errors.append(
                f"{entry['path']}: frontmatter description 與 index.json 不符"
                f"（跑 bin/gen-skill-frontmatter.py --write 重新生成）"
            )
    return errors


def hook_status(repository: Path) -> str:
    """回報 pre-commit hook 是否真的掛上。

    讓「你手動跑的工具」自己告訴你「自動防線在不在」——2026-08-04 實測
    文件宣稱裝了 6 份、實際 0 份，就是因為部署狀態只能靠人記得。
    """
    hook = repository / ".git/hooks/pre-commit"
    if not hook.is_file():
        return "pre-commit hook: 未安裝（bash bin/install-git-hooks.sh）"
    if not os.access(hook, os.X_OK):
        return "pre-commit hook: 存在但不可執行"
    delegates = HOOK_CANONICAL in hook.read_text(encoding="utf-8")
    canonical = (repository / HOOK_CANONICAL).is_file()
    if not delegates:
        return f"pre-commit hook: 已安裝，但未委派給 {HOOK_CANONICAL}"
    if not canonical:
        return f"pre-commit hook: 委派給 {HOOK_CANONICAL}，但正本不存在（fail-open 放行）"
    return f"pre-commit hook: 已安裝並委派給 {HOOK_CANONICAL}"


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
    indexed_entries = {
        entry["name"]: {field: entry.get(field, "") for field in ROUTING_FIELDS}
        for entry in skills
    }
    if indexed_entries != human_entries:
        errors.append("skills/index.json and skills/llms.txt routing metadata differ")
    for entry in skills:
        lifecycle = entry.get("lifecycle")
        if lifecycle is not None and lifecycle not in LIFECYCLE_VALUES:
            errors.append(f"{entry['name']}: unknown lifecycle {lifecycle!r}")
        unexpected = set(entry) - set(ROUTING_FIELDS) - {"lifecycle"}
        if unexpected:
            errors.append(f"{entry['name']}: unexpected index fields {sorted(unexpected)}")
    for entry in skills:
        skill_path = repository / entry["path"]
        if skill_path.name != "SKILL.md" or not skill_path.is_file():
            errors.append(f"invalid package path: {entry['path']}")
            continue
        if frontmatter_name(skill_path) != entry["name"]:
            errors.append(f"frontmatter name mismatch: {entry['path']}")
    errors.extend(frontmatter_description_errors(repository, skills))
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
    print(f"      {hook_status(repository)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
