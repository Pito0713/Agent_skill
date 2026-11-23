#!/usr/bin/env bash
# test-worktree-base-check.sh — bin/worktree-base-check.sh 的測試（工單 W4）。fixture 在 mktemp -d。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/worktree-base-check.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@users.noreply.github.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@users.noreply.github.com
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
check() { [[ "$2" == "$3" ]] && pass "$1" || fail "${1}（實際：${2}）"; }

WORK="$SANDBOX/work"
git init -q --bare "$SANDBOX/remote.git" && git init -q -b main "$WORK" || exit 2
git -C "$WORK" remote add origin "$SANDBOX/remote.git"
commit() { echo "$RANDOM" >>"$WORK/f"; git -C "$WORK" add f; git -C "$WORK" commit -q -m c; git -C "$WORK" rev-parse HEAD; }
run() { OUT=$(cd "$WORK" && bash "$TOOL" "$@" 2>"$SANDBOX/err"); RC=$?; }

commit >/dev/null
run
check "沒有 upstream → exit 2（要求工單寫明基底）" "$RC:$(grep -c '沒有 upstream' "$SANDBOX/err")" "2:1"

git -C "$WORK" push -q -u origin main 2>/dev/null
run
check "本地 == upstream → 無輸出 exit 0" "$RC:${OUT}" "0:"

ahead_sha=$(commit); commit >/dev/null; ahead_sha=$(git -C "$WORK" rev-parse HEAD)
run
check "本地領先 → exit 0" "$RC" 0
grep -qF "git merge --ff-only ${ahead_sha}" <<<"$OUT" && pass "第 0 步含本地 sha 與 ff-only" || fail "第 0 步含本地 sha 與 ff-only"
grep -qF "領先 upstream 2 個 commit" <<<"$OUT" && pass "寫明領先幾個 commit" || fail "寫明領先幾個 commit"

git -C "$WORK" push -q origin main 2>/dev/null
git -C "$WORK" reset -q --hard HEAD~1
commit >/dev/null
git -C "$WORK" fetch -q origin
run
check "與 upstream 分歧 → exit 2 不給第 0 步" "$RC:${OUT}" "2:"

git -C "$WORK" checkout -q --detach
run
check "detached HEAD → exit 2" "$RC" 2

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
