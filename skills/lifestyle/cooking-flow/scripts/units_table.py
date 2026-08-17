#!/usr/bin/env python3
"""單位換算的正本資料表（cooking-flow 唯一數字來源）。

`references/units.md` 只寫「什麼時候該用哪種單位」與誤差說明，**不重抄任何數字**。
兩個地方各抄一份數字，正是最容易靜默漂移的地方。

密度值來自烘焙常用對照（1 cup 中筋麵粉 ≈ 125 g、1 cup 細砂糖 ≈ 200 g 等），
誤差約 ±5%。體積換重量本身就不精確，烘焙請直接秤重——這點寫在 units.md。
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import math

MASS_TO_GRAM = {
    "mg": 0.001,
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.3495,
    "lb": 453.592,
    "兩": 37.5,      # 台制一兩
    "斤": 600.0,     # 台斤
    "市斤": 500.0,   # 中國大陸市斤，與台斤差 100 g——不可互為別名
}

VOLUME_TO_ML = {
    "ml": 1.0,
    "l": 1000.0,
    "tsp": 5.0,      # 台灣食譜的「小匙／茶匙」
    "tbsp": 15.0,    # 台灣食譜的「大匙／湯匙」
    "cup": 236.588,  # 美制 cup；台灣量杯常為 240 ml，差異見 units.md
    "米杯": 180.0,   # 電鍋附的量米杯
    "floz": 29.5735,
}

# 使用者會打的各種寫法 → 正規化單位鍵
UNIT_ALIASES = {
    "毫克": "mg",
    "公克": "g", "克": "g", "gram": "g", "grams": "g",
    "公斤": "kg", "千克": "kg",
    "盎司": "oz", "ounce": "oz",
    "磅": "lb", "pound": "lb",
    "台兩": "兩",
    "台斤": "斤",
    "毫升": "ml", "cc": "ml", "c.c.": "ml", "毫公升": "ml",
    "公升": "l", "liter": "l", "litre": "l", "公升數": "l",
    "小匙": "tsp", "茶匙": "tsp", "teaspoon": "tsp", "t": "tsp",
    "大匙": "tbsp", "湯匙": "tbsp", "tablespoon": "tbsp", "T": "tbsp",
    "杯": "cup", "量杯": "cup",
    "量米杯": "米杯",
    "液量盎司": "floz", "fl oz": "floz",
}

# 食材密度（g/ml）。體積↔重量互轉時必須指定食材，否則只有水能算。
DENSITY_G_PER_ML = {
    "水": 1.00,
    "中筋麵粉": 0.53,
    "高筋麵粉": 0.55,
    "低筋麵粉": 0.50,
    "細砂糖": 0.85,
    "二砂": 0.80,
    "糖粉": 0.50,
    "鹽": 1.20,
    "白米": 0.85,
    "食用油": 0.92,
    "橄欖油": 0.92,
    "蜂蜜": 1.42,
    "牛奶": 1.03,
    "醬油": 1.15,
    "米酒": 0.98,
    "無鹽奶油": 0.91,
}

INGREDIENT_ALIASES = {
    "麵粉": "中筋麵粉", "flour": "中筋麵粉", "低粉": "低筋麵粉", "高粉": "高筋麵粉",
    "糖": "細砂糖", "白糖": "細砂糖", "砂糖": "細砂糖", "sugar": "細砂糖",
    "黃砂糖": "二砂", "紅糖": "二砂",
    "salt": "鹽", "食鹽": "鹽",
    "米": "白米", "rice": "白米",
    "油": "食用油", "沙拉油": "食用油", "oil": "食用油",
    "奶油": "無鹽奶油", "butter": "無鹽奶油",
    "milk": "牛奶", "鮮奶": "牛奶",
    "honey": "蜂蜜",
    "water": "水",
}

# 數得出顆數的單位不做任何換算，只能同名合併。
COUNT_UNITS = {
    "顆", "個", "粒", "把", "根", "支", "片", "條", "尾", "隻", "包", "盒",
    "罐", "瓣", "株", "束", "朵", "塊", "節", "張", "份",
}

# 無法量化的單位：給了數字也不能相加，「3 少許」沒有意義。
NON_QUANTIFIABLE_UNITS = {"適量", "少許", "些許", "隨意"}


class UnitError(ValueError):
    """單位無法辨識或無法換算時拋出，訊息需可直接顯示給使用者。"""


def normalize_unit(unit: str) -> str:
    """把使用者寫法正規化成資料表的鍵，認不得就原樣回傳（可能是計數單位）。"""
    cleaned = unit.strip()
    if cleaned in UNIT_ALIASES:
        return UNIT_ALIASES[cleaned]
    lowered = cleaned.lower()
    if lowered in UNIT_ALIASES:
        return UNIT_ALIASES[lowered]
    if lowered in MASS_TO_GRAM or lowered in VOLUME_TO_ML:
        return lowered
    return cleaned


def normalize_ingredient(ingredient: str) -> str:
    """食材別名正規化，用於查密度表。"""
    cleaned = ingredient.strip()
    if cleaned in DENSITY_G_PER_ML:
        return cleaned
    return INGREDIENT_ALIASES.get(cleaned, INGREDIENT_ALIASES.get(cleaned.lower(), cleaned))


def unit_dimension(unit: str) -> str:
    """回傳 'mass' / 'volume' / 'count' / 'vague'，是合併與換算的分派依據。

    認不得的單位一律報錯，不再默默當成計數單位——把打錯的「gg」當成一種
    計數單位，它就永遠不會跟 g 合併，採購清單會靜默少買或重複買。
    """
    key = normalize_unit(unit)
    if key in MASS_TO_GRAM:
        return "mass"
    if key in VOLUME_TO_ML:
        return "volume"
    if key in COUNT_UNITS:
        return "count"
    if key in NON_QUANTIFIABLE_UNITS:
        return "vague"
    known = "、".join(sorted(COUNT_UNITS | NON_QUANTIFIABLE_UNITS))
    raise UnitError(
        f"不認得單位「{unit}」。重量／體積單位見 units_table.py，"
        f"計數與模糊單位只接受：{known}"
    )


def density_of(ingredient: str) -> float:
    """查食材密度，查不到就明確報錯——不得預設 1.0 蒙混過去。"""
    key = normalize_ingredient(ingredient)
    if key not in DENSITY_G_PER_ML:
        known = "、".join(sorted(DENSITY_G_PER_ML))
        raise UnitError(
            f"密度表沒有「{ingredient}」，無法在體積與重量之間換算。"
            f"已知食材：{known}"
        )
    return DENSITY_G_PER_ML[key]


def convert(amount: float, from_unit: str, to_unit: str, ingredient: str = "") -> float:
    """單位換算。跨維度（重量↔體積）必須提供 ingredient 才能查密度。"""
    source, target = normalize_unit(from_unit), normalize_unit(to_unit)
    from_dim, to_dim = unit_dimension(source), unit_dimension(target)

    if from_dim in {"count", "vague"} or to_dim in {"count", "vague"}:
        raise UnitError(f"計數／模糊單位（{from_unit} / {to_unit}）無法換算，只能同名合併")

    if from_dim == to_dim:
        table = MASS_TO_GRAM if from_dim == "mass" else VOLUME_TO_ML
        return amount * table[source] / table[target]

    if not ingredient:
        raise UnitError(
            f"{from_unit} → {to_unit} 是重量與體積互轉，必須指定食材才能查密度"
        )
    density = density_of(ingredient)
    if from_dim == "volume":
        grams = amount * VOLUME_TO_ML[source] * density
        return grams / MASS_TO_GRAM[target]
    milliliters = amount * MASS_TO_GRAM[source] / density
    return milliliters / VOLUME_TO_ML[target]


def to_base(amount: float, unit: str, ingredient: str = "") -> "tuple[float, str]":
    """換成該維度的基準單位（g 或 ml），供採購清單合併使用。

    模糊單位一律回傳 `適量` 作為單位——「少許」與「適量」是同一件事，
    不併成一個 key 會讓清單出現兩筆長得一模一樣的列。
    """
    dimension = unit_dimension(unit)
    if dimension == "mass":
        return convert(amount, unit, "g", ingredient), "g"
    if dimension == "volume":
        return convert(amount, unit, "ml", ingredient), "ml"
    if dimension == "vague":
        return amount, "適量"
    return amount, normalize_unit(unit)


def is_finite_number(value: object) -> bool:
    """擋掉 NaN 與 Infinity。`float("nan") <= 0` 是 False，只檢查正負會漏。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def fahrenheit_to_celsius(value: float) -> float:
    return (value - 32.0) * 5.0 / 9.0


def celsius_to_fahrenheit(value: float) -> float:
    return value * 9.0 / 5.0 + 32.0


def pretty(value: float) -> str:
    """依數量級決定小數位——食譜寫 187.5 g 沒意義，寫 188 g 才可執行。"""
    if abs(value) >= 100:
        return str(int(round(value)))
    if abs(value) >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")
