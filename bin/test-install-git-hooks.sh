#!/usr/bin/env bash
# test-install-git-hooks.sh — bin/install-git-hooks.sh 的測試（含 pre-push 端到端：真的 git push 到 bare remote）。
# HOME 換成 sandbox，裡面的 Agent_skill symlink 指回本 repo，wrapper 才找得到正本。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALLER="$SCRIPT_DIR/install-git-hooks.sh"
SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL
export HOME="$SANDBOX/home"
mkdir -p "$HOME" && ln -s "$REPO_ROOT" "$HOME/Agent_skill"

NOREPLY="12345+someone@users.noreply.github.com"
PERSONAL="someone@example.com"

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
check() { [[ "$2" == "$3" ]] && pass "$1" || fail "${1}（實際：${2}）"; }

# new_project <名稱> [with-commit]：PROJECT 指向工作 repo（附 bare remote）
new_project() {
  PROJECT="$SANDBOX/$1"
  git init -q --bare "$PROJECT.git" && git init -q "$PROJECT" || { echo "fixture 失敗：init $1" >&2; exit 2; }
  git -C "$PROJECT" remote add origin "$PROJECT.git"
  git -C "$PROJECT" config user.name tester
  [[ "${2:-}" == with-commit ]] && commit_as "$PERSONAL" >/dev/null
  return 0
}

commit_as() {
  echo "$RANDOM$RANDOM" >>"$PROJECT/file.txt"
  git -C "$PROJECT" add file.txt
  GIT_AUTHOR_EMAIL="$1" GIT_COMMITTER_EMAIL="$1" git -C "$PROJECT" commit -q --no-verify -m c || exit 2
  git -C "$PROJECT" rev-parse HEAD
}

install() { OUT=$(AGENT_SKILL_PROJECT_DIR="$PROJECT" bash "$INSTALLER" "${1:---all}" 2>&1); RC=$?; }
hook_path() { echo "$PROJECT/.git/hooks/$1"; }

echo "[首次安裝]"
new_project fresh with-commit
history_head=$(git -C "$PROJECT" rev-parse HEAD)
install
check "安裝 exit 0" "$RC" 0
for name in pre-commit pre-push; do
  [[ -x "$(hook_path "$name")" ]] && pass "${name} wrapper 已安裝且可執行" || fail "${name} wrapper 已安裝且可執行"
done
grep -q 'Agent_skill/hooks/pre-push-email-audit.sh' "$(hook_path pre-push)" && pass "pre-push wrapper 指向正本" || fail "pre-push wrapper 指向正本"
grep -qF '$HOME' "$(hook_path pre-push)" && pass "wrapper 保留 \$HOME 到執行時才展開" || fail "wrapper 保留 \$HOME 到執行時才展開"
check "沒有 upstream → 不設基準點" "$(git -C "$PROJECT" config --get audit.pushEmailBaseline || echo unset)" unset
grep -q '沒有 upstream' <<<"$OUT" && pass "沒有 upstream 時明講不設" || fail "沒有 upstream 時明講不設"

echo "[端到端：真的 git push]"
new_project e2e with-commit
history_head=$(git -C "$PROJECT" rev-parse HEAD)
git -C "$PROJECT" push -q --no-verify -u origin HEAD:refs/heads/main 2>/dev/null   # 既有歷史已公開
unpushed_personal=$(commit_as "$PERSONAL")                                        # 安裝當下還沒 push
install
check "基準點 = upstream tip，不是 HEAD" "$(git -C "$PROJECT" config --get audit.pushEmailBaseline)" "$history_head"
grep -q '1 個未 push 的 commit 不在豁免範圍' <<<"$OUT" && pass "安裝時提醒未 push 的 commit" || fail "安裝時提醒未 push 的 commit"
git -C "$PROJECT" push -q origin HEAD:refs/heads/main 2>"$SANDBOX/err"
check "安裝前就存在、未 push 的個人信箱 commit → 不被豁免、push 被擋" "$?" 1
git -C "$PROJECT" reset -q --hard "$history_head"
commit_as "$NOREPLY" >/dev/null
git -C "$PROJECT" push -q origin HEAD:refs/heads/main 2>"$SANDBOX/err"
check "歷史是個人信箱、新 commit 是 noreply → push 成功" "$?" 0
commit_as "$PERSONAL" >/dev/null
git -C "$PROJECT" push -q origin HEAD:refs/heads/main 2>"$SANDBOX/err"
check "新 commit 是個人信箱 → push 被擋" "$?:$(grep -c '個人信箱' "$SANDBOX/err")" "1:1"

echo "[重裝與保守原則]"
git -C "$PROJECT" config audit.pushEmailBaseline "$history_head"
commit_as "$NOREPLY" >/dev/null
install
check "重裝不改動既有基準點" "$(git -C "$PROJECT" config --get audit.pushEmailBaseline)" "$history_head"
new_project foreign with-commit
printf '#!/bin/sh\necho mine\n' >"$(hook_path pre-push)"
install
check "既有非本專案 pre-push hook 不被覆蓋" "$(cat "$(hook_path pre-push)")" "#!/bin/sh
echo mine"
grep -q '已存在非本專案安裝的 pre-push hook' <<<"$OUT" && pass "preflight 警告既有 hook" || fail "preflight 警告既有 hook"
printf '#!/bin/sh\necho mine\n"$HOME/Agent_skill/hooks/pre-push-email-audit.sh" "$@" || exit 1\n' >"$(hook_path pre-push)"
custom=$(cat "$(hook_path pre-push)")
install
check "使用者照建議加進正本那行（含 marker）→ 仍不覆蓋" "$(cat "$(hook_path pre-push)")" "$custom"
[[ -x "$(hook_path pre-commit)" ]] && pass "pre-commit 照常安裝" || fail "pre-commit 照常安裝"

echo "[linked worktree]"
new_project wt with-commit
git -C "$PROJECT" worktree add -q "$SANDBOX/wt-linked" -b side 2>/dev/null
OUT=$(AGENT_SKILL_PROJECT_DIR="$SANDBOX/wt-linked" bash "$INSTALLER" 2>&1); RC=$?
common_hooks="$(git -C "$PROJECT" rev-parse --path-format=absolute --git-common-dir)/hooks"
[[ -x "$common_hooks/pre-push" ]] && pass "worktree 安裝到共用 hooks 目錄" || fail "worktree 安裝到共用 hooks 目錄（${OUT}）"
# 舊版 bug 會把絕對路徑接在 worktree 後面，在底下建出 var/… 或 private/… 目錄
[[ ! -e "$SANDBOX/wt-linked/var" && ! -e "$SANDBOX/wt-linked/private" ]] \
  && pass "worktree 下沒有憑空建出目錄" || fail "worktree 下沒有憑空建出目錄"

echo "[略過情境]"
new_project hookspath with-commit
git -C "$PROJECT" config core.hooksPath custom-hooks
install
[[ ! -e "$(hook_path pre-push)" ]] && pass "core.hooksPath 已設 → 不安裝" || fail "core.hooksPath 已設 → 不安裝"
new_project empty
install
check "空 repo（沒有 HEAD）安裝 exit 0" "$RC" 0
check "空 repo 不設基準點" "$(git -C "$PROJECT" config --get audit.pushEmailBaseline || echo unset)" unset

echo ""
echo "結果：${PASS_COUNT} passed, ${FAIL_COUNT} failed"
[[ "$FAIL_COUNT" -eq 0 ]]
