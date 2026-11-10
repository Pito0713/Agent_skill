"""project_review_report.py — 組 status.json 與每日報告 markdown。

status.json 給 Floating 等程式讀（每次整份覆蓋）；報告給人看。
overall 依優先序取最嚴重者：fail > crash > warn > ok > idle（stale 由讀取端依 ranAt 判斷）。
"""

import json
import os
from pathlib import Path
from typing import Optional

from project_review_checks import tail_of

# 讀取端：~/Floating/Sources/FloatingAgenda/Data/ReviewStatus.swift——改欄位或 overall 值域時要同步改那邊（ADR-032）
STATUS_SCHEMA_VERSION = 1
RESULT_LABELS = {"pass": "✅ 通過", "flaky": "⚠️ flaky（重跑才過）", "fail": "🔴 失敗",
                 "crash": "💥 執行錯誤", "none": "— 未設定檢查", "skipped": "💤 無變更，沿用上次"}


def compute_overall(status: dict) -> str:
    l1_result = status["l1"]["result"]
    review_layers = (status["l2"], status["l3"])
    if l1_result == "fail" or any(layer["highSeverity"] > 0 for layer in review_layers):
        return "fail"
    if l1_result == "crash" or any(layer["result"] == "crash" for layer in review_layers):
        return "crash"
    if l1_result == "flaky" or any(layer["newFindings"] > 0 for layer in review_layers):
        return "warn"
    return "ok" if status["changed"] else "idle"


def skipped_review_layer() -> dict:
    # L2 / L3 在 P2 / P3 才啟用；先固定欄位，讓讀取端的 schema 不必改
    return {"result": "skipped", "newFindings": 0, "highSeverity": 0}


def build_status(context: dict, l1: dict, report_path: Path) -> dict:
    status = {
        "schema": STATUS_SCHEMA_VERSION,
        "project": context["name"],
        "ranAt": context["ran_at"],
        "commit": context["commit"],
        "changed": context["changed"],
        "l1": l1,
        "l2": skipped_review_layer(),
        "l3": skipped_review_layer(),
        "handoff": context["handoff"],
        "reportPath": str(report_path),
        "errors": context["errors"],
    }
    status["overall"] = compute_overall(status)
    return status


def write_json_atomically(path: Path, payload: dict) -> None:
    # 先寫暫存檔再 rename：讀取端（Floating）不會讀到寫一半的 JSON
    temporary_path = path.with_name(path.name + ".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, path)


def read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def render_handoff_line(handoff: Optional[dict]) -> str:
    if handoff is None:
        return "- 交接檔：無"
    lag = handoff["lagCommits"]
    lag_text = "未知" if lag is None else f"{lag} commits"
    return f"- 交接檔最後更新：{handoff['updatedAt'] or '解析不出'}（之後新增 {lag_text}）"


def render_l1_section(status: dict, log_dir: Path) -> list:
    l1 = status["l1"]
    lines = ["## L1 確定性檢查", "", f"彙總：{RESULT_LABELS.get(l1['result'], l1['result'])}"]
    if l1.get("carried"):
        lines.append("（沒有新 commit，沿用上次結果）")
    if l1["checks"]:
        lines += ["", "| 檢查 | 結果 |", "|------|------|"]
        lines += [f"| {name} | {RESULT_LABELS.get(result, result)} |" for name, result in l1["checks"].items()]
    for name, result in l1["checks"].items():
        if result in ("fail", "crash", "flaky") and not l1.get("carried"):
            log_path = log_dir / f"{name}.log"
            lines += ["", f"### {name} 輸出（末段，完整 log：`{log_path}`）", "", "```", tail_of(log_path), "```"]
    return lines


def render_report(status: dict, log_dir: Path) -> str:
    lines = [f"# {status['project']} — project review {status['ranAt'][:10]}", "",
             f"- 執行時間：{status['ranAt']}", f"- commit：`{status['commit']}`",
             f"- 有新 commit：{'是' if status['changed'] else '否'}",
             f"- 整體：{status['overall']}", render_handoff_line(status["handoff"]), ""]
    if status["errors"]:
        lines += ["## 錯誤", ""] + [f"- {error}" for error in status["errors"]] + [""]
    lines += render_l1_section(status, log_dir)
    lines += ["", "## L2 / L3", "", "尚未啟用（P2 / P3）。", ""]
    return "\n".join(lines)
