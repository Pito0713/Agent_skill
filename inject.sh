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
#   - 所有情境：偵測跨專案工作流 skills 是否完整，缺少時詢問是否補齊

set -euo pipefail

PROJECT_DIR="$(pwd)"
CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"
SKILLS_BASE="@~/.claude/skills"

# 顏色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─────────────────────────────────────────
# install_hook：安裝 post-commit hook
# ─────────────────────────────────────────
install_hook() {
  if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    echo "⚠️  非 git 專案，略過 post-commit hook 安裝"
    return
  fi

  HOOK_SRC="$(cd "$(dirname "$0")" && pwd)/bin/post-commit-hook.sh"
  HOOK_DEST="$PROJECT_DIR/.git/hooks/post-commit"

  if [[ ! -f "$HOOK_SRC" ]]; then
    echo "⚠️  找不到 $HOOK_SRC，略過 hook 安裝"
    return
  fi

  if [[ -f "$HOOK_DEST" ]]; then
    echo ""
    read -r -p "已存在 post-commit hook，是否覆蓋？(y/N) " hook_confirm
    [[ ! "$hook_confirm" =~ ^[Yy]$ ]] && echo "略過 hook 安裝。" && return
  fi

  cp "$HOOK_SRC" "$HOOK_DEST"
  chmod +x "$HOOK_DEST"
  echo -e "${GREEN}✅ 已安裝 post-commit hook${NC}"
  echo "   路徑：$HOOK_DEST"
}

# ─────────────────────────────────────────
# prompt_productivity：偵測並詢問跨專案工作流 skills
# 輸出：設定全域變數 PRODUCTIVITY_ADDITION（空字串 or 要補入的區塊）
# 用法：prompt_productivity [existing_claude_md_path]
# ─────────────────────────────────────────
PRODUCTIVITY_ADDITION=""

prompt_productivity() {
  local existing_file="${1:-}"
  local missing_paths=()
  local missing_descs=()

  local skills=(
    "productivity/project-dashboard.md:project-dashboard — 查看跨專案進度總覽"
    "productivity/rag-search.md:rag-search — 搜尋 knowledge/ 內部知識庫"
    "productivity/onboarding.md:onboarding — 接手新專案快速上手"
  )

  for item in "${skills[@]}"; do
    local rel_path="${item%%:*}"
    local desc="${item##*:}"
    local full_path="${SKILLS_BASE}/${rel_path}"

    # 若有既有檔案，檢查此 skill 是否已存在
    if [[ -n "$existing_file" ]] && grep -qF "$rel_path" "$existing_file" 2>/dev/null; then
      continue
    fi
    missing_paths+=("# $full_path")
    missing_descs+=("$desc")
  done

  if [[ ${#missing_paths[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ 跨專案工作流 skills 已全部載入${NC}"
    PRODUCTIVITY_ADDITION=""
    return
  fi

  echo ""
  echo "📦 以下跨專案工作流 skills 尚未載入："
  for desc in "${missing_descs[@]}"; do
    echo "   • $desc"
  done
  echo ""
  read -r -p "是否加入按需載入清單？(y/N) " prod_confirm

  if [[ ! "$prod_confirm" =~ ^[Yy]$ ]]; then
    echo "略過跨專案工作流 skills。"
    PRODUCTIVITY_ADDITION=""
    return
  fi

  PRODUCTIVITY_ADDITION=$'\n## 跨專案工作流（按需載入）\n'
  for path in "${missing_paths[@]}"; do
    PRODUCTIVITY_ADDITION+="${path}"$'\n'
  done
}

# ─────────────────────────────────────────
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
# 常駐載入區塊內容（固定部分）
# ─────────────────────────────────────────
INJECT_BLOCK=$(cat <<BLOCK
## 常駐載入（Agent Skill）

${SKILLS_BASE}/rules/coding-standards.md
${SKILLS_BASE}/rules/security.md
${SKILLS_BASE}/rules/git.md
${SKILLS_BASE}/engineering/coding-workflow-core.md
${SKILLS_BASE}/engineering/gemini-assist.md
${SKILLS_BASE}/productivity/handoff.md
${SKILLS_BASE}/productivity/version-log.md

## 按需載入（視任務加入）
## 按需載入項目已列出（預設註解，移除 # 即可啟用）

# ${SKILLS_BASE}/rules/typescript.md
# ${SKILLS_BASE}/rules/python.md
# ${SKILLS_BASE}/engineering/coding-workflow-ref.md
# ${SKILLS_BASE}/learning/feedback-loop.md
# ${SKILLS_BASE}/learning/concrete-example.md
# ${SKILLS_BASE}/learning/academic-mentor.md
# ${SKILLS_BASE}/learning/mentor-neuro.md
# ${SKILLS_BASE}/design/wireframing.md
# ${SKILLS_BASE}/design/ui-visual-design.md
# ${SKILLS_BASE}/design/information-architecture.md
# ${SKILLS_BASE}/productivity/obsidian-query.md
# ${SKILLS_BASE}/productivity/obsidian-save.md
BLOCK
)

# ─────────────────────────────────────────
# 情境 1：沒有 CLAUDE.md → 生成新檔案
# ─────────────────────────────────────────
if [[ ! -f "$CLAUDE_MD" ]]; then
  echo "📄 未找到 CLAUDE.md，自動生成..."
  echo ""

  # 詢問跨專案工作流（無既有檔案，全部列為缺少）
  prompt_productivity ""

  PROJECT_NAME="$(basename "$PROJECT_DIR")"
  FULL_INJECT="${INJECT_BLOCK}${PRODUCTIVITY_ADDITION}"

  cat > "$CLAUDE_MD" <<EOF
# ${PROJECT_NAME}

> 專案 AI 行為規範。由 Agent Skill 自動生成。

---

${FULL_INJECT}

---

## 溝通規範

- 繁體中文溝通，技術詞彙保留英文
- 回應給極短摘要，再給可執行內容
- 指出邏輯漏洞、不為友善而同意
EOF

  echo ""
  echo -e "${GREEN}✅ 已生成 CLAUDE.md${NC}"
  echo "   路徑：$CLAUDE_MD"
  echo ""
  echo -e "${CYAN}📌 常駐載入已設定（4 個 skills）${NC}"
  echo "   按需載入項目已列出（預設註解，移除 # 即可啟用）"
  install_hook
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

  # 偵測缺少的跨專案工作流 skills（對照現有檔案）
  prompt_productivity "$CLAUDE_MD"

  # 組合最終要寫入的區塊
  FULL_INJECT="${INJECT_BLOCK}${PRODUCTIVITY_ADDITION}"

  # 抓出現有的常駐區塊預覽
  echo ""
  echo "─────────────────────────────────────────"
  echo "📋 現有 Agent Skill 區塊："
  echo ""
  awk '/## 常駐載入（Agent Skill）/{found=1} found{print} found && /^---$/{exit}' "$CLAUDE_MD"
  echo "─────────────────────────────────────────"
  echo ""
  echo "📋 新版區塊將替換為："
  echo ""
  echo "$FULL_INJECT"
  echo "─────────────────────────────────────────"
  echo ""

  read -r -p "確認更新？(y/N) " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消。"
    exit 0
  fi

  # 用 Python 替換現有區塊（保留使用者已啟用的 skills）
  python3 - "$CLAUDE_MD" "$FULL_INJECT" <<'PYEOF'
import sys

filepath = sys.argv[1]
new_block = sys.argv[2]

with open(filepath, 'r') as f:
    content = f.read()

start_marker = "## 常駐載入（Agent Skill）"
start_idx = content.find(start_marker)
if start_idx == -1:
    print("找不到區塊起點，取消。")
    sys.exit(1)

end_idx = content.find("\n---", start_idx)
if end_idx == -1:
    end_idx = len(content)
else:
    end_idx += 1

old_block = content[start_idx:end_idx]

# 找出舊區塊中使用者已啟用（去除 # 前綴）的 skill 路徑
enabled = set()
for line in old_block.splitlines():
    s = line.strip()
    if s.startswith('@') and '/.claude/skills/' in s:
        enabled.add(s)

# 在新區塊中，對使用者已啟用的 skill 還原啟用狀態
preserved = 0
new_lines = []
for line in new_block.splitlines():
    s = line.strip()
    if s.startswith('# @') and '/.claude/skills/' in s:
        path = s[2:]  # 去除 '# '
        if path in enabled:
            line = path
            preserved += 1
    new_lines.append(line)

new_block_final = '\n'.join(new_lines)
new_content = content[:start_idx] + new_block_final + "\n" + content[end_idx:]

with open(filepath, 'w') as f:
    f.write(new_content)

if preserved:
    print(f"✅ 區塊已更新（保留 {preserved} 個使用者自訂啟用項目）")
else:
    print("✅ 區塊已更新")
PYEOF

  echo ""
  echo -e "${GREEN}✅ 更新完成${NC}"
  echo "   路徑：$CLAUDE_MD"
  echo ""
  echo -e "${CYAN}📌 常駐載入已更新（4 個 skills）${NC}"
  install_hook
  exit 0
fi

# ─────────────────────────────────────────
# 情境 3：有 CLAUDE.md 但未注入過
# ─────────────────────────────────────────

# 詢問跨專案工作流（對照現有檔案）
prompt_productivity "$CLAUDE_MD"

FULL_INJECT="${INJECT_BLOCK}${PRODUCTIVITY_ADDITION}"

echo "─────────────────────────────────────────"
echo "將在 CLAUDE.md 最上方注入以下內容："
echo ""
echo "$FULL_INJECT"
echo "─────────────────────────────────────────"
echo ""

read -r -p "確認注入？(y/N) " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "已取消。"
  exit 0
fi

ORIGINAL=$(cat "$CLAUDE_MD")
cat > "$CLAUDE_MD" <<EOF
${FULL_INJECT}

---

${ORIGINAL}
EOF

echo ""
echo -e "${GREEN}✅ 注入完成${NC}"
echo "   路徑：$CLAUDE_MD"
echo ""
echo -e "${CYAN}📌 常駐載入已設定（4 個 skills）${NC}"
echo "   按需載入項目已列出（預設註解，移除 # 即可啟用）"
install_hook
