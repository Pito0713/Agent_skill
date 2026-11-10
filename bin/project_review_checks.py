"""project_review_checks.py — project-review 的 L1 確定性檢查（test / lint / typecheck）。

檢查跑在 HEAD 的 git worktree 快照上，不碰使用者的工作目錄：多 harness 並行時，
原地跑會吃到其他 session 未 commit 的變更，結果不可重現。

單一檢查的結果：
  pass   第一次就過
  flaky  第一次失敗、重跑通過
  fail   兩次都失敗
  crash  逾時、指令不存在（exit 126/127）、或 worktree / setup 本身出錯
"""

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CHECK_ORDER = ("test", "lint", "typecheck")
OUTPUT_TAIL_LINES = 40
EXIT_NOT_RUNNABLE = (126, 127)
RESULT_SEVERITY = {"crash": 4, "fail": 3, "flaky": 2, "pass": 1}


class SnapshotError(Exception):
    """worktree 快照建立失敗；整個 L1 視為 crash。"""


def run_shell(command: str, cwd: Path, timeout_seconds: int, log_path: Path) -> Optional[int]:
    """跑一條 shell 指令，輸出 append 到 log；逾時回傳 None。"""
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"$ {command}\n")
        log_file.flush()
        # 開新 process group：逾時要連 npm / jest 這類衍生的子程序一起殺，否則它們會在快照被刪後繼續跑
        process = subprocess.Popen(
            ["/bin/bash", "-c", command], cwd=str(cwd), stdin=subprocess.DEVNULL,
            stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            kill_process_group(process)
            log_file.write(f"\n[project-review] 逾時（{timeout_seconds}s）\n")
            return None


def kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def create_snapshot(repo_path: Path, commit: str) -> Path:
    snapshot_root = Path(tempfile.mkdtemp(prefix="project-review-"))
    snapshot_path = snapshot_root / "tree"
    completed = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "--detach", str(snapshot_path), commit],
        capture_output=True, text=True,
    )
    if completed.returncode != 0:
        shutil.rmtree(snapshot_root, ignore_errors=True)
        raise SnapshotError(f"git worktree add 失敗：{completed.stderr.strip()}")
    return snapshot_path


def remove_snapshot(repo_path: Path, snapshot_path: Path) -> None:
    # 先用 git 移除，讓 .git/worktrees 的登記一起清掉；失敗再退回 prune，不留殘骸
    subprocess.run(["git", "-C", str(repo_path), "worktree", "remove", "--force", str(snapshot_path)],
                   capture_output=True)
    shutil.rmtree(snapshot_path.parent, ignore_errors=True)
    subprocess.run(["git", "-C", str(repo_path), "worktree", "prune"], capture_output=True)


def classify_attempt(exit_code: Optional[int]) -> str:
    if exit_code is None or exit_code in EXIT_NOT_RUNNABLE:
        return "crash"
    return "pass" if exit_code == 0 else "fail"


def run_single_check(command: str, cwd: Path, timeout_seconds: int, log_path: Path) -> str:
    first = classify_attempt(run_shell(command, cwd, timeout_seconds, log_path))
    if first != "fail":
        return first
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n[project-review] 第一次失敗，重跑一次判斷是否 flaky\n")
    second = classify_attempt(run_shell(command, cwd, timeout_seconds, log_path))
    if second == "pass":
        return "flaky"
    return second


def tail_of(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-OUTPUT_TAIL_LINES:])


def aggregate(results: Dict[str, str]) -> str:
    if not results:
        return "none"
    return max(results.values(), key=lambda result: RESULT_SEVERITY[result])


def run_checks(project: dict, commit: str, log_dir: Path, timeout_seconds: int) -> Tuple[str, Dict[str, str], List[str]]:
    """回傳 (彙總結果, {檢查名: 結果}, 錯誤訊息)。沒設定任何檢查回傳 'none'。"""
    checks = project.get("checks") or {}
    ordered = [name for name in CHECK_ORDER if checks.get(name)] + \
              sorted(name for name in checks if name not in CHECK_ORDER and checks.get(name))
    if not ordered:
        return "none", {}, []
    repo_path = Path(project["path"])
    try:
        snapshot_path = create_snapshot(repo_path, commit)
    except SnapshotError as error:
        return "crash", {}, [str(error)]
    try:
        return run_in_snapshot(project, ordered, snapshot_path, log_dir, timeout_seconds)
    finally:
        remove_snapshot(repo_path, snapshot_path)


def run_in_snapshot(project: dict, ordered: List[str], snapshot_path: Path, log_dir: Path,
                    timeout_seconds: int) -> Tuple[str, Dict[str, str], List[str]]:
    setup_command = project.get("setup")
    if setup_command:
        setup_log = log_dir / "setup.log"
        if run_shell(setup_command, snapshot_path, timeout_seconds, setup_log) != 0:
            return "crash", {}, [f"setup 失敗：{setup_command}（詳見 {setup_log}）"]
    results = {}
    for name in ordered:
        results[name] = run_single_check(project["checks"][name], snapshot_path, timeout_seconds,
                                         log_dir / f"{name}.log")
    return aggregate(results), results, []
