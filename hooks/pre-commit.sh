#!/usr/bin/env bash
# hooks/pre-commit.sh
# Claude Code pre-commit hook：commit 前自動執行品質檢查
# 安裝方式：cp hooks/pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -euo pipefail

# 顏色輸出
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "🔍 Running pre-commit checks..."
FAILED=0

# ─────────────────────────────────────────
# 1. 偵測專案類型
# ─────────────────────────────────────────
IS_NODE=false
IS_PYTHON=false

[[ -f "package.json" ]] && IS_NODE=true
[[ -f "pyproject.toml" || -f "requirements.txt" ]] && IS_PYTHON=true

# ─────────────────────────────────────────
# 2. 取得暫存的檔案清單
# ─────────────────────────────────────────
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)
STAGED_TS=$(echo "$STAGED_FILES" | grep -E '\.(ts|tsx)$' || true)
STAGED_JS=$(echo "$STAGED_FILES" | grep -E '\.(js|jsx)$' || true)
STAGED_PY=$(echo "$STAGED_FILES" | grep -E '\.py$' || true)

# ─────────────────────────────────────────
# 3. Secret 掃描（所有語言）
# ─────────────────────────────────────────
echo "  🔑 Checking for secrets..."

SECRET_PATTERNS=(
  "AKIA[0-9A-Z]{16}"                    # AWS Access Key
  "sk-[a-zA-Z0-9]{32,}"                 # OpenAI / Anthropic key
  "ghp_[a-zA-Z0-9]{36}"                 # GitHub token
  "password\s*=\s*['\"][^'\"]{6,}"      # Hardcoded password
  "secret\s*=\s*['\"][^'\"]{8,}"        # Hardcoded secret
  "private_key\s*=\s*['\"]"             # Private key
)

for pattern in "${SECRET_PATTERNS[@]}"; do
  if echo "$STAGED_FILES" | xargs -I{} git show ":{}" 2>/dev/null | grep -qE "$pattern" 2>/dev/null; then
    echo -e "  ${RED}✗ Potential secret detected matching: $pattern${NC}"
    FAILED=1
  fi
done

# 更可靠：如果有安裝 detect-secrets
if command -v detect-secrets &>/dev/null; then
  if ! detect-secrets scan --baseline .secrets.baseline 2>/dev/null; then
    echo -e "  ${RED}✗ detect-secrets found potential secrets${NC}"
    FAILED=1
  fi
fi

# ─────────────────────────────────────────
# 4. Node.js / TypeScript 檢查
# ─────────────────────────────────────────
if [[ "$IS_NODE" == true && -n "$STAGED_TS$STAGED_JS" ]]; then

  # ESLint
  if command -v eslint &>/dev/null || [[ -f "node_modules/.bin/eslint" ]]; then
    echo "  📋 Running ESLint..."
    if ! npx eslint $STAGED_TS $STAGED_JS --max-warnings=0 2>&1; then
      echo -e "  ${RED}✗ ESLint failed${NC}"
      FAILED=1
    else
      echo -e "  ${GREEN}✓ ESLint passed${NC}"
    fi
  fi

  # TypeScript type check（只跑一次，不限暫存檔案）
  if [[ -f "tsconfig.json" ]]; then
    echo "  🔷 Running TypeScript check..."
    if ! npx tsc --noEmit 2>&1; then
      echo -e "  ${RED}✗ TypeScript errors found${NC}"
      FAILED=1
    else
      echo -e "  ${GREEN}✓ TypeScript check passed${NC}"
    fi
  fi

  # console.log 檢查
  echo "  🔍 Checking for console.log..."
  CONSOLE_LOGS=$(echo "$STAGED_TS$STAGED_JS" | xargs grep -l "console\.log" 2>/dev/null || true)
  if [[ -n "$CONSOLE_LOGS" ]]; then
    echo -e "  ${YELLOW}⚠ console.log found in:${NC}"
    echo "$CONSOLE_LOGS" | sed 's/^/    /'
    # 警告但不阻擋（允許開發時使用）
  fi

fi

# ─────────────────────────────────────────
# 5. Python 檢查
# ─────────────────────────────────────────
if [[ "$IS_PYTHON" == true && -n "$STAGED_PY" ]]; then

  # Ruff lint
  if command -v ruff &>/dev/null; then
    echo "  📋 Running ruff..."
    if ! ruff check $STAGED_PY 2>&1; then
      echo -e "  ${RED}✗ Ruff lint failed${NC}"
      FAILED=1
    else
      echo -e "  ${GREEN}✓ Ruff passed${NC}"
    fi
  fi

  # Ruff format check
  if command -v ruff &>/dev/null; then
    if ! ruff format --check $STAGED_PY 2>&1; then
      echo -e "  ${RED}✗ Ruff format check failed (run: ruff format)${NC}"
      FAILED=1
    fi
  fi

  # print() 檢查
  PRINT_STMTS=$(echo "$STAGED_PY" | xargs grep -l "^print(" 2>/dev/null || true)
  if [[ -n "$PRINT_STMTS" ]]; then
    echo -e "  ${YELLOW}⚠ print() found in:${NC}"
    echo "$PRINT_STMTS" | sed 's/^/    /'
  fi

fi

# ─────────────────────────────────────────
# 6. 結果
# ─────────────────────────────────────────
echo ""
if [[ $FAILED -eq 1 ]]; then
  echo -e "${RED}❌ Pre-commit checks failed. Fix the issues above before committing.${NC}"
  echo -e "${YELLOW}   Bypass (not recommended): git commit --no-verify${NC}"
  exit 1
else
  echo -e "${GREEN}✅ All pre-commit checks passed.${NC}"
  exit 0
fi
