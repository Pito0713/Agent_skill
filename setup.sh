#!/usr/bin/env bash
# setup.sh — 將 Agent Skill 連結到本機 ~/.claude/skills/
# 執行後，所有本機專案的 CLAUDE.md 均可 @import 這份 skill 庫

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_LINK="$CLAUDE_DIR/skills"

echo "🔧 Agent Skill Setup"
echo "   Repo: $REPO_DIR"
echo ""

# 建立 ~/.claude/ 目錄（若不存在）
if [[ ! -d "$CLAUDE_DIR" ]]; then
  mkdir -p "$CLAUDE_DIR"
  echo "✅ 建立 ~/.claude/ 目錄"
fi

# 處理已存在的 symlink 或目錄
if [[ -L "$SKILLS_LINK" ]]; then
  echo "⚠️  已存在 symlink：$SKILLS_LINK"
  echo "   舊連結：$(readlink "$SKILLS_LINK")"
  rm "$SKILLS_LINK"
  echo "   已移除舊連結"
elif [[ -d "$SKILLS_LINK" ]]; then
  echo "⚠️  $SKILLS_LINK 已是一個目錄，略過（請手動處理）"
  exit 1
fi

# 建立 symlink
ln -sf "$REPO_DIR/skills" "$SKILLS_LINK"
echo "✅ Skills 已連結："
echo "   $SKILLS_LINK → $REPO_DIR/skills"
echo ""

# 顯示可用的 skills 清單
echo "📦 可用 Skills："
find "$REPO_DIR/skills" -name "*.md" ! -path "*/_inbox/*" ! -name "convert-skill.md" \
  | sed "s|$REPO_DIR/skills/||" \
  | sort \
  | sed 's/^/   @~\/.claude\/skills\//'

echo ""
echo "─────────────────────────────────────────"
echo "📝 使用方式：在任何專案的 CLAUDE.md 加入："
echo ""
echo "   # 常駐載入（建議）"
echo "   @~/.claude/skills/engineering/coding-workflow-core.md"
echo "   @~/.claude/skills/engineering/gemini-assist.md"
echo ""
echo "   # 按需載入（視任務加入）"
echo "   @~/.claude/skills/learning/feedback-loop.md"
echo "   @~/.claude/skills/design/wireframing.md"
echo ""
echo "🔄 更新方式："
echo "   cd $REPO_DIR && git pull"
echo "   （symlink 指向原始檔，pull 後立即生效，不需重新執行 setup）"
echo "─────────────────────────────────────────"
echo ""
echo "🎉 Setup 完成！"
