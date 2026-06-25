#!/bin/bash
# 輕量 metadata 寫入，不需要 Claude 介入
# 由 inject.sh 安裝至目標專案的 .git/hooks/post-commit

PROJECT_NAME=$(basename "$PWD")
PROJECT_PATH="$PWD"
SESSION_DIR="$HOME/.agent-sessions/$PROJECT_NAME"
LATEST="$SESSION_DIR/latest.md"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
LAST_COMMIT=$(git log -1 --pretty=%s 2>/dev/null || echo "—")
BRANCH=$(git branch --show-current 2>/dev/null || echo "—")

mkdir -p "$SESSION_DIR"

if [ -f "$LATEST" ]; then
  # 檔案已存在：只更新前 7 行 metadata，保留其餘內容
  BODY=$(tail -n +8 "$LATEST")
  cat > "$LATEST" <<EOF
# $PROJECT_NAME

> 路徑：$PROJECT_PATH
> 最後更新：$TIMESTAMP
> 觸發來源：git-hook
> 最後 commit：$LAST_COMMIT
> 分支：$BRANCH
$BODY
EOF
else
  # 檔案不存在：建立輕量初始版本
  cat > "$LATEST" <<EOF
# $PROJECT_NAME

> 路徑：$PROJECT_PATH
> 最後更新：$TIMESTAMP
> 觸發來源：git-hook
> 最後 commit：$LAST_COMMIT
> 分支：$BRANCH
> 狀態：🟡 進行中

## 當前焦點

—

## 進行中

—

## 下一步

—

## 卡住的點

無

## 本輪決策

—
EOF
fi
