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

# 只用在「顯示」：awk 的 substr 在 macOS BWK awk 按 byte 截斷，會切壞中文字元。
# 判斷一律用原始內容，不得用轉換後的結果——iconv 失敗時輸出可能不完整，拿來判斷會漏擋。
to_valid_utf8() {
  if command -v iconv >/dev/null 2>&1; then iconv -c -f UTF-8 -t UTF-8 2>/dev/null; else cat; fi
  return 0
}

# 取 staged 的新增行；任何失敗一律放行（fail-open）
# core.quotepath=false：否則非 ASCII 檔名會被 git 輸出成 `+++ "b/\350..."`，
# 前置雙引號使檔頭 regex 失配，導致洩漏被歸屬到上一個檔名（2026-07-31 review 實測）
# --src-prefix/--dst-prefix：使用者設了 diff.noprefix 或 diff.mnemonicPrefix 時，檔頭不會是 b/，
# 下面的 awk 會認不出檔名（2026-11-24 codex 審查）
DIFF=$(git -c core.quotepath=false diff --cached --unified=0 --no-color --src-prefix=a/ --dst-prefix=b/ -- . 2>/dev/null) || exit 0
[[ -z "$DIFF" ]] && exit 0

# 只看新增行（+ 開頭，排除 +++ 檔頭）；附上所屬檔名
HITS=$(printf '%s\n' "$DIFF" | awk '
  /^diff --git / { in_header = 1; next }
  /^@@/ { in_header = 0; next }
  in_header && /^\+\+\+ "?b\// { sub(/^\+\+\+ "?b\//, ""); sub(/"$/, ""); file = $0; next }
  in_header { next }
  /^\+/ {
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
  printf '%s\n' "$HITS" | to_valid_utf8
  echo ""
  echo "  修法：改為 ~ 開頭（如 ~/Agent_skill/...）或 \$HOME；確定要保留就在該行加 audit-ok 標記。"
  echo "  旁路：git commit --no-verify"
  echo ""
  exit 1
fi

# ── 延後註解提醒（警告級，不擋；計劃書 agent-env-trust-pyramid T5）──────────
#
# 為什麼需要它：agent 常以延後註解代替完成就回報「做完了」，與 judgment-rubrics R2
# 衝突。關鍵字可 regex 判定，git hook 三 harness 皆生效。
#
# 為什麼只警告：文件與字串常數裡的同字樣會誤報。觀察兩週誤報率再決定是否升為攔截。
# 位置：必須在下方「僅本 repo」閘門之前，否則下游 repo 跑不到。
# 旁路：同上，該行加獨立的 audit-ok 標記。

DEFERRED=$(printf '%s\n' "$DIFF" | awk '
  /^diff --git / { in_header = 1; next }
  /^@@/ { in_header = 0; next }
  in_header && /^\+\+\+ "?b\// { sub(/^\+\+\+ "?b\//, ""); sub(/"$/, ""); file = $0; next }
  in_header { next }
  /^\+/ {
    line = substr($0, 2)
    if (line ~ /(^|[^A-Za-z0-9_-])audit-ok([^A-Za-z0-9_-]|$)/) next
    if (line ~ /(^|[^A-Za-z])(TODO|FIXME)([^A-Za-z]|$)/ || line ~ /之後補|暫時/ || tolower(line) ~ /for now/) {  # audit-ok
      printf "  %s: %s\n", file, substr(line, 1, 100)
    }
  }
')

if [[ -n "$DEFERRED" ]]; then
  echo "" >&2
  echo "${YELLOW}⚠ pre-commit 提醒（不擋）：staged 新增行含延後註解${NC}" >&2
  printf '%s\n' "$DEFERRED" | to_valid_utf8 >&2
  echo "  延後不等於完成：要延後就記進專案待辦並告知使用者；誤報可在該行加 audit-ok 標記。" >&2
  echo "" >&2
fi

# ── shell 變數緊接多位元組字元（警告級，不擋；工單 W2，lessons 2026-07-31）────
#
# 為什麼需要它：bash 會把變數名後面緊接的多位元組字元（全形標點、中文）一起吃進
# 變數名，配 set -u 直接 unbound variable。這條路徑常在錯誤分支裡，平常跑不到，
# 2026-11-23 本 repo 新寫的三支測試又全部踩到。改寫成 ${VAR} 即可。
#
# 判定：LC_ALL=C 下按 byte 比，變數名後面不是 tab 也不是可列印 ASCII → 多位元組。
# 不用 grep -P：macOS 舊版與部分下游環境沒有 PCRE。
# 排除：註解行（# 開頭）、跳脫的字面 \$（前面奇數個反斜線；"\\$x" 是字面反斜線＋展開，照樣抓）。只查 *.sh / *.bash。

BARE_VARS=$(printf '%s\n' "$DIFF" | LC_ALL=C awk '
  /^diff --git / { in_header = 1; next }
  /^@@/ { in_header = 0; next }
  in_header && /^\+\+\+ "?b\// { sub(/^\+\+\+ "?b\//, ""); sub(/"$/, ""); file = $0; next }
  in_header { next }
  /^\+/ && file ~ /\.(sh|bash)$/ {
    line = substr($0, 2)
    if (line ~ /^[[:space:]]*#/) next
    if (line ~ /(^|[^A-Za-z0-9_-])audit-ok([^A-Za-z0-9_-]|$)/) next
    if (line ~ /(^|[^\\])(\\\\)*\$[A-Za-z_][A-Za-z0-9_]*[^\t -~]/) printf "  %s: %s\n", file, substr(line, 1, 100)
  }
')

if [[ -n "$BARE_VARS" ]]; then
  echo "" >&2
  echo "${YELLOW}⚠ pre-commit 提醒（不擋）：shell 變數後面緊接多位元組字元${NC}" >&2
  printf '%s\n' "$BARE_VARS" | to_valid_utf8 >&2
  echo "  bash 會把後面的字元吃進變數名（set -u 下直接崩）：改寫成 \${VAR}；誤報可在該行加 audit-ok 標記。" >&2
  echo "" >&2
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
[[ -f "$ROOT/skills/index.json" ]] || exit 0

# ── skill 裡直接寫 codex exec（僅本 repo，不依賴 python3 / validator；skill 體檢 B2，lessons 2026-11-22）──────
#
# 為什麼需要它：codex 唯讀委派的安全旗標與 </dev/null 都收在 bin/codex-ro.sh（T6 C4），
# 但沒有東西擋住 skill 或派工模板重新出現直接寫的 codex exec——一處漏改就繞過 wrapper。
# 判定：skills/ 與 governance/delegation-templates.md 的新增行含 `codex exec`，且後面
# 不是緊接反引號（`codex exec` 用反引號包起來是在講這個指令，不是在呼叫它）。
# 失敗策略：命中即擋（fail-closed）；說明文字誤報可在該行加 audit-ok 標記。

RAW_CODEX=$(printf '%s\n' "$DIFF" | awk '
  /^diff --git / { in_header = 1; next }
  /^@@/ { in_header = 0; next }
  in_header && /^\+\+\+ "?b\// { sub(/^\+\+\+ "?b\//, ""); sub(/"$/, ""); file = $0; next }
  in_header { next }
  /^\+/ && (file ~ /^skills\// || file == "governance/delegation-templates.md") {
    line = substr($0, 2)
    if (line ~ /(^|[^A-Za-z0-9_-])audit-ok([^A-Za-z0-9_-]|$)/) next
    if (line ~ /(^|[^A-Za-z0-9_-])codex[[:space:]]+exec([^A-Za-z0-9_`-]|$)/) printf "  %s: %s\n", file, substr(line, 1, 100)
  }
')

if [[ -n "$RAW_CODEX" ]]; then
  echo ""
  echo "${RED}✖ pre-commit 擋下：skill / 派工模板直接寫 codex exec${NC}"
  echo ""
  printf '%s\n' "$RAW_CODEX" | to_valid_utf8
  echo ""
  echo "  修法：改用 ~/Agent_skill/bin/codex-ro.sh [--web] [--stdin] [-o 檔] -- \"<prompt>\""
  echo "        （固定帶唯讀旗標、沒帶 --stdin 自動接 /dev/null）；只是在說明指令就用反引號包住或加 audit-ok"
  echo "  旁路：git commit --no-verify"
  echo ""
  exit 1
fi

VALIDATOR="$ROOT/bin/validate-skill-index.py"
[[ -x "$VALIDATOR" ]] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

STAGED=$(git diff --cached --name-only 2>/dev/null) || exit 0

# ── 改到哪支就跑哪支的測試（僅本 repo；工單 W3 段 1，lessons 2026-09-30）──────
#
# 為什麼需要它：測試存在但沒有任何東西會自動執行它，紅了也沒人看到（09-30 實證兩週半）。
# 範圍：staged 碰到對照表左欄 → 跑右欄的測試；對照表就是「哪支程式由哪支測試守」的正本。
# 失敗策略：測試檔不存在 → 略過（fail-open）；測試非 0 → 擋（fail-closed）。
# 已知限制：跟 validator 一樣測的是**工作區**不是 staged 內容。test-skill-health 約 34 秒，
# 只在改到 skill-health 相關檔才跑。test-token-budget.sh 目前既有失敗（未查根因），修好前不接，否則改到預算檔就被擋。
# git 執行 hook 時會 export GIT_INDEX_FILE 等變數，測試在臨時 repo 跑 git 會誤用 → 一律清掉。

TEST_MAP='^bin/(skill-usage\.py|lib_skill_usage\.py|test-skill-usage\.sh)$ test-skill-usage.sh
^bin/(skill[-_]health|test-skill-health) test-skill-health.sh
^bin/(test-)?knowledge-grep\.sh$ test-knowledge-grep.sh
^(hooks/pre-commit-audit\.sh|bin/test-pre-commit-audit\.sh)$ test-pre-commit-audit.sh
^(hooks/pre-push-email-audit\.sh|bin/test-pre-push-email-audit\.sh)$ test-pre-push-email-audit.sh
^(hooks/pre-(commit|push)-[a-z-]+\.sh|bin/(test-)?install-git-hooks\.sh)$ test-install-git-hooks.sh
^bin/(validate-skill-index\.py|test-validate-skill-index\.sh)$ test-validate-skill-index.sh
^bin/(test-)?worktree-base-check\.sh$ test-worktree-base-check.sh
^bin/(project-review\.py|project_review_[a-z]+\.py|install-project-review-schedule\.sh|test-project-review\.sh)$ test-project-review.sh
^bin/(scan-downstream\.sh|test-fix-3\.sh)$ test-fix-3.sh
^bin/(test-)?codex-ro\.sh$ test-codex-ro.sh
^(bin/(test-)?detect-stack\.sh|skills/engineering/coding-workflow-core/SKILL\.md)$ test-detect-stack.sh
^(bin/(test-)?vault-env\.sh|skills/productivity/(obsidian-save|knowledge-search)/SKILL\.md|skills/learning/_shared/mentor-protocol\.md|skills/lifestyle/cooking-flow/SKILL\.md)$ test-vault-env.sh
^bin/(project-dashboard\.py|test-project-dashboard\.sh)$ test-project-dashboard.sh'

RELATED_TESTS=$(printf '%s\n' "$TEST_MAP" | while read -r pattern test_name; do
  printf '%s\n' "$STAGED" | grep -qE "$pattern" && echo "$test_name"
done | sort -u)

for test_name in $RELATED_TESTS; do
  test_file="$ROOT/bin/$test_name"
  [[ -f "$test_file" ]] || continue
  TEST_OUT=$(cd "$ROOT" && env -u GIT_INDEX_FILE -u GIT_DIR -u GIT_WORK_TREE -u GIT_PREFIX \
    bash "$test_file" 2>&1) || {
    echo ""
    echo "${RED}✖ pre-commit 擋下：相關測試失敗 bin/${test_name}${NC}"
    echo ""
    printf '%s\n' "$TEST_OUT" | grep -E 'FAIL|Error|錯誤' | head -n 15 | sed 's/^/  /'
    echo ""
    echo "  完整輸出：bash bin/${test_name}"
    echo "  旁路：git commit --no-verify"
    echo ""
    exit 1
  }
  echo "✓ pre-commit：bin/${test_name} 通過" >&2
done

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

# ── 制度層預算 --strict（maintenance-protocol §8.6）─────────────────────────
#
# 為什麼需要它：§8.6 寫明 --strict 給 pre-commit 用，但原本沒接上、靠人記得跑。
# 實證：tw-market-rotation 以 425 bytes（門檻 400）、無 waiver 進了 main，沒人發現。
#
# 範圍與失敗策略同上方 validator：沿用其「本 repo + staged 碰到 skills/」閘門
# （description 與 waiver 都在 skills/ 下）；腳本不存在 → 放行；--strict 非 0
# （未核准超標、失效 waiver、工具自身報錯）→ 擋。固定開場成本超 30,000 在
# --strict 下仍 exit 0（具名說明制，不是硬牆），不會被本檢查擋。

BUDGET="$ROOT/bin/token-budget.sh"
[[ -f "$BUDGET" ]] || exit 0

BUDGET_OUT=$(bash "$BUDGET" --strict 2>&1 >/dev/null) || {
  echo ""
  echo "${RED}✖ pre-commit 擋下：制度層預算 --strict 失敗${NC}"
  echo ""
  printf '%s\n' "$BUDGET_OUT" | sed 's/^/  /'
  echo ""
  echo "  明細：bash bin/token-budget.sh"
  echo "  修法：壓縮 description 到 400 bytes 內；waiver 只有使用者能核准（§8.3），不得為過關自補"
  echo "  旁路：git commit --no-verify"
  echo ""
  exit 1
}

exit 0
