#!/usr/bin/env bash
# pre-commit-audit.sh — 個人絕對路徑洩漏 lint（正本；下游以 exec wrapper 指向本檔）
#
# 對應正本條文：`~/Agent_skill/rules/security.md`（敏感資料處理——禁止洩漏可識別身分資訊）
# 設計依據：`governance/enforcement-layers.md` L2（客觀可判定的規則才下沉到腳本）
#
# 為什麼是 pre-commit 而非事後掃描：洩漏的傷害在 push 那刻發生，而 git 歷史刪不掉
# （要 rewrite history + force push）。事後掃描只能告訴你「已經寫進歷史了」。
#
# 為什麼可以用 L2 攔截（對照 ADR-015 廢除的 Stop hook）：本檢查的觸發條件是
# regex 命中，**客觀可判定、零意圖推斷**；Stop hook 廢除的原因是它要判斷「使用者
# 是否宣告收工」這種 hook 在原理上觀測不到的主觀意圖。兩者不同類。
#
# 範圍：只掃**本次 staged 的新增行**（`git diff --cached`），不翻舊帳、不掃工作區。
# 旁路：`git commit --no-verify`（git 原生），或行末加 `audit-ok` 標記。
# 失敗策略：fail-open——git 指令失敗、無 staged 內容等任何內部錯誤一律放行。

set -u

RED=$'\033[0;31m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'

# 取 staged 的新增行；任何失敗一律放行（fail-open）
DIFF=$(git diff --cached --unified=0 --no-color -- . 2>/dev/null) || exit 0
[[ -z "$DIFF" ]] && exit 0

# 只看新增行（+ 開頭，排除 +++ 檔頭）；附上所屬檔名
HITS=$(printf '%s\n' "$DIFF" | awk '
  /^\+\+\+ b\// { file = substr($0, 7); next }
  /^\+/ && !/^\+\+\+/ {
    line = substr($0, 2)
    if (line ~ /audit-ok/) next                      # 明示放行標記
    if (line ~ /\/Users\/[A-Za-z0-9._-]+/ || line ~ /file:\/\/\//) {
      printf "  %s: %s\n", file, substr(line, 1, 100)
    }
  }
')

[[ -z "$HITS" ]] && exit 0

echo ""
echo "${RED}✖ pre-commit 擋下：staged 內容含個人絕對路徑${NC}"
echo "${YELLOW}  公開 repo 會洩漏使用者名，且對他人斷鏈。${NC}"
echo ""
printf '%s\n' "$HITS"
echo ""
echo "  修法：改為 ~ 開頭（如 ~/Agent_skill/...）或 \$HOME；確定要保留就在該行加 audit-ok 標記。"
echo "  旁路：git commit --no-verify"
echo ""
exit 1
