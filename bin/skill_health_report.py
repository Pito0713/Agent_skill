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
# 有執行 B 層時由 B 層章節取代；沒執行則保留
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


def load_review(results_dir: str) -> dict:
    """B 層結果：B.status 不存在 = 未啟用；ok = 已執行；其他一律當失敗（不得當通過）。"""
    status = read_text(os.path.join(results_dir, "B.status")).strip()
    if not status:
        return {"status": "skip", "output": "", "reason": ""}
    reason = read_text(os.path.join(results_dir, "B.err")).strip()
    if status != "ok":
        status, reason = "crash", reason or "B 層未記錄失敗原因"
    # 模型輸出可能含 HTML 註解開頭，避免干擾報告末尾的機器可讀註解
    output = read_text(os.path.join(results_dir, "B.out")).strip().replace("<!--", "&lt;!--")
    return {"status": status, "output": output, "reason": reason}


def review_summary(review: dict) -> str:
    if review["status"] == "skip":
        return B_LAYER_SUMMARY
    if review["status"] == "ok":
        return "已執行"
    return "💥 檢查失敗（%s）" % review["reason"].splitlines()[0]


def render_review_section(review: dict) -> list:
    if review["status"] == "ok":
        return ["## B 層模型審查", "> 以下是模型給的線索，不是結論；每條附證據與信心，請自行核對。", "",
                review["output"]]
    lines = ["## B 層模型審查", "- 💥 檢查失敗 B：" + review["reason"].splitlines()[0]]
    extra = review["reason"].splitlines()[1:]
    return lines + (["```"] + extra + ["```"] if extra else [])


def build_summary_line(commit: str, counts: dict, review_text: str) -> str:
    layer_a = " / ".join("%s %d" % (SYMBOLS[s], counts[s]) for s in STATUS_ORDER)
    return "基準 commit：%s · A 層 %s · B 層 %s" % (commit, layer_a, review_text)


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


def render_problem_report(heading, summary_line, results, comparison, note, review) -> str:
    lines = [heading, "> " + summary_line, "", "## 需要處理"]
    for check_id, _title in CHECKS:
        if results[check_id]["status"] != "ok":
            lines.append("- " + describe(check_id, results[check_id]))
    # 有執行 B 層就取代插入點；沒有則保留插入點
    lines += ["", B_LAYER_MARKER if review["status"] == "skip" else "\n".join(render_review_section(review)), ""]
    lines += render_comparison(results, comparison, note)
    lines += ["", "## 全部檢查明細"]
    for check_id, _title in CHECKS:
        result = results[check_id]
        lines.append("### " + describe(check_id, result))
        detail = format_detail(result["detail"])
        if detail:
            lines += ["```"] + detail + ["```"]
    return "\n".join(lines)


def render_green_report(heading, counts, comparison, review) -> str:
    if review["status"] == "crash":  # B 層 💥 時不得宣稱「全部通過」，只能說 A 層通過
        line = "%s — A 層全部通過（A 層 ✅ %d · B 層 %s）· 💥 B 層審查未完成，不可視為全部通過" % (
            heading, counts["ok"], review_summary(review))
    else:
        line = "%s — ✅ 全部通過（A 層 ✅ %d · B 層 %s）" % (heading, counts["ok"], review_summary(review))
    if comparison and comparison["resolved"]:
        line += " · 已解決：" + "、".join(comparison["resolved"])
    if review["status"] != "skip":  # 全綠單行之後附 B 層段落，避免 B 層結果被吞掉
        line += "\n\n" + "\n".join(render_review_section(review))
    return line


def render_machine_json(date: str, commit: str, results: dict, review_status: str) -> str:
    checks = {cid: {"status": r["status"], "summary": r["summary"], "streak": r["streak"]}
              for cid, r in results.items()}
    payload = json.dumps({"version": 1, "date": date, "commit": commit, "checks": checks,
                          "review": review_status}, ensure_ascii=False)
    # 避免內容含 "--" 提早結束 HTML 註解
    return "<!-- skill-health-json: %s -->" % payload.replace("--", "\\u002d\\u002d")


def build_report(args, results: dict, review: dict) -> tuple:
    today = datetime.date.fromisoformat(args.date)
    heading = "# Skill 體檢 %s（%s）" % (args.date, WEEKDAYS[today.weekday()])
    previous, note = load_previous(args.report_dir, args.date + ".md")
    apply_streaks(results, previous)
    comparison = compare_with_previous(results, previous) if previous is not None else None
    counts = count_symbols(results)
    summary_line = build_summary_line(args.commit, counts, review_summary(review))
    if counts["ok"] == len(CHECKS):
        body = render_green_report(heading, counts, comparison, review)
    else:
        body = render_problem_report(heading, summary_line, results, comparison, note, review)
    machine = render_machine_json(args.date, args.commit, results, review["status"])
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
    report, summary_line = build_report(args, load_results(args.results), load_review(args.results))
    write_atomically(os.path.join(args.report_dir, args.date + ".md"), report)
    write_atomically(args.summary_out, summary_line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
