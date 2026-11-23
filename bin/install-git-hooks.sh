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
#
# 安裝兩個 hook：pre-commit（個人路徑 lint 等）、pre-push（個人信箱，工單 W6）。
# 首次安裝 pre-push 時把 audit.pushEmailBaseline 設成 upstream 的 tip（已公開的部分）：
# 既有歷史不回溯（使用者 2026-11-23 裁決），只擋還沒送出的 commit。不用 HEAD——
# HEAD 可能領先遠端，會把未 push 的個人信箱 commit 一起豁免（W6 冷啟動審查 HIGH）。
# 沒有 upstream 就不設（全部檢查）。已設定則不動。

set -euo pipefail

REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="${AGENT_SKILL_PROJECT_DIR:-$(pwd)}"

# git hook 名稱 → 正本檔名（相對於 hooks/）
HOOK_NAMES=(pre-commit pre-push)
canon_file() { case "$1" in pre-commit) echo pre-commit-audit.sh ;; pre-push) echo pre-push-email-audit.sh ;; esac; }

marker_for() { echo "Agent_skill/hooks/$(canon_file "$1")"; }
WRAPPER_HEADER='# 由 ~/Agent_skill 注入（bin/install-git-hooks.sh）；邏輯在正本，本檔勿手改。'

# 是不是我們裝的 wrapper：看固定檔頭，不看 marker——使用者照 preflight 建議把正本那一行
# 加進自己的 hook 後，檔案也會含 marker，只比 marker 會把他的 hook 整份覆蓋（W6 審查 HIGH）
is_managed_wrapper() { [[ -f "$1" ]] && grep -qxF "$WRAPPER_HEADER" "$1" 2>/dev/null; }

# 印出 wrapper 內容。單引號 heredoc 讓 $HOME 留到執行時才展開
print_wrapper() {
  local canon; canon="$(canon_file "$1")"
  printf '#!/usr/bin/env bash\n'
  printf '%s\n' "$WRAPPER_HEADER"
  printf '# fail-open：正本遺失 / 不可執行 / $HOME 解析失敗 → 放行。\n'
  printf 'CANON="$HOME/Agent_skill/hooks/%s"\n' "$canon"
  printf '[ -x "$CANON" ] || exit 0\n'
  printf 'exec "$CANON" "$@"\n'
}

# 回傳 hooks 目錄路徑；非 git repo 回傳空字串
# 一律回傳絕對路徑：linked worktree 下 --git-path 本來就回絕對路徑，接在 $PROJECT_DIR 後面會接錯（W6 審查）
hooks_dir() {
  local hd
  hd="$(git -C "$PROJECT_DIR" rev-parse --path-format=absolute --git-path hooks 2>/dev/null)" && { echo "$hd"; return 0; }
  hd="$(git -C "$PROJECT_DIR" rev-parse --git-path hooks 2>/dev/null)" || return 0   # git < 2.31 沒有 --path-format
  [[ "$hd" == /* ]] && echo "$hd" || echo "$PROJECT_DIR/$hd"
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

  local name canon_abs hd target status=0
  hd="$(hooks_dir)"
  for name in "${HOOK_NAMES[@]}"; do
    canon_abs="$REPOSITORY_DIR/hooks/$(canon_file "$name")"
    if [[ ! -x "$canon_abs" ]]; then
      echo "⚠️  正本不可執行：${canon_abs}（需 chmod +x）——裝了 wrapper 也只會 fail-open 放行。" >&2
      status=1; continue
    fi
    target="$hd/$name"
    if [[ -f "$target" ]] && ! is_managed_wrapper "$target"; then
      echo "⚠️  已存在非本專案安裝的 ${name} hook：${target}" >&2
      echo "   → 不會覆蓋。要啟用請手動把下列一行加進該 hook：" >&2
      echo "     \"\$HOME/$(marker_for "$name")\" \"\$@\" || exit 1" >&2
    fi
  done
  return "$status"
}

run_install() {
  git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1 || return 0
  [[ -z "$(git -C "$PROJECT_DIR" config --get core.hooksPath || true)" ]] || return 0

  local name hd target
  hd="$(hooks_dir)"
  # 部分 repo 沒有 .git/hooks 目錄（Agent_skill 自己曾是；commit 6170e81 修過同一問題）
  mkdir -p "$hd"
  for name in "${HOOK_NAMES[@]}"; do
    target="$hd/$name"
    if [[ -f "$target" ]] && ! is_managed_wrapper "$target"; then
      echo "⏭  保留既有 ${name} hook，未安裝 wrapper：${target}"
      continue
    fi
    print_wrapper "$name" > "$target"
    chmod +x "$target"
    echo "✅ git hook：${name} wrapper → ${target}"
  done
  set_push_email_baseline
}

# 首次安裝才設；已設定（含使用者手動調整過）一律不動。基準點 = upstream tip（已公開的部分）
set_push_email_baseline() {
  git -C "$PROJECT_DIR" config --get audit.pushEmailBaseline >/dev/null 2>&1 && return 0
  local upstream unpushed
  upstream="$(git -C "$PROJECT_DIR" rev-parse -q --verify '@{upstream}' 2>/dev/null)" || {
    echo "ℹ️  pre-push email：目前分支沒有 upstream，不設基準點（push 時檢查全部 commit）"
    return 0
  }
  git -C "$PROJECT_DIR" config audit.pushEmailBaseline "$upstream"
  echo "✅ pre-push email 基準點：${upstream:0:7}（upstream，已公開的部分）"
  unpushed="$(git -C "$PROJECT_DIR" rev-list --count "${upstream}..HEAD" 2>/dev/null || echo 0)"
  [[ "$unpushed" == 0 ]] || echo "⚠️  有 ${unpushed} 個未 push 的 commit 不在豁免範圍：其中若有個人信箱，push 會被擋" >&2
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
