#!/usr/bin/env python3
"""project-dashboard.py — 跨專案總覽（project-dashboard skill Phase 1–3；計劃書 plans/t6-bash-extraction.md C3）。

用法：python3 bin/project-dashboard.py [--sessions-dir DIR] [--today YYYY-MM-DD]
exit：0 有輸出（個別專案讀取失敗只標在該列）/ 1 沒有任何 latest.md / 2 找不到 git

讀 <sessions-dir>/*/latest.md 的交接欄位，並對每個專案 repo **現跑 git**（分支、未 commit 數、
交接後又幾個 commit）。輸出 markdown 總覽表，最後一行列出需要展開的專案（🔴 / 有 Blocker / 落後 >5）。
latest.md 裡殘留的「最後 commit」「分支」是過期快取，一律不讀（2026-07-31 前由已刪除的 hook 寫入）。

為什麼抽成 script：表裡每個數字都要對 N 個 repo 跑 git，模型逐專案手算容易漏跑或抄錯；
「數字由 script 算，模型只判讀」（T6 C3）。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

LAG_WARNING_THRESHOLD = 5
FOCUS_MAX_CHARS = 30
# 冒號後只吃同一行的空白：用 \s* 會跨過換行，欄位留空時抓到下一行（C3 審查 HIGH）
FIELD_PATTERN = r"^>[ \t]*{}：[ \t]*(\S.*?)[ \t]*$"
UPDATED_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?$")
GIT_TIMEOUT_SECONDS = 10
# 路徑來自 latest.md，可能指向不受信任的 repo：關掉 fsmonitor 等會執行外部指令的設定
GIT_SAFETY = ["-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false"]
# 從 git hook 或帶 GIT_DIR 的環境執行時，-C 蓋不過這些變數 → 每個專案都讀到同一個 repo（codex 審查）
GIT_ENVIRONMENT = {key: value for key, value in os.environ.items()
                   if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX",
                                  "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE")}


def read_field(text: str, label: str) -> Optional[str]:
    match = re.search(FIELD_PATTERN.format(label), text, re.MULTILINE)
    return match.group(1) if match else None


def section_lines(text: str, heading: str) -> list:
    """`## heading` 之後、下一個 `## ` 之前的非空行。"""
    match = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def git(repo: Path, *arguments: str) -> Optional[str]:
    try:
        completed = subprocess.run(["git", *GIT_SAFETY, "-C", str(repo), *arguments],
                                   capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
                                   env=GIT_ENVIRONMENT)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def parse_updated(updated: Optional[str]) -> Optional[float]:
    """「最後更新」→ epoch 秒（本機時區）。只有日期視為當天 00:00；格式不合 → None（顯示 ?）。"""
    match = UPDATED_PATTERN.match(updated or "")
    if not match:
        return None
    try:   # 格式對但日期不存在（2026-02-30）也算解析不了，不能讓整列變成讀取失敗（codex 審查）
        moment = datetime.strptime(f"{match.group(1)} {match.group(2) or '00:00'}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return moment.astimezone().timestamp()


def count_commits_since(repo: Path, since_epoch: float) -> Optional[int]:
    """所有本機分支上 committer date ≥ 交接時間的 commit 數。自己數，不用 --since：
    git 遇到時間倒退的 commit 會提早停止走訪；只看本機分支，不把別人 push 的 commit 算進來。"""
    output = git(repo, "log", "--branches", "--format=%ct")
    if output is None:
        return None
    return sum(1 for line in output.splitlines() if line.strip().isdigit() and int(line) >= since_epoch)


def repo_columns(path: Optional[str], updated: Optional[str]) -> dict:
    """分支 / 未 commit / 落後；路徑不存在或不是 git repo → STALE；交接時間解析不了 → 落後顯示 ?。"""
    repo = Path(path.strip("`")).expanduser() if path else None   # 交接檔常把路徑包在反引號裡
    if repo is None or git(repo, "rev-parse", "--git-dir") is None:
        return {"lag": "STALE", "branch": "—", "dirty": "—", "lag_count": None}
    branch = git(repo, "branch", "--show-current") or "(detached)"
    porcelain = git(repo, "status", "--porcelain")
    dirty = "?" if porcelain is None else str(len([line for line in porcelain.splitlines() if line.strip()]))
    since_epoch = parse_updated(updated)
    lag_count = None if since_epoch is None else count_commits_since(repo, since_epoch)
    if lag_count is None:
        return {"lag": "?", "branch": branch, "dirty": dirty, "lag_count": None}
    lag = f"{lag_count} ⚠️" if lag_count > LAG_WARNING_THRESHOLD else str(lag_count)
    return {"lag": lag, "branch": branch, "dirty": dirty, "lag_count": lag_count}


def is_no_blocker(line: str) -> bool:
    """只有「無」「無。」「無（備註）」算沒有 Blocker；「無法連線」「無權限」是真的卡住（C3 審查 HIGH）。"""
    text = line.lstrip("-* ").strip()
    return text in ("無", "無。") or text.startswith(("無（", "無("))


def project_row(latest: Path) -> dict:
    text = latest.read_text(encoding="utf-8", errors="replace")
    status_field = read_field(text, "狀態") or "—"
    updated = read_field(text, "最後更新")
    focus = section_lines(text, "當前焦點")
    blockers = [line for line in section_lines(text, "卡住的點") if not is_no_blocker(line)]
    row = {
        "name": latest.parent.name,
        "status": status_field.split()[0],
        "updated": updated or "—",
        "focus": truncate(focus[0], FOCUS_MAX_CHARS) if focus else "—",
        "blocker": "有" if blockers else "—",
    }
    row.update(repo_columns(read_field(text, "路徑"), updated))
    return row


def needs_expansion(row: dict) -> bool:
    lag = row["lag_count"]
    return row["status"] == "🔴" or row["blocker"] == "有" or (lag is not None and lag > LAG_WARNING_THRESHOLD)


def render(rows: list, today: str) -> str:
    lines = [f"## 跨專案狀態（{today}）", "",
             "| 專案 | 狀態 | 交接更新 | 落後 | 分支 | 未 commit | 當前焦點 | Blocker |",
             "|------|------|---------|------|------|-----------|---------|---------|"]
    for row in rows:
        cells = [row[key].replace("|", "\\|") for key in
                 ("name", "status", "updated", "lag", "branch", "dirty", "focus", "blocker")]
        lines.append("| " + " | ".join(cells) + " |")
    expand = [row["name"] for row in rows if needs_expansion(row)]
    lines += ["", f"需要展開：{'、'.join(expand) if expand else '無'}"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="跨專案總覽")
    parser.add_argument("--sessions-dir", type=Path, default=Path("~/.agent-sessions").expanduser())
    parser.add_argument("--today", default=date.today().isoformat())
    arguments = parser.parse_args()
    if shutil.which("git") is None:
        print("project-dashboard: 找不到 git", file=sys.stderr)
        return 2
    files = sorted(arguments.sessions_dir.glob("*/latest.md"))
    if not files:
        print("尚無專案紀錄，請在專案中執行 handoff 後再查看。")
        return 1
    rows = [safe_project_row(path) for path in files]
    print(render(rows, arguments.today))
    return 0


def safe_project_row(latest: Path) -> dict:
    """單一專案壞掉（讀不到、是目錄、編碼錯）只影響那一列，不中斷其他專案。"""
    try:
        return project_row(latest)
    except (OSError, ValueError) as error:
        print(f"project-dashboard: {latest.parent.name} 讀取失敗：{error}", file=sys.stderr)
        return {"name": latest.parent.name, "status": "❓", "updated": "—", "focus": "（latest.md 讀取失敗）",
                "blocker": "—", "lag": "?", "branch": "—", "dirty": "—", "lag_count": None}


if __name__ == "__main__":
    raise SystemExit(main())
