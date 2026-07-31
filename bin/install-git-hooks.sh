#!/usr/bin/env bash
# install-git-hooks.sh — 在下游專案安裝指向正本的 git hook wrapper。
#
# 用法：bash bin/install-git-hooks.sh [--preflight|--install|--all]
#       專案目錄取自 $AGENT_SKILL_PROJECT_DIR，未設則用 $PWD
#
# 為什麼獨立成一支而不放進 inject-<harness>.sh：git hook 與 harness 無關，
# 三個 harness 共用同一份 .git/hooks（ADR-013 按 harness 拆分的理由不適用）。
#
# 安裝的是 3 行 wrapper，不複製邏輯（ADR-016）：git 只認 .git/hooks/<固定檔名>，
# 沒有「填路徑」的欄位，wrapper 是唯一能達成「指向正本」的方式。
#
# 保守原則（與 FIX-3 一致）：**絕不覆蓋非本專案安裝的既有 hook**，只警告。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="${AGENT_SKILL_PROJECT_DIR:-$(pwd)}"

CANON_REL="Agent_skill/hooks/pre-commit-audit.sh"
MARKER="$CANON_REL"          # 用來辨識「這份 hook 是我們裝的」
CANON_ABS="$REPOSITORY_DIR/hooks/pre-commit-audit.sh"

read -r -d '' WRAPPER <<'WRAP' || true
#!/usr/bin/env bash
# 由 ~/Agent_skill 注入（bin/install-git-hooks.sh）；邏輯在正本，本檔勿手改。
# fail-open：正本遺失 / 不可執行 / $HOME 解析失敗 → 放行，不擋 commit。
CANON="$HOME/Agent_skill/hooks/pre-commit-audit.sh"
[ -x "$CANON" ] || exit 0
exec "$CANON" "$@"
WRAP

# 回傳 hooks 目錄路徑；非 git repo 回傳空字串
hooks_dir() {
  git -C "$PROJECT_DIR" rev-parse --git-path hooks 2>/dev/null || true
}

run_preflight() {
  if ! git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    echo "ℹ️  非 git repo，略過 git hook 安裝。"
    return 0
  fi

  # core.hooksPath 會讓 .git/hooks 完全不被執行——裝了也沒用，明講而不是靜默
  local hp
  hp="$(git -C "$PROJECT_DIR" config --get core.hooksPath || true)"
  if [[ -n "$hp" ]]; then
    # 注意 ${hp} 必須加大括號：後接全形標點時 bash 會把多位元組字元吃進變數名，
    # 配上 set -u 就是 unbound variable 硬失敗（2026-07-31 實測踩到）
    echo "⚠️  本專案設了 core.hooksPath=${hp}，.git/hooks 不會被執行；略過安裝。" >&2
    return 0
  fi

  if [[ ! -x "$CANON_ABS" ]]; then
    echo "⚠️  正本不可執行：${CANON_ABS}（需 chmod +x）——裝了 wrapper 也只會 fail-open 放行。" >&2
    return 1
  fi

  local hd target
  hd="$(hooks_dir)"
  target="$PROJECT_DIR/$hd/pre-commit"
  if [[ -f "$target" ]] && ! grep -q "$MARKER" "$target" 2>/dev/null; then
    echo "⚠️  已存在非本專案安裝的 pre-commit hook：$target" >&2
    echo "   → 不會覆蓋。要啟用個人路徑 lint 請手動把下列一行加進該 hook：" >&2
    echo "     \"\$HOME/$CANON_REL\" \"\$@\" || exit 1" >&2
  fi
}

run_install() {
  git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1 || return 0
  [[ -z "$(git -C "$PROJECT_DIR" config --get core.hooksPath || true)" ]] || return 0

  local hd target
  hd="$(hooks_dir)"
  target="$PROJECT_DIR/$hd/pre-commit"

  # 部分 repo 沒有 .git/hooks 目錄（Agent_skill 自己曾是；commit 6170e81 修過同一問題）
  mkdir -p "$(dirname "$target")"

  if [[ -f "$target" ]] && ! grep -q "$MARKER" "$target" 2>/dev/null; then
    echo "⏭  保留既有 pre-commit hook，未安裝 wrapper：$target"
    return 0
  fi

  printf '%s\n' "$WRAPPER" > "$target"
  chmod +x "$target"
  echo "✅ git hook：pre-commit wrapper → $target"
}

MODE="${1:---all}"
case "$MODE" in
  --preflight | --install | --all) ;;
  *)
    echo "用法：$0 [--preflight|--install|--all]" >&2
    exit 2
    ;;
esac

[[ "$MODE" == "--install" ]] || run_preflight
[[ "$MODE" == "--preflight" ]] || run_install
