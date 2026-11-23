#!/usr/bin/env bash
# detect-stack.sh — coding-workflow-core Phase 0 的 shell fallback（計劃書 plans/t6-bash-extraction.md C5）
#
# 用法：detect-stack.sh [專案目錄]（預設目前目錄）
# 輸出：每行一個應載入的 rules 檔（~/Agent_skill/rules/<名稱>.md），依 Phase 0 表的順序；沒有命中 → 無輸出
#
# 只在 harness 原生唯讀工具（Glob / Grep）不可用時才用——Phase 0 的「原生工具優先」規則不變。
# 不判斷 rules/git.md：它取決於「任務是否涉及 commit / PR」，只有模型知道。
# 對照表的正本是 SKILL.md 的 Phase 0 表；test-detect-stack.sh 會比對兩邊，避免漂移。

set -u

project_dir="${1:-.}"
[[ -d "$project_dir" ]] || { echo "detect-stack: 找不到目錄 ${project_dir}" >&2; exit 2; }

# 掃三層、略過依賴與版控目錄：避免 node_modules 裡的 *.ts / *.test.* 造成誤判
has_file() {
  [[ -n "$(find "$project_dir" -maxdepth 3 \( -name node_modules -o -name .git -o -name .venv -o -name venv \) -prune \
    -o -type f \( "$@" \) -print 2>/dev/null | head -n 1)" ]]
}
# 看兩層內所有 package.json（monorepo 的 frontend/package.json 才有 react）；只認 "react": 這種鍵，不認描述文字
package_has() {
  find "$project_dir" -maxdepth 2 -name node_modules -prune -o -name package.json -type f -print 2>/dev/null \
    | while IFS= read -r file; do grep -qE "\"($1)\"[[:space:]]*:" "$file" && echo hit && break; done | grep -q hit
}

emit() { echo "~/Agent_skill/rules/$1.md"; }

has_file -name tsconfig.json -o -name '*.ts' -o -name '*.tsx' && emit typescript
package_has react && emit react
has_file -name 'next.config.*' && emit nextjs
has_file -name requirements.txt -o -name pyproject.toml -o -name '*.py' && emit python
has_file -name '*.test.*' -o -name '*.spec.*' -o -name 'jest.config.*' -o -name pytest.ini && emit testing
package_has 'react|vue|next' && emit frontend-security
exit 0
