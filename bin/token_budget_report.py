"""三類成本報表、baseline、delta 比對、CLI。

量測本身在 `token_budget_spec.py`;本模組只負責彙總與呈現。
入口是 `bin/token-budget.sh`,規格權威定義在該檔檔頭註解。
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_budget_render import render  # noqa: E402
from token_budget_spec import (  # noqa: E402
    TOKEN_DIVISOR, SpecError, collect_skills, resident_rules,
)

DESC_THRESHOLD_BYTES = 400
# 2026-08-10 使用者裁決：現值 25,432 bytes，保留約 18% 餘裕。
FIXED_STARTUP_BUDGET_BYTES = 30000
COUNT_TOKENS_MODEL = "claude-opus-5"
BASELINE_DIR = "plans/baselines"
KNOWN_FLAGS = {"--json", "--save-baseline", "--compare", "--exact", "--help", "--strict"}
DELTA_ROWS = [
    ("常駐 rules", "fixed_startup_cost", "resident_rules_bytes"),
    ("descriptions", "fixed_startup_cost", "descriptions_bytes"),
    ("固定開場小計", "fixed_startup_cost", "subtotal_bytes"),
    ("body inventory", "maintenance_inventory", "body_bytes"),
]


def git_revision(repo: str) -> dict:
    def run(*command: str) -> str:
        try:
            return subprocess.run(
                command, cwd=repo, capture_output=True, text=True, check=True
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    return {
        "commit": run("git", "rev-parse", "--short", "HEAD") or "nogit",
        "branch": run("git", "branch", "--show-current"),
        "dirty": bool(run("git", "status", "--porcelain")),
    }


def exact_tokens(text: str) -> tuple[int | None, str]:
    """Anthropic count_tokens。無 key 或失敗一律回 None,絕不中斷報表。

    禁止改用 tiktoken——那是 OpenAI 的 tokenizer,對 Claude 低估約 15–20%。
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "未設定 ANTHROPIC_API_KEY"
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=json.dumps({
            "model": COUNT_TOKENS_MODEL,
            "messages": [{"role": "user", "content": text}],
        }).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response).get("input_tokens"), "ok"
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
        return None, f"count_tokens 失敗：{error}"


def _description_threshold(skills: list[dict]) -> dict:
    over_limit = [row for row in skills if row["description_bytes"] > DESC_THRESHOLD_BYTES]
    over = [row for row in over_limit if not row["description_waiver"]]
    waived = [row for row in over_limit if row["description_waiver"]]
    stale = [
        row for row in skills
        if row["description_waiver"] and row["description_bytes"] <= DESC_THRESHOLD_BYTES
    ]
    def waiver_row(row: dict) -> dict:
        return {
            "name": row["name"],
            "bytes": row["description_bytes"],
            "waiver": row["description_waiver"],
        }
    return {
        "limit_bytes": DESC_THRESHOLD_BYTES,
        "total": len(skills),
        "pass": len(skills) - len(over_limit),
        "over": sorted(
            ({"name": row["name"], "bytes": row["description_bytes"]} for row in over),
            key=lambda row: -row["bytes"],
        ),
        "waived": sorted((waiver_row(row) for row in waived), key=lambda row: -row["bytes"]),
        "stale_waivers": sorted((waiver_row(row) for row in stale), key=lambda row: row["name"]),
    }


def _exact_measurement(repo: str, resident: list[str], use_exact: bool) -> tuple:
    if not use_exact:
        return None, "未啟用"
    joined = "\n".join(
        open(os.path.join(repo, relative), encoding="utf-8").read()
        for relative in resident
    )
    return exact_tokens(joined)


def build_report(repo: str, use_exact: bool) -> dict:
    resident = resident_rules(repo)
    rules = {r: os.path.getsize(os.path.join(repo, r)) for r in resident}
    skills = collect_skills(repo)
    descriptions = sum(row["description_bytes"] for row in skills)
    body = sum(row["body_bytes"] for row in skills)
    rules_total = sum(rules.values())
    value, status = _exact_measurement(repo, resident, use_exact)
    fixed_startup_total = rules_total + descriptions

    return {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "git": git_revision(repo),
        "spec": "plans/token-budget-optimization.md §1.1 / bin/token-budget.sh 檔頭註解",
        "token_estimate": {
            "method": f"bytes/{TOKEN_DIVISOR}",
            "provider": "Anthropic",
            "caveat": "非 Codex / agy 的 token 數;僅供參考,制度門檻一律用 bytes",
        },
        "exact_tokens": {
            "scope": "resident_rules_only",
            "model": COUNT_TOKENS_MODEL,
            "value": value,
            "status": status,
            "note": "不涵蓋 descriptions,因此不是固定開場成本的精確值",
        },
        "fixed_startup_cost": {
            "resident_rules_bytes": rules_total,
            "resident_rules_detail": rules,
            "descriptions_bytes": descriptions,
            "subtotal_bytes": fixed_startup_total,
            "budget_bytes": FIXED_STARTUP_BUDGET_BYTES,
            "over_budget": fixed_startup_total > FIXED_STARTUP_BUDGET_BYTES,
        },
        "on_demand_cost": {
            "measured": False,
            "reason": "需 per-session 觸發分布,無 transcript / telemetry 支撐（計劃書 §2）",
        },
        "maintenance_inventory": {
            "body_bytes": body,
            "skill_count": len(skills),
            "mean_body_bytes": round(body / len(skills)),
        },
        "description_threshold": _description_threshold(skills),
        "skills": sorted(skills, key=lambda r: -r["description_bytes"]),
    }


def _changed_skills(old: dict, report: dict) -> list[dict]:
    before_map = {r["name"]: r for r in old.get("skills", [])}
    after_map = {r["name"]: r for r in report["skills"]}
    changed = []
    for name in sorted(set(before_map) | set(after_map)):
        before, after = before_map.get(name), after_map.get(name)
        if before is None:
            changed.append({"name": name, "status": "added"})
        elif after is None:
            changed.append({"name": name, "status": "removed"})
        elif (before["description_bytes"] != after["description_bytes"]
              or before["body_bytes"] != after["body_bytes"]):
            changed.append({
                "name": name, "status": "changed",
                "description_delta": after["description_bytes"] - before["description_bytes"],
                "body_delta": after["body_bytes"] - before["body_bytes"],
            })
    return changed


def build_comparison(report: dict, baseline_path: str) -> dict:
    """彙總 + per-skill 明細。只比總量會被「一增一減」抵銷掩蓋。"""
    with open(baseline_path, encoding="utf-8") as handle:
        old = json.load(handle)
    totals = []
    for label, section, key in DELTA_ROWS:
        before = old.get(section, {}).get(key)
        after = report[section][key]
        totals.append({
            "label": label, "before": before, "after": after,
            "delta": None if before is None else after - before,
        })
    return {
        "baseline": os.path.basename(baseline_path),
        "baseline_git": old.get("git", {}).get("commit"),
        "current_git": report["git"]["commit"],
        "totals": totals,
        "changed_skills": _changed_skills(old, report),
    }


def save_baseline(repo: str, report: dict) -> str:
    """檔名含微秒 + dirty 標記;已存在一律拒寫,不靜默覆寫。"""
    directory = os.path.join(repo, BASELINE_DIR)
    os.makedirs(directory, exist_ok=True)
    stamp = report["measured_at"].replace(":", "").replace("-", "").replace(".", "")
    suffix = "-dirty" if report["git"]["dirty"] else ""
    target = os.path.join(directory, f"{stamp}-{report['git']['commit']}{suffix}.json")
    if os.path.exists(target):
        raise SpecError(f"baseline 已存在,拒絕覆寫：{target}")
    with open(target, "x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


def parse_args(argv: list[str]) -> dict:
    unknown = [a for a in argv if a.startswith("-") and a not in KNOWN_FLAGS]
    if unknown:
        raise SpecError(f"未知旗標 {unknown};可用：{sorted(KNOWN_FLAGS)}")
    compare_path = None
    if "--compare" in argv:
        position = argv.index("--compare") + 1
        if position >= len(argv) or argv[position].startswith("-"):
            raise SpecError("--compare 需要 baseline 檔路徑")
        compare_path = argv[position]
    return {
        "json": "--json" in argv,
        "exact": "--exact" in argv,
        "save": "--save-baseline" in argv,
        "compare": compare_path,
        "help": "--help" in argv,
        "strict": "--strict" in argv,
    }


def strict_failure(report: dict) -> str | None:
    threshold = report["description_threshold"]
    over_count = len(threshold["over"])
    stale_count = len(threshold["stale_waivers"])
    if not over_count and not stale_count:
        return None
    return (
        "token-budget.sh: --strict 失敗——"
        f"未核准超標 {over_count} 筆、失效 waiver {stale_count} 筆"
    )


def main() -> int:
    repo, argv = sys.argv[1], sys.argv[2:]
    try:
        args = parse_args(argv)
        if args["help"]:
            print("用法見 bin/token-budget.sh 檔頭註解")
            return 0
        report = build_report(repo, args["exact"])
        comparison = build_comparison(report, args["compare"]) if args["compare"] else None
        baseline = save_baseline(repo, report) if args["save"] else None
    except (SpecError, OSError, json.JSONDecodeError, KeyError) as error:
        print(f"token-budget.sh: {error}", file=sys.stderr)
        return 1

    if args["json"]:
        document = dict(report)
        if comparison:
            document["comparison"] = comparison
        if baseline:
            document["baseline_path"] = os.path.relpath(baseline, repo)
        print(json.dumps(document, ensure_ascii=False, indent=2))
    else:
        render(repo, report, comparison, baseline)
    failure = strict_failure(report) if args["strict"] else None
    if failure:
        print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
