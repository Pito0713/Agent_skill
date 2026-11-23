#!/usr/bin/env bash
# test-pre-push-email-audit.sh — hooks/pre-push-email-audit.sh 的測試。
# 每個案例在 mktemp -d 建 bare remote + 工作 repo，用 git 傳給 pre-push 的 stdin 格式直接呼叫 hook。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../hooks/pre-push-email-audit.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

# hermetic：不吃使用者的全域 / 系統 git 設定與身分
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL

ZERO=0000000000000000000000000000000000000000
NOREPLY="12345+someone@users.noreply.github.com"
PERSONAL="someone@example.com"

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }

# new_repo <名稱>：建 bare remote 與工作 repo，WORK 指向工作 repo
new_repo() {
  local remote="$SANDBOX/$1.git"
  WORK="$SANDBOX/$1"
  git init -q --bare "$remote" && git init -q "$WORK" || { echo "fixture 失敗：init $1" >&2; exit 2; }
  git -C "$WORK" remote add origin "$remote"
  git -C "$WORK" config user.name tester
}

# commit_as <author email> [committer email]：在 WORK 建一個 commit，印出 sha
commit_as() {
  local author="$1" committer="${2:-$1}"
  echo "$RANDOM$RANDOM" >>"$WORK/file.txt"
  git -C "$WORK" add file.txt
  GIT_AUTHOR_EMAIL="$author" GIT_COMMITTER_EMAIL="$committer" \
    git -C "$WORK" commit -q -m "c" || { echo "fixture 失敗：commit" >&2; exit 2; }
  git -C "$WORK" rev-parse HEAD
}

# push_raw：不經 hook 直接推到 remote（模擬既有歷史已公開）
push_raw() { git -C "$WORK" push -q --no-verify origin HEAD:refs/heads/main 2>/dev/null; git -C "$WORK" fetch -q origin; }

# run_hook <local sha> <remote sha> [ref]：結果在 RC / OUT
run_hook() {
  local ref="${3:-refs/heads/main}"
  OUT=$(cd "$WORK" && printf '%s %s %s %s\n' "$ref" "$1" "$ref" "$2" | bash "$HOOK" origin "$SANDBOX/x.git" 2>&1)
  RC=$?
}

expect() {
  local description="$1" expected_rc="$2" pattern="${3:-}"
  if [[ "$RC" != "$expected_rc" ]]; then fail "${description}（exit ${RC}，預期 ${expected_rc}）"; return; fi
  if [[ -n "$pattern" ]] && ! grep -qF -- "$pattern" <<<"$OUT"; then fail "${description}（輸出缺「${pattern}」）"; return; fi
  pass "$description"
}

echo "[既有分支]"
new_repo existing; base=$(commit_as "$NOREPLY"); push_raw
head=$(commit_as "$NOREPLY"); run_hook "$head" "$base"
expect "只有 noreply → 放行" 0
head=$(commit_as "$PERSONAL"); run_hook "$head" "$base"
expect "author 為個人信箱 → 擋下" 1 "author	$PERSONAL"
new_repo committer; base=$(commit_as "$NOREPLY"); push_raw
head=$(commit_as "$NOREPLY" "$PERSONAL"); run_hook "$head" "$base"
expect "只有 committer 是個人信箱 → 也擋" 1 "committer	$PERSONAL"
new_repo anthropic; base=$(commit_as "$NOREPLY"); push_raw
head=$(commit_as "$NOREPLY" "noreply@anthropic.com"); run_hook "$head" "$base"
expect "noreply@anthropic.com → 放行" 0

echo "[允許清單比對嚴格]"
new_repo strict; base=$(commit_as "$NOREPLY"); push_raw
head=$(commit_as "x@users.noreply.github.com.evil.com"); run_hook "$head" "$base"
expect "noreply 網域後面再接字 → 擋（錨定結尾）" 1
head=$(commit_as "x@usersXnoreply.github.com"); run_hook "$head" "$base"
expect "點號不是萬用字元 → 擋" 1

echo "[新分支與刪除]"
new_repo newbranch; old=$(commit_as "$PERSONAL"); push_raw
head=$(commit_as "$NOREPLY"); run_hook "$head" "$ZERO" refs/heads/feature
expect "新分支：遠端已有的個人信箱歷史不重查 → 放行" 0
head=$(commit_as "$PERSONAL"); run_hook "$head" "$ZERO" refs/heads/feature
expect "新分支：新 commit 是個人信箱 → 擋" 1
run_hook "$ZERO" "$old" refs/heads/feature
expect "刪除遠端分支 → 放行" 0

echo "[基準點豁免]"
new_repo baseline; first=$(commit_as "$PERSONAL"); old=$(commit_as "$PERSONAL")
git -C "$WORK" config audit.pushEmailBaseline "$old"
head=$(commit_as "$NOREPLY"); run_hook "$head" "$ZERO"
expect "基準點（含）之前的個人信箱不查 → 放行" 0
head=$(commit_as "$PERSONAL"); run_hook "$head" "$ZERO"
expect "基準點之後的個人信箱 → 擋" 1 "author	$PERSONAL"
git -C "$WORK" config audit.pushEmailBaseline deadbeef
run_hook "$head" "$ZERO"
expect "基準點找不到 → 警告且不豁免" 1 "找不到這個 commit"
git -C "$WORK" config audit.pushEmailBaseline HEAD
run_hook "$head" "$ZERO"
expect "基準點設成會移動的 ref（HEAD）→ 不接受、不豁免" 1 "不是 commit sha"

echo "[審查補案例：合作者、tag、大小寫、replace、URL、fail-open]"
new_repo colleague; base=$(commit_as "$NOREPLY"); push_raw
git -C "$WORK" push -q --no-verify origin HEAD:refs/heads/feature 2>/dev/null
other=$(commit_as "colleague@corp.com"); push_raw      # 合作者的個人信箱 commit 已在 origin/main
git -C "$WORK" checkout -q -b feature "$base"
commit_as "$NOREPLY" >/dev/null
git -C "$WORK" merge -q --no-edit origin/main 2>/dev/null
GIT_COMMITTER_EMAIL="$NOREPLY" git -C "$WORK" commit -q --amend --no-edit --author="t <$NOREPLY>"
run_hook "$(git -C "$WORK" rev-parse HEAD)" "$base" refs/heads/feature
expect "merge 進遠端已有的合作者 commit → 不誤擋" 0
new_repo tagger; base=$(commit_as "$NOREPLY"); push_raw
GIT_COMMITTER_EMAIL="$PERSONAL" git -C "$WORK" tag -a v1 -m t "$base"
run_hook "$(git -C "$WORK" rev-parse v1)" "$ZERO" refs/tags/v1
expect "annotated tag 的 tagger 是個人信箱 → 擋" 1 "tagger	$PERSONAL"
new_repo casing; base=$(commit_as "$NOREPLY"); push_raw
head=$(commit_as "12345+Someone@Users.Noreply.GitHub.com"); run_hook "$head" "$base"
expect "noreply 大小寫不同 → 放行" 0
new_repo replace; base=$(commit_as "$NOREPLY"); push_raw
real=$(commit_as "$PERSONAL")
fake=$(GIT_AUTHOR_EMAIL="$NOREPLY" GIT_COMMITTER_EMAIL="$NOREPLY" git -C "$WORK" commit-tree "$(git -C "$WORK" rev-parse "$real^{tree}")" -p "$base" -m c)
git -C "$WORK" replace "$real" "$fake"
run_hook "$real" "$base"
expect "replace ref 換成 noreply 物件 → 仍看原始物件並擋" 1 "author	$PERSONAL"
new_repo byurl; base=$(commit_as "$NOREPLY"); push_raw
head=$(commit_as "$PERSONAL")
OUT=$(cd "$WORK" && printf 'refs/heads/main %s refs/heads/main %s\n' "$head" "$base" | bash "$HOOK" "$SANDBOX/byurl.git" "$SANDBOX/byurl.git" 2>&1); RC=$?
expect "用 URL 當 remote 直接 push → 照樣檢查" 1 "author	$PERSONAL"
run_hook 1111111111111111111111111111111111111111 "$base"
expect "本機沒有要送出的物件（內部錯誤）→ fail-open 並警告" 0 "git log 失敗"

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
