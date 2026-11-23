#!/usr/bin/env python3
"""project-review.py — 專案定期 review（P0：L0 閘門 + L1 確定性檢查 + status.json）。

用法：
  python3 bin/project-review.py                  跑登記表中所有專案
  python3 bin/project-review.py --project NAME   只跑一個
  python3 bin/project-review.py --force          今天已跑過也重跑
  python3 bin/project-review.py --preflight ENTRY.json
                                                 **登記前必跑**：在 HEAD 快照上跑一次該專案的檢查，
                                                 不過就不要登記（ENTRY.json = 登記表裡的一項）

登記表（每台機器自己的設定，不進 repo）：~/.config/agent-review/projects.json
  {"projects": [{"name": "foo", "path": "~/foo", "setup": "npm ci",
                 "checks": {"test": "npm test", "lint": "npm run lint"}, "timeoutSeconds": 600}]}
  name 要等於 ~/.agent-sessions/ 下的目錄名，Floating 靠它把交接檔和狀態檔對起來。
  新增專案前先跑 --preflight：原地測試通過、快照不過 = 測試不 hermetic（依賴自身絕對路徑等），
  登記後每天都會誤報（lessons 2026-11-10，工單 W5）。

產出：~/.agent-reports/project-review/<name>/{status.json, YYYY-MM-DD.md, logs/YYYY-MM-DD/}
本程式只讀專案 repo（檢查跑在 worktree 快照），不寫 ~/.agent-sessions（ADR-015）。

環境變數（測試用）：PROJECT_REVIEW_CONFIG、PROJECT_REVIEW_REPORT_DIR、PROJECT_REVIEW_SESSIONS_DIR、
  PROJECT_REVIEW_TODAY（YYYY-MM-DD）、PROJECT_REVIEW_NOTIFY=off、PROJECT_REVIEW_NOTIFY_CMD
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from project_review_checks import run_checks, tail_of
from project_review_report import build_status, read_json, render_report, write_json_atomically

DEFAULT_TIMEOUT_SECONDS = 600
HANDOFF_UPDATED_PATTERN = re.compile(r"最後更新：\s*(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?)")


class ConfigError(Exception):
    pass


def env_path(name: str, default: str) -> Path:
    return Path(os.path.expanduser(os.environ.get(name, default)))


def load_projects(config_path: Path) -> list:
    if not config_path.exists():
        raise ConfigError(f"找不到登記表 {config_path}（格式見本檔開頭說明）")
    config = read_json(config_path)
    if not isinstance(config, dict) or not isinstance(config.get("projects"), list):
        raise ConfigError(f"{config_path} 不是合法 JSON 或缺少 projects 陣列")
    for project in config["projects"]:
        validate_project(project)
    return config["projects"]


def validate_project(project: object) -> None:
    if not isinstance(project, dict) or not project.get("name") or not project.get("path"):
        raise ConfigError(f"每個專案都要有 name 與 path：{project}")
    if "/" in project["name"] or project["name"].startswith("."):
        raise ConfigError(f"name 不能含 / 或以 . 開頭：{project['name']}")
    project["path"] = os.path.expanduser(project["path"])


def run_preflight(entry_path: Path) -> int:
    """登記前在 HEAD 快照跑一次檢查；全部第一次就過才回 0。flaky 也不算過——登記後會天天誤報。"""
    entry = read_json(entry_path)
    if entry is None:
        raise ConfigError(f"preflight：讀不到 {entry_path} 或不是合法 JSON")
    validate_project(entry)
    if not entry.get("checks"):
        raise ConfigError("preflight：沒有設定任何 checks，登記了也沒有東西可檢查")
    commit = git_output(entry["path"], "rev-parse", "--short=12", "HEAD")
    if commit is None:
        raise ConfigError(f"preflight：{entry['path']} 不是可讀的 git repo")
    timeout_seconds = int(entry.get("timeoutSeconds", DEFAULT_TIMEOUT_SECONDS))
    with tempfile.TemporaryDirectory(prefix="project-review-preflight-") as log_dir:
        result, checks, errors = run_checks(entry, commit, Path(log_dir), timeout_seconds)
        for name, check_result in checks.items():
            print(f"  {name}: {check_result}")
            if check_result != "pass":
                print("    " + tail_of(Path(log_dir) / f"{name}.log").replace("\n", "\n    "))
        if not checks and (Path(log_dir) / "setup.log").exists():
            # 暫存 log 目錄離開 with 就刪掉，setup 失敗的原因要在這裡印出來
            print("  setup：\n    " + tail_of(Path(log_dir) / "setup.log").replace("\n", "\n    "))
    for error in errors:
        print(f"  錯誤：{error}")
    if result == "pass":
        print(f"preflight 通過（{entry['name']} @ {commit}）：可以登記")
        return 0
    print(f"preflight 不通過（{result}）：不要登記。原地跑得過、快照跑不過 = 測試不 hermetic"
          "（例如依賴自身絕對路徑或 symlink），先修測試或從 checks 拿掉該項")
    return 1


def git_output(repo_path: str, *arguments: str) -> Optional[str]:
    completed = subprocess.run(["git", "-C", repo_path, *arguments], capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else None


def read_handoff(project: dict, sessions_dir: Path) -> Optional[dict]:
    handoff_path = sessions_dir / project["name"] / "latest.md"
    if not handoff_path.exists():
        return None
    match = HANDOFF_UPDATED_PATTERN.search(handoff_path.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return {"updatedAt": None, "lagCommits": None}
    updated_at = match.group(1)
    count = git_output(project["path"], "rev-list", "--count", f"--since={updated_at}", "HEAD")
    return {"updatedAt": updated_at, "lagCommits": int(count) if count and count.isdigit() else None}


def notify(title: str, message: str) -> None:
    if os.environ.get("PROJECT_REVIEW_NOTIFY", "on") == "off":
        return
    custom_command = os.environ.get("PROJECT_REVIEW_NOTIFY_CMD")
    command = [custom_command, title, message] if custom_command else [
        "osascript", "-e", "on run argv", "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
        "-e", "end run", "--", message, title]
    try:
        subprocess.run(command, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"project-review: 通知失敗：{error}", file=sys.stderr)


def run_l1(project: dict, context: dict, previous_status: Optional[dict], log_dir: Path) -> dict:
    if not context["changed"] and previous_status:
        # 沒新 commit 就沿用上次結果：否則昨天的 🔴 會在今天變成 💤，失敗被藏起來
        carried = dict(previous_status["l1"])
        carried["carried"] = True
        return carried
    timeout_seconds = int(project.get("timeoutSeconds", DEFAULT_TIMEOUT_SECONDS))
    result, checks, errors = run_checks(project, context["commit"], log_dir, timeout_seconds)
    context["errors"].extend(errors)
    failed = [name for name, check_result in checks.items() if check_result in ("fail", "crash")]
    return {"result": result, "checks": checks, "failed": failed, "carried": False}


def build_context(project: dict, state: dict, sessions_dir: Path, ran_at: str) -> dict:
    commit = git_output(project["path"], "rev-parse", "--short=12", "HEAD")
    return {"name": project["name"], "ran_at": ran_at, "commit": commit,
            "changed": commit is None or state.get("lastCommit") != commit,
            "handoff": read_handoff(project, sessions_dir) if commit else None, "errors": []}


def review_project(project: dict, paths: dict, today: str, is_forced: bool) -> str:
    project_dir = paths["reports"] / project["name"]
    project_dir.mkdir(parents=True, exist_ok=True)
    state = read_json(project_dir / "state.json") or {}
    if state.get("lastRunDay") == today and not is_forced:
        return "今天已跑過，略過（--force 可重跑）"
    context = build_context(project, state, paths["sessions"], paths["ran_at"])
    log_dir = project_dir / "logs" / today
    if context["changed"]:
        shutil.rmtree(log_dir, ignore_errors=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    if context["commit"] is None:
        context["errors"].append(f"{project['path']} 不是可讀的 git repo")
        l1 = {"result": "crash", "checks": {}, "failed": [], "carried": False}
    else:
        l1 = run_l1(project, context, read_json(project_dir / "status.json"), log_dir)
    report_path = project_dir / f"{today}.md"
    status = build_status(context, l1, report_path)
    report_path.write_text(render_report(status, log_dir), encoding="utf-8")
    write_json_atomically(project_dir / "status.json", status)
    if l1["result"] != "crash":
        # crash 不推進基準 commit，下次觸發會重試
        write_json_atomically(project_dir / "state.json", {"lastCommit": context["commit"], "lastRunDay": today})
    if status["overall"] in ("fail", "crash") and not l1.get("carried"):
        notify("Project Review", f"{project['name']}：{'測試失敗' if status['overall'] == 'fail' else '執行錯誤'}，詳見報告")
    return status["overall"]


def main() -> int:
    parser = argparse.ArgumentParser(description="專案定期 review（L0 + L1）")
    parser.add_argument("--project", help="只跑這個 name")
    parser.add_argument("--force", action="store_true", help="今天已跑過也重跑")
    parser.add_argument("--preflight", type=Path, metavar="ENTRY_JSON", help="登記前在快照上試跑一個專案項目")
    arguments = parser.parse_args()
    if arguments.preflight:
        try:
            return run_preflight(arguments.preflight)
        except ConfigError as error:
            print(f"project-review: {error}", file=sys.stderr)
            return 1
    try:
        projects = load_projects(env_path("PROJECT_REVIEW_CONFIG", "~/.config/agent-review/projects.json"))
    except ConfigError as error:
        print(f"project-review: {error}", file=sys.stderr)
        return 1
    if arguments.project:
        projects = [project for project in projects if project["name"] == arguments.project]
        if not projects:
            print(f"project-review: 登記表沒有 {arguments.project}", file=sys.stderr)
            return 1
    now = datetime.now().astimezone()
    paths = {"reports": env_path("PROJECT_REVIEW_REPORT_DIR", "~/.agent-reports/project-review"),
             "sessions": env_path("PROJECT_REVIEW_SESSIONS_DIR", "~/.agent-sessions"),
             "ran_at": now.isoformat(timespec="seconds")}
    today = os.environ.get("PROJECT_REVIEW_TODAY") or now.strftime("%Y-%m-%d")
    for project in projects:
        print(f"{project['name']}: {review_project(project, paths, today, arguments.force)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
