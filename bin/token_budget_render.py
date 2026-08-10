"""報表呈現層。

只負責把 `token_budget_report.build_report()` 的 dict 印成人類可讀格式;
不做任何量測。規格權威定義在 `bin/token-budget.sh` 檔頭註解。
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_budget_spec import TOKEN_DIVISOR  # noqa: E402


def approx_tokens(byte_count: int) -> int:
    return round(byte_count / TOKEN_DIVISOR)


def _render_costs(report: dict) -> None:
    fixed = report["fixed_startup_cost"]
    inventory = report["maintenance_inventory"]

    print("【固定開場成本】每 session 必付")
    for relative, size in fixed["resident_rules_detail"].items():
        print(f"    {relative:<48}{size:>9,}")
    print(f"    {'常駐 rules 小計':<46}{fixed['resident_rules_bytes']:>9,}")
    print(f"    {'frontmatter description 總計':<46}{fixed['descriptions_bytes']:>9,}")
    print(f"    {'─' * 46}{'─' * 9}")
    subtotal = fixed["subtotal_bytes"]
    budget = fixed["budget_bytes"]
    usage = subtotal / budget * 100
    print(f"    {'小計':<46}{subtotal:>9,} / {budget:,} bytes ({usage:.1f}%)"
          f"  ≈ {approx_tokens(subtotal):,} tokens *")
    if fixed["over_budget"]:
        print("    ⚠️  固定開場成本超過預算；依 governance/maintenance-protocol.md §8"
              " 須具名說明，並非禁止。")

    exact = report["exact_tokens"]
    if exact["value"] is not None:
        print(f"    {'（常駐 rules 精確值,不含 descriptions）':<44}{exact['value']:>9,} tokens")
    elif exact["status"] != "未啟用":
        print(f"    （--exact 未取得精確值：{exact['status']}）")

    print("\n【按需載入成本】觸發時才付")
    print(f"    未量測 —— {report['on_demand_cost']['reason']}")
    print("\n【維護 inventory】非執行成本,不併入任何小計")
    print(f"    {'SKILL.md body 總計':<46}{inventory['body_bytes']:>9,} bytes")
    print(f"    {'平均每個 skill':<46}{inventory['mean_body_bytes']:>9,} bytes\n")


def _render_comparison(comparison: dict) -> None:
    print(f"【與 baseline 比對】{comparison['baseline']}")
    print(f"    baseline git: {comparison['baseline_git']}  →  現在: {comparison['current_git']}")
    for row in comparison["totals"]:
        if row["delta"] is None:
            print(f"    {row['label']:<24} baseline 無此欄位")
            continue
        mark = "  " if row["delta"] == 0 else ("↑" if row["delta"] > 0 else "↓")
        sign = "+" if row["delta"] > 0 else ""
        print(f"    {row['label']:<24}{row['before']:>9,} → {row['after']:>9,}"
              f"   {mark} {sign}{row['delta']:,}")
    changed = comparison["changed_skills"]
    print(f"    per-skill 變動：{len(changed)} 個"
          f"{'（總量抵銷時這裡仍會顯示）' if changed else ''}")
    for row in changed[:20]:
        if row["status"] == "changed":
            print(f"      {row['name']:<40} desc {row['description_delta']:+,}"
                  f"  body {row['body_delta']:+,}")
        else:
            print(f"      {row['name']:<40} {row['status']}")
    print()


def render(repo: str, report: dict, comparison: dict | None, baseline: str | None) -> None:
    git = report["git"]
    threshold = report["description_threshold"]

    print("Token Budget — Agent_skill")
    print(f"  git      : {git['commit']} ({git['branch']})"
          f"{'  ⚠️ 工作區有未 commit 變更' if git['dirty'] else ''}")
    print(f"  measured : {report['measured_at']}")
    print(f"  spec     : {report['spec']}\n")

    _render_costs(report)

    print(f"【description 門檻】{threshold['limit_bytes']} bytes"
          f" — 通過 {threshold['pass']} / {threshold['total']}")
    for row in threshold["over"]:
        print(f"    ⚠️  {row['name']:<44}{row['bytes']:>9,}")
    if threshold["over"]:
        print("    （超標須具名 waiver,見計劃書 §4 目標 C）")
    else:
        print("    無未核准超標")
    if threshold["waived"]:
        print("\n    【已核准 waiver】")
        for row in threshold["waived"]:
            print(f"    ✓   {row['name']:<44}{row['bytes']:>9,}")
            print(f"        {row['waiver']}")
    if threshold["stale_waivers"]:
        print("\n    【waiver 已失效，應從 index.json 移除】")
        for row in threshold["stale_waivers"]:
            print(f"    ⚠️  {row['name']:<44}{row['bytes']:>9,}")
            print(f"        {row['waiver']}")
    print()

    if comparison:
        _render_comparison(comparison)
    if baseline:
        print(f"baseline 已存：{os.path.relpath(baseline, repo)}\n")

    estimate = report["token_estimate"]
    print(f"* token 為 {estimate['method']} 估算,{estimate['provider']} 口徑。{estimate['caveat']}")
