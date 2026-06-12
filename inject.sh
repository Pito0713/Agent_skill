#!/usr/bin/env bash
# inject.sh — 在目標專案注入 Agent Skill 的常駐載入設定
#
# 使用方式（在你要開發的專案目錄下執行）：
#   bash ~/Agent_skill/inject.sh
#
# 功能：
#   - 沒有 CLAUDE.md → 自動生成含常駐 skill 的模板
#   - 已有 CLAUDE.md，未注入過 → 詢問確認後注入常駐 skill 區塊
#   - 已有 CLAUDE.md，已注入過 → 顯示現有區塊，詢問是否更新

set -euo pipefail

PROJECT_DIR="$(pwd)"
CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"
SKILLS_BASE="@~/.claude/skills"

# 顏色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "🔧 Agent Skill Inject"
echo "   專案目錄：$PROJECT_DIR"
echo ""

# ─────────────────────────────────────────
# 確認 ~/.claude/skills 是否已設定
# ─────────────────────────────────────────
if [[ ! -d "$HOME/.claude/skills" ]]; then
  echo "⚠️  找不到 ~/.claude/skills/"
  echo "   請先執行 setup.sh 完成初始安裝："
  echo "   bash ~/Agent_skill/setup.sh"
  exit 1
fi

# ─────────────────────────────────────────
# 常駐載入區塊內容
# ─────────────────────────────────────────
INJECT_BLOCK="## 常駐載入（Agent Skill）

${SKILLS_BASE}/rules/coding-standards.md
${SKILLS_BASE}/rules/security.md
${SKILLS_BASE}/engineering/coding-workflow-core.md
${SKILLS_BASE}/engineering/gemini-assist.md

## 按需載入（視任務加入）

# ${SKILLS_BASE}/rules/typescript.md         # TypeScript 專案
# ${SKILLS_BASE}/rules/python.md             # Python 專案
# ${SKILLS_BASE}/rules/git.md                # commit / PR 時
# ${SKILLS_BASE}/engineering/coding-workflow-ref.md   # 查實作模式
# ${SKILLS_BASE}/learning/feedback-loop.md            # 刻意練習
# ${SKILLS_BASE}/learning/concrete-example.md         # 邏輯舉例說明
# ${SKILLS_BASE}/design/wireframing.md                # 頁面規劃
# ${SKILLS_BASE}/design/ui-visual-design.md           # 視覺風格
# ${SKILLS_BASE}/design/information-architecture.md   # 導航架構"

# ─────────────────────────────────────────
# 情境 1：沒有 CLAUDE.md → 生成新檔案
# ─────────────────────────────────────────
if [[ ! -f "$CLAUDE_MD" ]]; then
  echo "📄 未找到 CLAUDE.md，自動生成..."

  PROJECT_NAME="$(basename "$PROJECT_DIR")"

  cat > "$CLAUDE_MD" <<EOF
# ${PROJECT_NAME}

> 專案 AI 行為規範。由 Agent Skill 自動生成。

---

${INJECT_BLOCK}

---

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應給極短摘要，再給可執行內容
- 指出邏輯漏洞、不為友善而同意
EOF

  echo -e "${GREEN}✅ 已生成 CLAUDE.md${NC}"
  echo "   路徑：$CLAUDE_MD"
  echo ""
  echo -e "${CYAN}📌 常駐載入已設定（4 個 skills）${NC}"
  echo "   按需載入項目已列出（預設註解，移除 # 即可啟用）"
  exit 0
fi

# ─────────────────────────────────────────
# 情境 2：已有 CLAUDE.md → 詢問後注入
# ─────────────────────────────────────────
echo "📄 找到現有 CLAUDE.md"
echo ""

# 檢查是否已注入過 → 若是，進入更新流程
if grep -q "Agent Skill" "$CLAUDE_MD" 2>/dev/null; then
  echo -e "${YELLOW}⚠️  CLAUDE.md 已包含 Agent Skill 設定${NC}"
  echo ""

  # 抓出現有的常駐區塊（從 ## 常駐載入 到下一個 --- 或檔案結尾）
  echo "─────────────────────────────────────────"
  echo "📋 現有 Agent Skill 區塊："
  echo ""
  awk '/## 常駐載入（Agent Skill）/{found=1} found{print} found && /^---$/{exit}' "$CLAUDE_MD"
  echo "─────────────────────────────────────────"
  echo ""
  echo "📋 新版區塊將替換為："
  echo ""
  echo "$INJECT_BLOCK"
  echo "─────────────────────────────────────────"
  echo ""

  read -r -p "確認更新？(y/N) " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消。"
    exit 0
  fi

  # 用 Python 替換現有區塊（從 ## 常駐載入（Agent Skill） 到下一個 --- 之間）
  python3 - "$CLAUDE_MD" "$INJECT_BLOCK" <<'PYEOF'
import sys

filepath = sys.argv[1]
new_block = sys.argv[2]

with open(filepath, 'r') as f:
    content = f.read()

# 找到區塊起點
start_marker = "## 常駐載入（Agent Skill）"
start_idx = content.find(start_marker)
if start_idx == -1:
    print("找不到區塊起點，取消。")
    sys.exit(1)

# 找到區塊結尾（下一個 --- 或檔案結尾）
end_idx = content.find("\n---", start_idx)
if end_idx == -1:
    end_idx = len(content)
else:
    end_idx += 1  # 保留換行符

new_content = content[:start_idx] + new_block + "\n" + content[end_idx:]

with open(filepath, 'w') as f:
    f.write(new_content)

print("✅ 區塊已更新")
PYEOF

  echo ""
  echo -e "${GREEN}✅ 更新完成${NC}"
  echo "   路徑：$CLAUDE_MD"
  echo ""
  echo -e "${CYAN}📌 常駐載入已更新（4 個 skills）${NC}"
  exit 0
fi

# 預覽注入內容
echo "─────────────────────────────────────────"
echo "將在 CLAUDE.md 最上方注入以下內容："
echo ""
echo "$INJECT_BLOCK"
echo "─────────────────────────────────────────"
echo ""

read -r -p "確認注入？(y/N) " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "已取消。"
  exit 0
fi

# 注入到最上方（保留原有內容）
ORIGINAL=$(cat "$CLAUDE_MD")
cat > "$CLAUDE_MD" <<EOF
${INJECT_BLOCK}

---

${ORIGINAL}
EOF

echo ""
echo -e "${GREEN}✅ 注入完成${NC}"
echo "   路徑：$CLAUDE_MD"
echo ""
echo -e "${CYAN}📌 常駐載入已設定（4 個 skills）${NC}"
echo "   按需載入項目已列出（預設註解，移除 # 即可啟用）"
