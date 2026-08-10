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
# 旁路：`git commit --no-verify`（git 原生），或該行加獨立的 `audit-ok` 標記
#       （必須是獨立 token——`audit-oklahoma` 這種子字串不算，2026-07-31 review 修正）。
# 失敗策略：fail-open——git 指令失敗、無 staged 內容等任何內部錯誤一律放行。
#
# 已知限制（2026-07-31 獨立 review 實測確認，皆為刻意接受的取捨）：
#   1. binary 檔不掃：git diff 對 binary 不產生 `+` 行。編譯產物內嵌 build path
#      屬此漏洞，但改掃 binary 成本與誤報都太高。
#   2. 個人目錄底下只有單一 segment 時會誤報：例如同名的 REST 路由會被擋  (audit-ok)
#      （`/Users/:id` 不會——冒號不在字元類）。**刻意不收窄**：漏掉洩漏不可逆
#      （git 歷史刪不掉），誤報只需改寫或加 audit-ok。成本不對稱。
#   3. `file://<host>/path` 形式不命中（只抓三斜線的 `file://` + 本機路徑）。
#      若該 URL 指向個人目錄，會被第 1 條 pattern 接住。
#   4. rename 未加 `-M`：純改名會讓舊內容以新增行重掃一次。

set -u

RED=$'\033[0;31m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'

# 取 staged 的新增行；任何失敗一律放行（fail-open）
# core.quotepath=false：否則非 ASCII 檔名會被 git 輸出成 `+++ "b/\350..."`，
# 前置雙引號使檔頭 regex 失配，導致洩漏被歸屬到上一個檔名（2026-07-31 review 實測）
DIFF=$(git -c core.quotepath=false diff --cached --unified=0 --no-color -- . 2>/dev/null) || exit 0
[[ -z "$DIFF" ]] && exit 0

# 只看新增行（+ 開頭，排除 +++ 檔頭）；附上所屬檔名
HITS=$(printf '%s\n' "$DIFF" | awk '
  /^\+\+\+ "?b\// { sub(/^\+\+\+ "?b\//, ""); sub(/"$/, ""); file = $0; next }
  /^\+/ && !/^\+\+\+/ {
    line = substr($0, 2)
    # 明示放行標記：必須是獨立 token，避免 audit-oklahoma 這類子字串靜默旁路
    if (line ~ /(^|[^A-Za-z0-9_-])audit-ok([^A-Za-z0-9_-]|$)/) next
    if (line ~ /\/Users\/[A-Za-z0-9._-]+/ || line ~ /file:\/\/\//) {
      printf "  %s: %s\n", file, substr(line, 1, 100)
    }
  }
')

if [[ -n "$HITS" ]]; then
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
fi

# ── skill index 三向同步（僅 Agent_skill 本身，計劃書目標 D'）──────────────
#
# 為什麼可以用 L2 攔截：三向逐字比對是**機械可判定、零誤報**，與上面的路徑 lint
# 同類；ADR-015 廢除的 Stop hook 是要推斷「使用者是否宣告收工」這種主觀意圖，不同類。
#
# 為什麼需要它：frontmatter description 是路由的實際依據，卻是三處副本裡唯一原本
# 沒有防漂移保護的一處。手改 frontmatter 而忘了改 index.json，靜默生效、沒人會發現。
#
# 範圍：只在**本 repo**（有 skills/index.json 與 validator 才跑），且只在 staged
# 內容碰到 skills/ 時觸發——下游 repo（WakaWaka / shopee 等）共用本檔，那裡沒有
# skills/index.json，必須完全不受影響。
#
# 失敗策略：**基礎設施問題 fail-open**（無 python3、腳本不存在 → 放行）；
# **實際漂移 fail-closed**（validator 回非 0 → 擋）。這是本檢查存在的意義。
#
# 已知限制：validator 檢查**工作區**而非 staged 內容。若你只 stage 了一半的修正，
# 訊息可能與 staged diff 對不上。改成檢查 staged 內容要 git stash 或 worktree，
# 成本與風險都高於這個限制本身。

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
VALIDATOR="$ROOT/bin/validate-skill-index.py"
[[ -f "$ROOT/skills/index.json" && -x "$VALIDATOR" ]] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

STAGED=$(git diff --cached --name-only 2>/dev/null) || exit 0
printf '%s\n' "$STAGED" | grep -q '^skills/' || exit 0

VALIDATOR_OUT=$(python3 "$VALIDATOR" --repo "$ROOT" 2>&1) || {
  echo ""
  echo "${RED}✖ pre-commit 擋下：skill index 三向同步失敗${NC}"
  echo "${YELLOW}  index.json / llms.txt / frontmatter description 之間有漂移。${NC}"
  echo ""
  printf '%s\n' "$VALIDATOR_OUT" | sed 's/^/  /'
  echo ""
  echo "  修法：只改 skills/index.json，再跑 bin/gen-skill-frontmatter.py --write"
  echo "        （禁止手改 frontmatter——它是生成產物）"
  echo "  旁路：git commit --no-verify"
  echo ""
  exit 1
}

exit 0
