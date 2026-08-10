"""§1.1 量測規格的唯一實作。

權威定義在 `bin/token-budget.sh` 檔頭註解與 `plans/token-budget-optimization.md` §1.1；
本模組是它的程式碼落地。畸形輸入一律 raise SpecError，不猜測——2026-08-07 的
Codex 對抗測試證明,留白會讓 parser 把 plain scalar 算成 12 bytes、tab 縮排算成
10 bytes、CRLF 讓 body 少算,而且全部 exit 0。
"""

from __future__ import annotations  # 本機為 macOS 系統 Python 3.9

import json
import os
import re

# bytes ÷ 3.5，Anthropic 口徑估算。僅供參考顯示，制度門檻一律用 bytes。
TOKEN_DIVISOR = 3.5
DELIMITER = b"---"
INDENT = b"  "
ENTRY_FILE = "CLAUDE.md"
INDEX_FILE = "skills/index.json"


class SpecError(Exception):
    """檔案不符合 §1.1 規格。報錯優於靜默算錯。"""


def resident_rules(repo: str) -> list[str]:
    """從 CLAUDE.md 的 `@` 常駐清單現算,不硬編。

    硬編的後果是接線改了工具照樣 exit 0,輸出看似精確的過期數字——
    正是本計劃在抱怨的那種「文件說有、實際沒有」。
    """
    with open(os.path.join(repo, ENTRY_FILE), encoding="utf-8") as handle:
        imports = re.findall(r"^@(\S+)$", handle.read(), re.M)
    if not imports:
        raise SpecError(f"{ENTRY_FILE}: 找不到任何 `@` 常駐載入行")
    resolved = [ENTRY_FILE]
    for relative in imports:
        if not os.path.isfile(os.path.join(repo, relative)):
            raise SpecError(f"{ENTRY_FILE} 常駐載入 `@{relative}`,但該檔不存在")
        resolved.append(relative)
    return resolved


def split_frontmatter(data: bytes, label: str) -> tuple[list[bytes], bytes]:
    """切出 frontmatter 行與 body。逐字比對 delimiter,禁止 split('---')。"""
    if b"\r\n" in data:
        raise SpecError(f"{label}: 含 CRLF 行尾,不符規格（會導致 body 少算）")
    lines = data.split(b"\n")
    if not lines or lines[0] != DELIMITER:
        raise SpecError(f"{label}: 第 1 行不是 ---")
    offset = len(lines[0]) + 1
    for index in range(1, len(lines)):
        if lines[index] == DELIMITER:
            return lines[1:index], data[offset + len(lines[index]) + 1:]
        offset += len(lines[index]) + 1
    raise SpecError(f"{label}: 找不到收尾的 --- 行")


def _description_marker(frontmatter: list[bytes], label: str) -> int:
    for index, line in enumerate(frontmatter):
        if line.startswith(b"description:"):
            marker = line[len(b"description:"):].strip()
            if marker != b"|":
                shown = marker.decode("utf-8", "replace") or "(空)"
                raise SpecError(
                    f"{label}: description 必須是 block scalar `|`,實際為 `{shown}`"
                )
            return index
    raise SpecError(f"{label}: frontmatter 缺 description")


def extract_description(frontmatter: list[bytes], label: str) -> str:
    """取 block scalar `|` 的值。

    續行須以恰好 2 個半形空格開頭,移除該 2 bytes 後原樣保留（不 strip、
    不過濾空行）。多行以 `\\n` 接合——`|` 是 literal block,保留換行;折疊成
    空格是 `>` 的語意。最後只 strip 尾隨換行。
    """
    start = _description_marker(frontmatter, label)
    collected: list[bytes] = []
    for line in frontmatter[start + 1:]:
        if line.startswith(b"\t"):
            raise SpecError(f"{label}: description 續行使用 tab 縮排,不符規格")
        if not line.startswith(INDENT):
            break
        collected.append(line[len(INDENT):])

    value = b"\n".join(collected).rstrip(b"\n")
    if not value.strip():
        raise SpecError(f"{label}: description 內容為空")
    return value.decode("utf-8")


def read_index(repo: str) -> list[dict]:
    """讀 index.json 並驗證 name / path 唯一——重複會靜默重複計費。"""
    with open(os.path.join(repo, INDEX_FILE), "rb") as handle:
        payload = json.loads(handle.read().decode("utf-8"))
    skills = payload.get("skills")
    if not isinstance(skills, list) or not skills:
        raise SpecError(f"{INDEX_FILE}: 未讀到任何 skill")
    for field in ("name", "path"):
        values = [entry[field] for entry in skills]
        duplicates = sorted({v for v in values if values.count(v) > 1})
        if duplicates:
            raise SpecError(f"{INDEX_FILE}: {field} 重複 {duplicates}")
    return skills


def collect_skills(repo: str) -> list[dict]:
    """每個 skill 的 description / body byte 數,一律 raw bytes。"""
    rows = []
    for entry in read_index(repo):
        with open(os.path.join(repo, entry["path"]), "rb") as handle:
            data = handle.read()
        frontmatter, body = split_frontmatter(data, entry["path"])
        description = extract_description(frontmatter, entry["path"])
        rows.append({
            "name": entry["name"],
            "path": entry["path"],
            "description_bytes": len(description.encode("utf-8")),
            "body_bytes": len(body),
        })
    return rows
