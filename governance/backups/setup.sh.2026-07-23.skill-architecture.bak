#!/usr/bin/env bash
# setup.sh — 將 Agent Skill 正本接線到三個 harness
#   Claude Code：~/.claude/skills + ~/.claude/governance（目錄 symlink）
#   Codex      ：~/.codex/AGENTS.md → repo/AGENTS.md（全域指令檔）
#   Antigravity：~/.gemini/GEMINI.md → repo/GEMINI.md（全域指令檔）

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_LINK="$CLAUDE_DIR/skills"
GOVERNANCE_LINK="$CLAUDE_DIR/governance"
CODEX_LINK="$HOME/.codex/AGENTS.md"
AGY_LINK="$HOME/.gemini/GEMINI.md"
CLAUDE_GLOBAL_LINK="$CLAUDE_DIR/CLAUDE.md"

echo "🔧 Agent Skill Setup"
echo "   Repo: $REPO_DIR"
echo ""

# 建立 ~/.claude/ 目錄（若不存在）
if [[ ! -d "$CLAUDE_DIR" ]]; then
  mkdir -p "$CLAUDE_DIR"
  echo "✅ 建立 ~/.claude/ 目錄"
fi

# 前置檢查：任一目標是實體目錄就先退出——此時尚未動任何 symlink，
# 不會出現「舊鏈已刪、新鏈未建」的斷鏈中間態
if [[ ! -L "$SKILLS_LINK" && -d "$SKILLS_LINK" ]]; then
  echo "⚠️  $SKILLS_LINK 已是一個目錄，略過（請手動處理）"
  exit 1
fi
if [[ ! -L "$GOVERNANCE_LINK" && -d "$GOVERNANCE_LINK" ]]; then
  echo "⚠️  $GOVERNANCE_LINK 已是一個目錄，略過（請手動處理）"
  exit 1
fi
if [[ ! -L "$CODEX_LINK" && -e "$CODEX_LINK" ]]; then
  echo "⚠️  $CODEX_LINK 已是一個實體檔案，略過（請先備份後手動移除）"
  exit 1
fi
if [[ ! -L "$AGY_LINK" && -e "$AGY_LINK" ]]; then
  echo "⚠️  $AGY_LINK 已是一個實體檔案，略過（請先備份後手動移除）"
  exit 1
fi
if [[ ! -L "$CLAUDE_GLOBAL_LINK" && -e "$CLAUDE_GLOBAL_LINK" ]]; then
  echo "⚠️  $CLAUDE_GLOBAL_LINK 已是一個實體檔案，略過（請先備份後手動移除）"
  exit 1
fi

# 移除已存在的舊 symlink
if [[ -L "$SKILLS_LINK" ]]; then
  echo "⚠️  已存在 symlink：$SKILLS_LINK"
  echo "   舊連結：$(readlink "$SKILLS_LINK")"
  rm "$SKILLS_LINK"
  echo "   已移除舊連結"
fi

if [[ -L "$GOVERNANCE_LINK" ]]; then
  echo "⚠️  已存在 symlink：$GOVERNANCE_LINK"
  echo "   舊連結：$(readlink "$GOVERNANCE_LINK")"
  rm "$GOVERNANCE_LINK"
  echo "   已移除舊連結"
fi

# 建立 symlink
ln -sf "$REPO_DIR/skills" "$SKILLS_LINK"
echo "✅ Skills 已連結："
echo "   $SKILLS_LINK → $REPO_DIR/skills"

ln -sf "$REPO_DIR/governance" "$GOVERNANCE_LINK"
echo "✅ Governance 已連結："
echo "   $GOVERNANCE_LINK → $REPO_DIR/governance"

# Codex / Antigravity 全域指令檔（檔案 symlink；ln -sf 可原子覆蓋舊 symlink）
mkdir -p "$HOME/.codex" "$HOME/.gemini"
ln -sf "$REPO_DIR/AGENTS.md" "$CODEX_LINK"
echo "✅ Codex 全域 AGENTS.md 已連結："
echo "   $CODEX_LINK → $REPO_DIR/AGENTS.md"

ln -sf "$REPO_DIR/GEMINI.md" "$AGY_LINK"
echo "✅ Antigravity 全域 GEMINI.md 已連結："
echo "   $AGY_LINK → $REPO_DIR/GEMINI.md"

ln -sf "$REPO_DIR/CLAUDE.global.md" "$CLAUDE_GLOBAL_LINK"
echo "✅ Claude 全域 CLAUDE.md 已連結："
echo "   $CLAUDE_GLOBAL_LINK → $REPO_DIR/CLAUDE.global.md"
echo ""

# 顯示可用的 skills 清單
echo "📦 可用 Skills："
find "$REPO_DIR/skills" -name "*.md" ! -path "*/_inbox/*" ! -name "convert-skill.md" \
  | sed "s|$REPO_DIR/skills/||" \
  | sort \
  | sed 's/^/   @~\/.claude\/skills\//'

echo ""
echo "─────────────────────────────────────────"
echo "📝 使用方式：在目標專案執行 inject.sh 自動注入（建議，含完整常駐/按需清單）："
echo ""
echo "   cd ~/my-project && bash $REPO_DIR/inject.sh"
echo ""
echo "   或手動在專案 CLAUDE.md 加入，例如："
echo "   @~/.claude/skills/rules/coding-standards.md"
echo "   @~/.claude/skills/rules/security.md"
echo "   @~/.claude/skills/engineering/coding-workflow-core.md"
echo ""
echo "🔄 更新方式："
echo "   cd $REPO_DIR && git pull"
echo "   （symlink 指向原始檔，pull 後立即生效，不需重新執行 setup）"
echo "─────────────────────────────────────────"
echo ""
echo "🎉 Setup 完成！"
