#!/usr/bin/env python3
"""份量換算工具：單位轉換、食譜縮放、烤溫轉換、烤模尺寸調整。

LLM 不得自行心算這四類數字，一律呼叫本工具。

用法：
    python3 scale.py convert 2 cup g --ingredient 麵粉
    python3 scale.py recipe recipe.json --servings 4
    python3 scale.py temp 350 F
    python3 scale.py pan --from 20 --to 23
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from units_table import (  # noqa: E402
    UnitError, celsius_to_fahrenheit, convert, fahrenheit_to_celsius,
    is_finite_number, normalize_ingredient, pretty, unit_dimension,
)

# 體積量測誤差最大的幾類，換算時提醒改用秤重。
WEIGH_INSTEAD = {"中筋麵粉", "高筋麵粉", "低筋麵粉", "糖粉"}


def load_recipe(path: str) -> dict:
    """讀取食譜 JSON，欄位缺失一律當錯誤——靜默補預設值會產出錯的份量。"""
    try:
        with open(path, encoding="utf-8") as handle:
            recipe = json.load(handle)
    except FileNotFoundError:
        raise UnitError(f"找不到食譜檔：{path}")
    except json.JSONDecodeError as error:
        raise UnitError(f"食譜檔不是合法 JSON：{error}")

    for field in ("base_servings", "ingredients"):
        if field not in recipe:
            raise UnitError(f"食譜檔缺少必要欄位「{field}」")
    if not is_finite_number(recipe["base_servings"]) or recipe["base_servings"] <= 0:
        raise UnitError("base_servings 必須是有限正數")
    if not isinstance(recipe["ingredients"], list) or not recipe["ingredients"]:
        raise UnitError("ingredients 必須是非空陣列")

    for position, entry in enumerate(recipe["ingredients"], start=1):
        validate_ingredient(entry, position)
    return recipe


def validate_ingredient(entry: object, position: int) -> None:
    """逐筆檢查食材。寧可整份拒收，也不要靜默補一個看起來合理的預設值。"""
    label = f"第 {position} 筆食材"
    if not isinstance(entry, dict):
        raise UnitError(f"{label} 不是物件（收到 {type(entry).__name__}）")
    if not str(entry.get("item", "")).strip():
        raise UnitError(f"{label} 缺少 item")

    unit = entry.get("unit", "")
    unit_dimension(unit)  # 認不得的單位在這裡就擋掉

    amount = entry.get("amount")
    if amount is None:
        if unit_dimension(unit) != "vague":
            raise UnitError(
                f"{label}（{entry['item']}）沒有 amount，"
                f"只有 unit 為「適量」「少許」時才可省略"
            )
        return
    if not is_finite_number(amount) or amount < 0:
        raise UnitError(f"{label}（{entry['item']}）的 amount 必須是有限非負數，收到 {amount!r}")


def scale_entry(entry: dict, factor: float) -> dict:
    """縮放單一食材。`to_taste` 的放大／縮小／不變三種情況註記不同。"""
    item = entry.get("item", "")
    unit = entry.get("unit", "")
    amount = entry.get("amount")

    if amount is None:
        return {"item": item, "amount": None, "unit": unit, "note": "適量"}

    scaled_amount = round(float(amount) * factor, 4)
    if not entry.get("to_taste") or factor == 1:
        return {"item": item, "amount": scaled_amount, "unit": unit}
    if factor > 1:
        return {
            "item": item, "amount": amount, "unit": unit,
            "note": "未依比例放大，起手先放原量再試味調整",
        }
    return {
        "item": item, "amount": scaled_amount, "unit": unit,
        "note": "已依比例縮減，起鍋前仍要試味",
    }


def scale_recipe(recipe: dict, servings: float) -> dict:
    """依人數等比縮放。

    `to_taste` 的調味料只在**放大**時不跟著等比放大（3 倍的鹽會鹹到不能吃，
    起手用原量再補比較安全）。縮小時必須照比例減——8 人份的鹽留給 1 人份，
    鹹度會是 8 倍，比放大更難救。
    """
    if not is_finite_number(servings) or servings <= 0:
        raise UnitError(f"目標份數必須是有限正數，收到 {servings!r}")
    factor = servings / float(recipe["base_servings"])

    scaled = [scale_entry(entry, factor) for entry in recipe["ingredients"]]

    return {
        "name": recipe.get("name", ""),
        "base_servings": recipe["base_servings"],
        "target_servings": servings,
        "factor": round(factor, 4),
        "ingredients": scaled,
    }


def pan_area_factor(from_size: float, to_size: float, shape: str) -> float:
    """烤模換算走面積比，不是邊長比——直徑放大 15% 面積就多 32%。"""
    if not is_finite_number(from_size) or not is_finite_number(to_size):
        raise UnitError("烤模尺寸必須是有限數字（cm）")
    if from_size <= 0 or to_size <= 0:
        raise UnitError("烤模尺寸必須是正數（cm）")
    if shape == "round":
        return (to_size ** 2) / (from_size ** 2)
    if shape == "square":
        return (to_size ** 2) / (from_size ** 2)
    raise UnitError(f"未知的烤模形狀：{shape}（支援 round / square）")


def run_convert(args: argparse.Namespace) -> dict:
    if not is_finite_number(args.amount) or args.amount < 0:
        raise UnitError(f"換算數量必須是有限非負數，收到 {args.amount!r}")
    value = convert(args.amount, args.from_unit, args.to_unit, args.ingredient)
    warnings = []
    if unit_dimension(args.from_unit) != unit_dimension(args.to_unit):
        warnings.append("體積↔重量換算誤差約 ±5%，密度值見 units_table.py")
    canonical = normalize_ingredient(args.ingredient) if args.ingredient else ""
    if canonical in WEIGH_INSTEAD:
        warnings.append(f"{canonical} 的杯量誤差大（壓實與否可差 20%），建議直接秤重")
    return {
        "input": f"{pretty(args.amount)} {args.from_unit}",
        "output": f"{pretty(value)} {args.to_unit}",
        "value": round(value, 4),
        "ingredient": args.ingredient or None,
        "warnings": warnings,
    }


def run_recipe(args: argparse.Namespace) -> dict:
    return scale_recipe(load_recipe(args.file), args.servings)


def run_temp(args: argparse.Namespace) -> dict:
    if not is_finite_number(args.value):
        raise UnitError(f"溫度必須是有限數字，收到 {args.value!r}")
    scale = args.scale.upper()
    if scale == "F":
        celsius = fahrenheit_to_celsius(args.value)
        return {"input": f"{pretty(args.value)}°F", "output": f"{pretty(celsius)}°C"}
    if scale == "C":
        fahrenheit = celsius_to_fahrenheit(args.value)
        return {"input": f"{pretty(args.value)}°C", "output": f"{pretty(fahrenheit)}°F"}
    raise UnitError(f"溫標只支援 C 或 F，收到：{args.scale}")


def run_pan(args: argparse.Namespace) -> dict:
    factor = pan_area_factor(args.from_size, args.to_size, args.shape)
    return {
        "from": f"{pretty(args.from_size)} cm {args.shape}",
        "to": f"{pretty(args.to_size)} cm {args.shape}",
        "factor": round(factor, 4),
        "warnings": ["麵糊高度改變會影響烘烤時間，換模後從原時間的 80% 開始試探"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cooking-flow 份量換算工具")
    sub = parser.add_subparsers(dest="command", required=True)

    convert_cmd = sub.add_parser("convert", help="單位換算")
    convert_cmd.add_argument("amount", type=float)
    convert_cmd.add_argument("from_unit", metavar="FROM")
    convert_cmd.add_argument("to_unit", metavar="TO")
    convert_cmd.add_argument("--ingredient", default="", help="重量↔體積互轉時必填")
    convert_cmd.set_defaults(handler=run_convert)

    recipe_cmd = sub.add_parser("recipe", help="依人數縮放整份食譜")
    recipe_cmd.add_argument("file")
    recipe_cmd.add_argument("--servings", type=float, required=True)
    recipe_cmd.set_defaults(handler=run_recipe)

    temp_cmd = sub.add_parser("temp", help="烤箱溫度轉換")
    temp_cmd.add_argument("value", type=float)
    temp_cmd.add_argument("scale", help="輸入值的溫標：C 或 F")
    temp_cmd.set_defaults(handler=run_temp)

    pan_cmd = sub.add_parser("pan", help="烤模尺寸換算（面積比）")
    pan_cmd.add_argument("--from", dest="from_size", type=float, required=True)
    pan_cmd.add_argument("--to", dest="to_size", type=float, required=True)
    pan_cmd.add_argument("--shape", default="round", choices=["round", "square"])
    pan_cmd.set_defaults(handler=run_pan)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = args.handler(args)
    except UnitError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
