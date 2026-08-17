#!/usr/bin/env python3
"""週餐規劃的採購清單合併（模式 E）。

把多道菜的食材加總成一張清單：同食材同維度換算到基準單位相加，
計數單位只做同名合併，並標出每項食材被哪幾道菜用到——
沒有這欄，臨時抽換一道菜就不知道該刪掉哪些採購項目。

用法：
    python3 shopping_list.py week.json
    python3 shopping_list.py week.json --json
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import argparse
import json
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units_table import (  # noqa: E402
    UnitError, is_finite_number, normalize_ingredient, pretty, to_base,
    unit_dimension,
)

# 依採買動線分區，逛一次市場就能走完，不必來回折返。
#
# 比對規則是**最長關鍵字優先**，不是表格順序優先：「番茄醬」含「番茄」也含
# 「番茄醬」，只看順序會把它丟進蔬果區；「奶油」含「油」，只看順序會進調味料。
# 新增關鍵字時，只要把更精確的那個也寫進來就會自動勝出。
CATEGORY_KEYWORDS = OrderedDict([
    ("蔬果", ["蔥", "薑", "蒜", "洋蔥", "番茄", "高麗菜", "白菜", "菠菜", "青江菜",
             "紅蘿蔔", "白蘿蔔", "馬鈴薯", "地瓜", "南瓜", "茄子", "青椒", "彩椒",
             "小黃瓜", "苦瓜", "絲瓜", "玉米", "四季豆", "豆芽", "香菇", "金針菇",
             "杏鮑菇", "檸檬", "蘋果", "香蕉", "九層塔", "香菜", "辣椒", "筍"]),
    ("肉蛋豆", ["豬", "牛", "雞", "鴨", "羊", "絞肉", "培根", "香腸", "火腿",
               "蛋", "豆腐", "豆干", "豆皮", "油豆腐", "毛豆"]),
    ("海鮮", ["魚", "蝦", "蟹", "蛤", "蜊", "花枝", "透抽", "小卷", "鮭", "鯛",
             "干貝", "牡蠣", "蚵", "海帶", "紫菜"]),
    ("乾貨澱粉", ["米", "麵", "麵粉", "麵條", "冬粉", "米粉", "義大利麵", "吐司",
                 "麵包", "太白粉", "地瓜粉", "玉米粉", "木耳", "紅豆", "綠豆"]),
    ("調味料", ["鹽", "糖", "醬油", "醋", "酒", "油", "麻油", "蠔油", "味醂",
               "胡椒", "花椒", "八角", "咖哩", "番茄醬", "味噌", "豆瓣醬", "蜂蜜",
               "米酒", "米醋", "香油", "辣油", "沙拉油", "食用油", "橄欖油"]),
    ("乳製品", ["牛奶", "鮮奶", "奶油", "起司", "乳酪", "優格", "鮮奶油",
               "無鹽奶油", "有鹽奶油", "動物性鮮奶油"]),
])

# (關鍵字, 分區) 攤平後依長度遞減，最長的先比 → 精確詞永遠贏過泛用詞。
_KEYWORD_INDEX = sorted(
    ((keyword, category) for category, keywords in CATEGORY_KEYWORDS.items()
     for keyword in keywords),
    key=lambda pair: -len(pair[0]),
)


def categorize(item: str) -> str:
    """關鍵字比對分區；認不出來就進「其他」，不硬猜。"""
    for keyword, category in _KEYWORD_INDEX:
        if keyword in item:
            return category
    return "其他"


def load_plan(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            plan = json.load(handle)
    except FileNotFoundError:
        raise UnitError(f"找不到菜單檔：{path}")
    except json.JSONDecodeError as error:
        raise UnitError(f"菜單檔不是合法 JSON：{error}")

    if not isinstance(plan.get("meals"), list) or not plan["meals"]:
        raise UnitError("菜單檔需要非空的 meals 陣列")
    return plan


def accumulate(plan: dict) -> "dict[tuple, dict]":
    """把每道菜的食材累加進 (正規化食材名, 基準單位) 為鍵的桶子裡。

    合併鍵用 `normalize_ingredient()` 的正規名，否則「麵粉」與「中筋麵粉」
    會變成兩筆，照著買就會多買一份。
    """
    buckets: "dict[tuple, dict]" = OrderedDict()

    for position, meal in enumerate(plan["meals"], start=1):
        meal_name = meal.get("name", f"第 {position} 道（未命名）")
        if "ingredients" not in meal:
            raise UnitError(f"「{meal_name}」沒有 ingredients 欄位")
        if not isinstance(meal["ingredients"], list) or not meal["ingredients"]:
            raise UnitError(f"「{meal_name}」的 ingredients 必須是非空陣列")

        for entry in meal["ingredients"]:
            item, amount, unit = read_entry(entry, meal_name)
            canonical = normalize_ingredient(item)
            base_amount, base_unit = to_base(amount or 0.0, unit, item)
            quantifiable = base_unit != "適量" and amount is not None

            key = (canonical, base_unit)
            bucket = buckets.setdefault(key, {
                "item": canonical,
                "unit": base_unit,
                "total": 0.0 if quantifiable else None,
                "meals": [],
            })
            # 一旦有任何一道菜寫「適量」，這個 bucket 就永遠不可量化——
            # 把它加成數字會產出「鹽 1 適量」這種看似精確的假數量。
            if not quantifiable:
                bucket["total"] = None
            elif bucket["total"] is not None:
                bucket["total"] += base_amount
            bucket["meals"].append(meal_name)

    return buckets


def read_entry(entry: object, meal_name: str) -> "tuple[str, float, str]":
    """取出並驗證單筆食材，回傳 (item, amount 或 None, unit)。"""
    if not isinstance(entry, dict):
        raise UnitError(f"「{meal_name}」有一筆食材不是物件（{type(entry).__name__}）")
    item = str(entry.get("item", "")).strip()
    if not item:
        raise UnitError(f"「{meal_name}」有一筆食材沒有 item 欄位")

    unit = entry.get("unit", "")
    dimension = unit_dimension(unit)  # 認不得的單位在這裡就擋掉

    amount = entry.get("amount")
    if amount is None:
        if dimension != "vague":
            raise UnitError(
                f"「{meal_name}」的 {item} 沒有 amount，"
                f"只有 unit 為「適量」「少許」時才可省略"
            )
        return item, None, unit
    if not is_finite_number(amount) or amount < 0:
        raise UnitError(
            f"「{meal_name}」的 {item} 用量必須是有限非負數，收到 {amount!r}"
        )
    return item, float(amount), unit


def build_list(plan: dict) -> dict:
    """輸出分區採購清單。同食材若同時有重量與計數單位，會分列兩筆並標記。"""
    buckets = accumulate(plan)

    grouped: "dict[str, list]" = OrderedDict()
    item_unit_count: "dict[str, int]" = {}
    for (item, _), bucket in buckets.items():
        item_unit_count[item] = item_unit_count.get(item, 0) + 1

    for (item, _), bucket in buckets.items():
        category = categorize(item)
        row = {
            "item": item,
            "amount": None if bucket["total"] is None else round(bucket["total"], 2),
            "unit": bucket["unit"],
            "used_by": sorted(set(bucket["meals"])),
        }
        if item_unit_count[item] > 1:
            row["note"] = "同食材有多種單位，採買前請自行併成一種"
            row["note_level"] = "warn"
        elif category == "調味料":
            # 調味料多為常備品，列精確用量會讓人誤以為要買這個量。
            row["note"] = "常備品，確認存量即可"
            row["note_level"] = "info"
        grouped.setdefault(category, []).append(row)

    ordered = OrderedDict()
    for category in list(CATEGORY_KEYWORDS) + ["其他"]:
        if category in grouped:
            ordered[category] = sorted(grouped[category], key=lambda row: row["item"])

    return {
        "meal_count": len(plan["meals"]),
        "meals": [meal.get("name", "未命名") for meal in plan["meals"]],
        "categories": ordered,
    }


def render_text(result: dict) -> str:
    lines = [f"# 採購清單（{result['meal_count']} 道菜）", ""]
    for category, rows in result["categories"].items():
        lines.append(f"## {category}")
        for row in rows:
            amount = "適量" if row["amount"] is None else f"{pretty(row['amount'])} {row['unit']}"
            used = "、".join(row["used_by"])
            marker = "⚠️" if row.get("note_level") == "warn" else "·"
            suffix = f"  {marker} {row['note']}" if "note" in row else ""
            lines.append(f"- [ ] {row['item']}　{amount}　（{used}）{suffix}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description="週餐採購清單合併")
    parser.add_argument("file", help="菜單 JSON")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 而非 checklist")
    args = parser.parse_args()

    try:
        result = build_list(load_plan(args.file))
    except UnitError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, indent=2))
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
