#!/usr/bin/env python3
"""skill-health 報告：讀各檢查結果 → 與上次比對 → 寫 Markdown 報告（含機器可讀 JSON）。

結果目錄內每個檢查 id 有 `<id>.status`（ok|warn|fail|crash）、`<id>.out`（stdout，
首行為摘要、其餘為明細）、`<id>.err`（stderr，crash 時當錯誤訊息）。
"""
import argparse
import datetime
import json
import os
import re
import sys

CHECKS = [
    ("A1", "index.json / llms.txt / SKILL.md 一致"),
    ("A2", "索引檔大小上限"),
    ("A3", "全域 symlink 接線"),
    ("A4", "AGENTS/GEMINI inline 段一致"),
    ("A5", "路由指向的檔案存在"),
    ("A6", "token 預算與 waiver"),
    ("A7", "下游 skill farm dangling symlink"),
    ("A8", "程式檔超過 300 行"),
    ("A9", "SKILL.md 引用路徑存在"),
    ("A10", "repo 狀態"),
]
SYMBOLS = {"ok": "✅", "warn": "⚠️", "fail": "❌", "crash": "💥"}
STATUS_ORDER = ["ok", "warn", "fail", "crash"]
WEEKDAYS = "一二三四五六日"
REPORT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
JSON_COMMENT = re.compile(r"<!-- skill-health-json: (.*?) -->", re.S)
STREAK_ALERT_THRESHOLD = 3
MAX_DETAIL_LINES = 40
B_LAYER_SUMMARY = "略過（未啟用 --with-review）"
# 下一張工單（B 層）從這裡插入其章節
B_LAYER_MARKER = "<!-- B-LAYER-INSERTION-POINT -->"


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""


def load_results(results_dir: str) -> dict:
    results = {}
    for check_id, _title in CHECKS:
        status = read_text(os.path.join(results_dir, check_id + ".status")).strip()
        lines = read_text(os.path.join(results_dir, check_id + ".out")).splitlines()
        error = read_text(os.path.join(results_dir, check_id + ".err")).strip()
        if status not in SYMBOLS:
            status, error = "crash", error or "未記錄檢查結果"
        summary = lines[0] if lines else ""
        detail = lines[1:]
        if status == "crash":
            summary = "檢查失敗：" + (error.splitlines()[-1] if error else "未知錯誤")
            detail = error.splitlines() + detail
        results[check_id] = {"status": status, "summary": summary, "detail": detail}
    return results


def load_previous(report_dir: str, today_name: str) -> tuple:
    """回傳 (上次的 checks dict 或 None, 說明)。損壞或不存在都不丟例外。"""
    names = sorted(n for n in os.listdir(report_dir)
                   if REPORT_NAME.match(n) and n < today_name)
    if not names:
        return None, "無上次報告（首次執行）"
    previous_name = names[-1]
    match = JSON_COMMENT.search(read_text(os.path.join(report_dir, previous_name)))
    if not match:
        return None, "上次報告（%s）缺少機器可讀結果，無法比對" % previous_name
    try:
        checks = json.loads(match.group(1))["checks"]
        if not isinstance(checks, dict):
            raise ValueError("checks 不是物件")
    except (ValueError, KeyError, TypeError) as error:
        return None, "上次報告（%s）的機器可讀結果損壞（%s），無法比對" % (previous_name, error)
    return checks, "上次報告：%s" % previous_name


def previous_streak(previous, check_id: str) -> int:
    entry = (previous or {}).get(check_id)
    if not isinstance(entry, dict) or entry.get("status") == "ok":
        return 0
    streak = entry.get("streak")
    return streak if isinstance(streak, int) and streak > 0 else 1


def apply_streaks(results: dict, previous) -> None:
    for check_id, result in results.items():
        is_problem = result["status"] != "ok"
        result["streak"] = previous_streak(previous, check_id) + 1 if is_problem else 0


def compare_with_previous(results: dict, previous: dict) -> dict:
    new, resolved, persisting = [], [], []
    for check_id, _title in CHECKS:
        was_problem = previous_streak(previous, check_id) > 0
        is_problem = results[check_id]["status"] != "ok"
        if is_problem and not was_problem:
            new.append(check_id)
        elif was_problem and not is_problem:
            resolved.append(check_id)
        elif is_problem:
            persisting.append(check_id)
    return {"new": new, "resolved": resolved, "persisting": persisting}


def count_symbols(results: dict) -> dict:
    return {s: sum(1 for r in results.values() if r["status"] == s) for s in STATUS_ORDER}


def build_summary_line(commit: str, counts: dict) -> str:
    layer_a = " / ".join("%s %d" % (SYMBOLS[s], counts[s]) for s in STATUS_ORDER)
    return "基準 commit：%s · A 層 %s · B 層 %s" % (commit, layer_a, B_LAYER_SUMMARY)


def describe(check_id: str, result: dict) -> str:
    symbol = SYMBOLS[result["status"]]
    label = "檢查失敗 " if result["status"] == "crash" else ""
    title = dict(CHECKS)[check_id]
    return "%s %s%s %s：%s" % (symbol, label, check_id, title, result["summary"])


def format_detail(detail: list) -> list:
    lines = detail[:MAX_DETAIL_LINES]
    if len(detail) > MAX_DETAIL_LINES:
        lines.append("…（略 %d 行）" % (len(detail) - MAX_DETAIL_LINES))
    return lines


def join_ids(ids: list) -> str:
    return "、".join(ids) if ids else "無"


def render_comparison(results: dict, comparison, note: str) -> list:
    lines = ["## 與上次相比", "- " + note]
    if comparison is None:
        return lines
    lines.append("- 新增：" + join_ids(comparison["new"]))
    lines.append("- 已解決：" + join_ids(comparison["resolved"]))
    if not comparison["persisting"]:
        lines.append("- 仍未處理：無")
    for check_id in comparison["persisting"]:
        streak = results[check_id]["streak"]
        alert = streak >= STREAK_ALERT_THRESHOLD
        mark = " 🔥 **連續 %d 次未處理，請排處理**" % streak if alert else ""
        lines.append("- 仍未處理：%s（第 %d 次出現）%s" % (check_id, streak, mark))
    return lines


def render_problem_report(heading, summary_line, results, comparison, note) -> str:
    lines = [heading, "> " + summary_line, "", "## 需要處理"]
    for check_id, _title in CHECKS:
        if results[check_id]["status"] != "ok":
            lines.append("- " + describe(check_id, results[check_id]))
    lines += ["", B_LAYER_MARKER, ""]
    lines += render_comparison(results, comparison, note)
    lines += ["", "## 全部檢查明細"]
    for check_id, _title in CHECKS:
        result = results[check_id]
        lines.append("### " + describe(check_id, result))
        detail = format_detail(result["detail"])
        if detail:
            lines += ["```"] + detail + ["```"]
    return "\n".join(lines)


def render_green_report(heading, counts, comparison) -> str:
    line = "%s — ✅ 全部通過（A 層 ✅ %d · B 層 %s）" % (heading, counts["ok"], B_LAYER_SUMMARY)
    if comparison and comparison["resolved"]:
        line += " · 已解決：" + "、".join(comparison["resolved"])
    return line


def render_machine_json(date: str, commit: str, results: dict) -> str:
    checks = {cid: {"status": r["status"], "summary": r["summary"], "streak": r["streak"]}
              for cid, r in results.items()}
    payload = json.dumps({"version": 1, "date": date, "commit": commit, "checks": checks},
                         ensure_ascii=False)
    # 避免內容含 "--" 提早結束 HTML 註解
    return "<!-- skill-health-json: %s -->" % payload.replace("--", "\\u002d\\u002d")


def build_report(args, results: dict) -> tuple:
    today = datetime.date.fromisoformat(args.date)
    heading = "# Skill 體檢 %s（%s）" % (args.date, WEEKDAYS[today.weekday()])
    previous, note = load_previous(args.report_dir, args.date + ".md")
    apply_streaks(results, previous)
    comparison = compare_with_previous(results, previous) if previous is not None else None
    counts = count_symbols(results)
    summary_line = build_summary_line(args.commit, counts)
    if counts["ok"] == len(CHECKS):
        body = render_green_report(heading, counts, comparison)
    else:
        body = render_problem_report(heading, summary_line, results, comparison, note)
    machine = render_machine_json(args.date, args.commit, results)
    return body + "\n" + machine + "\n", summary_line


def write_atomically(path: str, content: str) -> None:
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(temporary, path)


def parse_args(argv: list):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--summary-out", required=True)
    return parser.parse_args(argv)


def main(argv: list) -> int:
    args = parse_args(argv)
    os.makedirs(args.report_dir, exist_ok=True)
    report, summary_line = build_report(args, load_results(args.results))
    write_atomically(os.path.join(args.report_dir, args.date + ".md"), report)
    write_atomically(args.summary_out, summary_line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
