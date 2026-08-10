#!/usr/bin/env python3
"""從 skills/index.json 生成 38 份 SKILL.md 的 frontmatter description。

計劃書目標 D'。`index.json` 是 frontmatter description 的 canonical source；
生成規則（2026-08-07 實測 38/38 成立）：

    frontmatter.description == index.description + " 觸發：" + index.triggers

── 強制規約（計劃書 §3.2）─────────────────────────────────────────────

* **禁用 YAML round-trip。** 本機無 yaml / ruamel.yaml；自行安裝並用
  safe_load + dump 會同時造成三項禁區違規：`description: |` block 樣式被改成
  引號字串、key 順序被重排、`metadata` 的 `version: "1.0"` 轉 float、
  `last_updated` 轉 date。本工具**只做純文字行替換**。
* **禁止用「觸發」當 regex 錨點。** `metadata.trigger` 就在 description 下方
  兩行且同樣含「觸發」二字，誤中即違反禁區（`metadata:` 是禁區）。
* **只寫 canonical path**，寫入前 assert 不是 symlink——38 份 SKILL.md 的所在
  目錄同時是 `~/.claude/skills/` symlink farm 的目標。
* **--dry-run 為預設**；實際寫入須明確加 --write。

解析共用 `token_budget_spec`，不另寫一份 parser——兩份解析各自漂移正是本
計劃在修的問題。

用法：
    bin/gen-skill-frontmatter.py            列出差異（不寫入）
    bin/gen-skill-frontmatter.py --write    實際寫入
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_budget_spec import (  # noqa: E402
    DELIMITER, INDENT, SpecError, read_index, split_frontmatter,
)

SEPARATOR = " 觸發："


def expected_description(entry: dict) -> str:
    """index.json 的兩個欄位合成 frontmatter 該有的 description。"""
    return f"{entry['description']}{SEPARATOR}{entry['triggers']}"


def assert_separator_unique(entry: dict) -> None:
    """反向 split 依賴「index 的兩個欄位都不含分隔符」。現況 38/38 成立。

    不檢查就會在有人把「觸發：」寫進 description 時靜默切錯。
    """
    for field in ("description", "triggers"):
        if SEPARATOR.strip() in entry[field]:
            raise SpecError(
                f"{entry['name']}: index.json 的 {field} 含分隔符「觸發：」，"
                f"會讓反向 split 產生歧義"
            )


def locate_description_block(frontmatter: list[bytes], label: str) -> tuple[int, int]:
    """回傳 description 續行的 [起, 迄) 行索引（相對 frontmatter）。

    錨點是行首的 `description:`，不是「觸發」二字——後者會誤中
    metadata.trigger（禁區）。
    """
    start = None
    for index, line in enumerate(frontmatter):
        if line.startswith(b"description:"):
            if line[len(b"description:"):].strip() != b"|":
                raise SpecError(f"{label}: description 必須是 block scalar `|`")
            start = index + 1
            break
    if start is None:
        raise SpecError(f"{label}: frontmatter 缺 description")

    end = start
    while end < len(frontmatter):
        if frontmatter[end].startswith(b"\t"):
            raise SpecError(f"{label}: description 續行使用 tab 縮排，不符規格")
        if not frontmatter[end].startswith(INDENT):
            break
        end += 1
    if end == start:
        raise SpecError(f"{label}: description 內容為空")
    return start, end


def rebuild(data: bytes, value: str, label: str) -> bytes:
    """只替換 description 續行，frontmatter 其餘部分與 body 逐 byte 保留。"""
    frontmatter, body = split_frontmatter(data, label)
    start, end = locate_description_block(frontmatter, label)
    replacement = [INDENT + line.encode("utf-8") for line in value.split("\n")]
    rebuilt = frontmatter[:start] + replacement + frontmatter[end:]
    head = DELIMITER + b"\n" + b"\n".join(rebuilt) + b"\n" + DELIMITER + b"\n"
    return head + body


def process(repo: str, write: bool) -> tuple[list[str], list[str]]:
    """回傳（有差異的 skill, 已寫入的 skill）。"""
    differing, written = [], []
    for entry in read_index(repo):
        assert_separator_unique(entry)
        path = os.path.join(repo, entry["path"])
        with open(path, "rb") as handle:
            data = handle.read()
        rebuilt = rebuild(data, expected_description(entry), entry["path"])
        if rebuilt == data:
            continue
        differing.append(entry["path"])
        if not write:
            continue
        if os.path.islink(path):
            raise SpecError(f"{entry['path']}: 是 symlink，拒絕寫入（會斷開 farm）")
        temporary = f"{path}.gen.tmp"
        with open(temporary, "wb") as handle:
            handle.write(rebuilt)
        os.replace(temporary, path)
        written.append(entry["path"])
    return differing, written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    parser.add_argument("--write", action="store_true",
                        help="實際寫入（預設只列差異，不動檔案）")
    arguments = parser.parse_args()

    try:
        differing, written = process(arguments.repo, arguments.write)
    except (SpecError, OSError, KeyError) as error:
        print(f"gen-skill-frontmatter: {error}", file=sys.stderr)
        return 1

    if not differing:
        print("PASS: 38 份 frontmatter description 已與 index.json 一致，無需寫入")
        return 0
    mode = "已寫入" if arguments.write else "需更新（--dry-run，未寫入）"
    print(f"{mode}：{len(written or differing)} 份")
    for path in written or differing:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
