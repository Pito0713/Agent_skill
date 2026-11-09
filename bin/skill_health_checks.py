#!/usr/bin/env python3
"""skill-health 的 Python 檢查：A6 預算解析、A9 SKILL.md 路徑引用。

介面與 skill-health.sh 的檢查函式一致：第一行 stdout 是摘要，其餘是明細；
exit 0 = 通過，10 = ⚠️，其他 = 檢查本身失敗（bash 端記為 💥）。
"""
import json
import os
import re
import sys

EXIT_OK = 0
EXIT_WARN = 10

# 路徑前綴；`~/Agent_skill/` 形式先剝掉再抽，才不會漏掉絕對寫法的引用
PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./~-])((?:skills|governance|rules)/[A-Za-z0-9_./-]*[A-Za-z0-9_/-])"
)
HOME_PREFIX = "~/Agent_skill/"
# 路徑後緊接這些字元代表是 glob / 佔位符，抽到的只是前半段
PLACEHOLDER_FOLLOWERS = "*<{$[…"


def classify_budget(report: dict) -> tuple:
    """回傳 (摘要, 明細列表)；明細為空代表沒有問題。"""
    issues = []
    startup = report["fixed_startup_cost"]
    if startup.get("over_budget"):
        issues.append("固定開場成本超標：%s / %s bytes"
                      % (startup.get("subtotal_bytes"), startup.get("budget_bytes")))
    threshold = report["description_threshold"]
    for item in threshold.get("over", []):
        issues.append("description 超過 %s bytes 且未 waiver：%s"
                      % (threshold.get("limit_bytes"), json.dumps(item, ensure_ascii=False)))
    for item in threshold.get("stale_waivers", []):
        issues.append("失效 waiver：%s" % json.dumps(item, ensure_ascii=False))
    summary = "固定開場成本 %s / %s bytes" % (
        startup.get("subtotal_bytes"), startup.get("budget_bytes"))
    return summary, issues


def run_budget() -> int:
    report = json.load(sys.stdin)
    summary, issues = classify_budget(report)
    if not issues:
        print(summary)
        return EXIT_OK
    print("%s；%d 項預算問題" % (summary, len(issues)))
    for issue in issues:
        print("- " + issue)
    return EXIT_WARN


def extract_repo_paths(text: str) -> list:
    """抽出文字中的 repo 相對路徑引用（去重、保留出現順序）。"""
    cleaned = text.replace(HOME_PREFIX, "")
    found = []
    for match in PATH_PATTERN.finditer(cleaned):
        follower = cleaned[match.end():match.end() + 1]
        if follower and follower in PLACEHOLDER_FOLLOWERS:
            continue
        path = match.group(1)
        if path not in found:
            found.append(path)
    return found


def find_missing_references(repo_root: str) -> tuple:
    """回傳 (SKILL.md 數量, [(SKILL.md 相對路徑, 缺少的路徑), ...])。"""
    skills_root = os.path.join(repo_root, "skills")
    if not os.path.isdir(skills_root):
        raise FileNotFoundError("skills/ 目錄不存在：%s" % skills_root)
    skill_files = []
    for directory, _subdirs, filenames in os.walk(skills_root):
        if "SKILL.md" in filenames:
            skill_files.append(os.path.join(directory, "SKILL.md"))
    missing = []
    for skill_file in sorted(skill_files):
        with open(skill_file, encoding="utf-8") as handle:
            text = handle.read()
        for path in extract_repo_paths(text):
            if not os.path.exists(os.path.join(repo_root, path)):
                missing.append((os.path.relpath(skill_file, repo_root), path))
    return len(skill_files), missing


def run_paths(repo_root: str) -> int:
    skill_count, missing = find_missing_references(repo_root)
    if not missing:
        print("%d 份 SKILL.md 的 repo 路徑引用皆存在" % skill_count)
        return EXIT_OK
    print("%d 個引用路徑不存在（掃 %d 份 SKILL.md）" % (len(missing), skill_count))
    for skill_file, path in missing:
        print("- %s 引用 %s" % (skill_file, path))
    return EXIT_WARN


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[1] == "budget":
        return run_budget()
    if len(argv) == 3 and argv[1] == "paths":
        return run_paths(argv[2])
    sys.stderr.write("usage: skill_health_checks.py budget < json | paths <repo>\n")
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
