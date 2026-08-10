#!/usr/bin/env bash
#
# token-budget.sh — 制度層 token 成本量測
#
# 交付自 plans/token-budget-optimization.md 目標 A。
# 唯讀：不修改 repo 任何檔案（--save-baseline 除外，只寫 plans/baselines/）。
#
# 拆檔（rules/coding-standards.md 檔案 300 行上限）：
#   bin/token-budget.sh          本檔——規格權威定義 + 入口
#   bin/token_budget_spec.py     §1.1 量測規格的實作（解析）
#   bin/token_budget_report.py   三類成本彙總、baseline、delta、CLI
#
# ── 量測規格（計劃書 §1.1，本註解為唯一權威定義）─────────────────────
#
# 一律以 **raw bytes** 讀檔，不做 newline normalization。含 CRLF 的檔案直接
# 報錯——正規化會讓 body 少算，靜默算錯比報錯危險。
#
# frontmatter 邊界
#   第 1 行必須**逐字**等於 `---`；結束於其後第一個**逐字**等於 `---` 的行。
#   縮排的 `---` 不算 delimiter。禁止 split('---')——body 內有 276 條 `---` 行。
#
# description
#   必須是 block scalar `|`（plain scalar、`>`、tab 縮排、空值一律報錯）。
#   續行必須以**恰好 2 個半形空格**開頭，移除該 2 bytes 後其餘內容原樣保留
#   （不 strip、不過濾空行）。多行以 `\n` 接合——`|` 是 literal block，保留
#   換行；折疊成空格是 `>` 的語意，不是 `|` 的。最後只 strip 尾隨換行
#   （`|` 非 `|-`，解析值結尾帶 \n；不 strip 每份多算 1 byte）。
#
# bytes：UTF-8 byte 數。body：closing delimiter 之後的全部原始 bytes。
# skills/index.json 的 name / path 必須唯一——重複會靜默重複計費。
# 常駐 rules 清單從 CLAUDE.md 的 `@` 載入行**現算**，不硬編——硬編的後果是
# 接線改了工具照樣 exit 0，輸出看似精確的過期數字。
#
# ── 三類成本（計劃書 §2，禁止相加）──────────────────────────────────
#
#   固定開場成本 = 常駐 rules + 38 份 description（每 session 必付）
#   按需載入成本 = 觸發時才付 —— **不量測**，需 per-session 觸發分布，
#                  無 transcript / telemetry 支撐，不得憑假設輸出期望值
#   維護 inventory = body 總量 —— 維護量不是執行成本，不併入任何小計
#
# ── token 估算 ─────────────────────────────────────────────────────
#
#   一律 bytes ÷ 3.5，**Anthropic 口徑**，非 Codex / agy 的 token 數，
#   僅供參考顯示。制度門檻一律用 bytes（計劃書 §4 目標 B）。
#   **禁止用 tiktoken 估 Claude token**——那是 OpenAI 的 tokenizer，
#   對 Claude 低估約 15–20%，程式碼與非英文更嚴重。
#   --exact 走 Anthropic count_tokens，但**只涵蓋常駐 rules**，
#   不涵蓋 descriptions；輸出以獨立欄位標明範圍，不冒充全域精確值。
#
# 用法：
#   bin/token-budget.sh                    報表
#   bin/token-budget.sh --json             機器可讀（單一 JSON document）
#   bin/token-budget.sh --save-baseline    寫入 plans/baselines/
#   bin/token-budget.sh --compare <file>   與 baseline 比對（含 per-skill 明細）
#   bin/token-budget.sh --exact            常駐 rules 走 count_tokens
#   bin/token-budget.sh --strict           未核准超標或失效 waiver 時 exit 1
#
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$BIN_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "token-budget.sh: 需要 python3（validate-skill-index.py 亦然）" >&2
  exit 1
fi

exec python3 "$BIN_DIR/token_budget_report.py" "$REPO_ROOT" "$@"
