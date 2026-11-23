#!/usr/bin/env bash
# worktree-base-check.sh — 派 worktree executor 前確認基底；本地領先 upstream 時印出要貼進工單的「第 0 步」
#
# 用法：worktree-base-check.sh [分支]（預設目前分支）
# 輸出：本地 == upstream → 無輸出；本地領先 → 「第 0 步」文字塊（原樣貼進工單最前面）
# exit：0 可以派工（含需要第 0 步）/ 2 本地與 upstream 分歧或無法判斷 → 先處理再派工
#
# 為什麼：harness 的 worktree 隔離是從 origin 開分支，不是從本地 HEAD。本地 main 領先
# origin 時，executor 看不到未 push 的檔案；它未改檔就停下時 worktree 會被清掉，
# 補授權只能重派（lessons 2026-11-09，工單 W4）。

set -u

branch="${1:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null)}"
[[ -n "$branch" && "$branch" != HEAD ]] || { echo "worktree-base-check: 無法判斷分支（detached HEAD？）" >&2; exit 2; }

local_sha=$(git rev-parse -q --verify "refs/heads/${branch}") || { echo "worktree-base-check: 找不到分支 ${branch}" >&2; exit 2; }
upstream_sha=$(git rev-parse -q --verify "${branch}@{upstream}" 2>/dev/null) || {
  echo "worktree-base-check: ${branch} 沒有 upstream，無法判斷 worktree 的基底——請在工單寫明基底 sha ${local_sha}" >&2
  exit 2
}

[[ "$local_sha" == "$upstream_sha" ]] && exit 0

if ! git merge-base --is-ancestor "$upstream_sha" "$local_sha"; then
  echo "worktree-base-check: ${branch} 與 upstream 分歧（不是單純領先），不能 ff——先處理再派工" >&2
  exit 2
fi

ahead=$(git rev-list --count "${upstream_sha}..${local_sha}")
cat <<EOF
## 第 0 步：確認基底（已預先授權，照做不必回報等指示）

本地 ${branch} 領先 upstream ${ahead} 個 commit，worktree 可能是從 upstream 開的。

1. \`git log -1 --format=%H\` 應為 \`${local_sha}\`
2. 不是的話：\`git merge --ff-only ${local_sha}\`（預先授權）
3. \`git diff --name-only ${upstream_sha:0:7}..HEAD\` 核對帶進來的檔案，共 $(git diff --name-only "${upstream_sha}..${local_sha}" | wc -l | tr -d ' ') 個
4. ff 失敗就停下回報，不要自行 rebase 或 reset
EOF
