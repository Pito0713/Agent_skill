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

# 掃三層、略過依賴 / 產物 / 版控目錄：避免 node_modules、dist/*.d.ts、vendor 裡的檔案造成誤判
# 範圍比 Phase 0 表的「根目錄」寬是刻意的：多載一份 rules 的成本遠小於 monorepo 漏載安全規範
SKIP_DIRS=(-name node_modules -o -name .git -o -name .venv -o -name venv -o -name dist -o -name vendor \
  -o -name third_party -o -name .pnpm-store -o -name __pycache__)
has_file() {
  [[ -n "$(find "$project_dir" -maxdepth 3 \( "${SKIP_DIRS[@]}" \) -prune \
    -o -type f \( "$@" \) -print 2>/dev/null | head -n 1)" ]]
}
# 看三層內所有 package.json（monorepo 的 frontend/、apps/web/ 才有 react；深度與 has_file 一致，
# 否則同一個 app 會偵測到 next.config 卻漏 react）。認的是 "react": 這種鍵——任何位置的同名鍵都算，與原生 Grep 路徑同樣寬
package_has() {
  find "$project_dir" -maxdepth 3 \( "${SKIP_DIRS[@]}" \) -prune -o -name package.json -type f -print 2>/dev/null \
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
