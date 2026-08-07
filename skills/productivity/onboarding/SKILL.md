---
name: onboarding
description: |
  新專案接手協調器，系統性了解架構、依賴、核心邏輯。 觸發：接手新專案、幫我了解這個 repo、我剛加入這個專案、幫我看這個 codebase（只是恢復上次工作狀態走 smart-init）
metadata:
  trigger: 剛加入新專案需系統性了解架構與技術堆疊時觸發
  version: "1.0"
  last_updated: "2026-07-04"
---

# Onboarding — Orchestrator

## 觸發後第一步：確認接手情境

詢問使用者（若未說明）：
> 1. 你的角色？（新加入成員 / 接手維護 / 短期協作）
> 2. 有沒有現有文件？（README / Wiki / 設計文件）
> 3. 最需要先了解的部分？（整體架構 / 特定功能 / 資料庫設計）

確認後進入 Phase 0。

---

## Phase 0：Session 初始化 + 基本環境掃描

首先觸發 `skills/productivity/smart-init/SKILL.md` 讀取現有記憶與工作狀態，
確認是否有前一次 session 留下的專案摘要可供參考。

```bash
# 專案基本資訊
ls README.md CHANGELOG.md package.json pyproject.toml go.mod 2>/dev/null
git log --oneline -10          # 近期變更
git branch -a                  # 分支結構
wc -l $(find . -name "*.ts" -o -name "*.py" -o -name "*.go" 2>/dev/null) | tail -1  # 程式碼規模
```

**輸出**：「專案規模：[行數]，近期活躍分支：[清單]」

---

## Phase 1：架構掃描

若專案規模小（< 5000 行）→ Claude 直接讀取

若專案規模大，詢問：
> 「是否啟用 agy 掃描整個 codebase？(y/n)」

**y：**（$CLI_CMD 依 `cli-delegate.md` 前置確認偵測）
```bash
# Bash tool timeout: 570s（agy --print-timeout 9m + 30s 緩衝，模式 B）
find ./src -name "*.ts" -o -name "*.py" -o -name "*.go" | \
  xargs cat | $CLI_CMD --print-timeout 9m -p "
分析這個專案的整體架構，條列以下內容，每項不超過 5 行：
1. 專案用途（一句話）
2. 主要模組與職責（條列）
3. 技術堆疊（框架 / DB / 外部服務）
4. 資料流向（請求從哪進來，怎麼處理，回哪裡）
5. 最複雜 / 最核心的模組是哪個

不要建議修改。繁體中文。"
```

**輸出**：架構摘要 → 進入 Phase 2

---

## Phase 2：技術堆疊偵測

依據 `coding-workflow-core.md` Phase 0 自動偵測：

```bash
ls tsconfig.json next.config.* requirements.txt pyproject.toml 2>/dev/null
grep -s '"react"\|"vue"\|"next"\|"express"\|"fastapi"' package.json 2>/dev/null
```

自動載入對應規則（typescript / react / nextjs / python）

---

## Phase 3：關鍵模組深度閱讀

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 4
> - Phase 1 agy 已輸出詳細摘要，**且**使用者目標為「了解架構概覽」（非立即開發）
> - 專案 README 已有完整模組說明，且已涵蓋當前任務所需細節（使用者確認）
> - 使用者明確說「只需要架構概覽，不需要深入每個模組」
>
> ⚠️ **注意**：若接下來要立即進行開發任務，不建議跳過——agy 摘要可能缺少實作細節

依 Phase 1 找出的核心模組，Claude 逐一讀取：

```
[ ] 入口檔案（index.ts / main.py / app.ts）
[ ] 資料模型 / Schema（types / models / prisma schema）
[ ] 核心業務邏輯（service / domain 層）
[ ] API 路由定義
[ ] 設定檔（config / env）
```

**輸出**：各模組一句話說明 → 確認理解後進入 Phase 4

---

## Phase 4：資訊架構理解

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 5
> - 純後端 API 專案（無前端路由 / 頁面，不需要 IA）
> - 使用者明確說「只需要了解後端架構，不需要 IA 整理」
> - 已有現成的路由文件 / sitemap（使用者確認）

委派 `skills/design/information-architecture/SKILL.md`（閱讀模式）：

```
[ ] 整理功能模組的層級關係
[ ] 釐清頁面 / 路由結構（前端專案）
[ ] 釐清 API endpoint 結構（後端專案）
```

**輸出**：功能地圖 + 路由 / API 清單

---

## Phase 5：輸出專案摘要文件

觸發 `skills/productivity/handoff/SKILL.md`（生成模式）：

產出可供後續 session 使用的摘要：

```
## 專案摘要
專案名稱：[名稱]
用途：[一句話]
技術堆疊：[清單]

### 架構概覽
[模組結構圖]

### 核心模組說明
- [模組]：[職責]

### 路由 / API 清單
[清單]

### 開發注意事項
- [特殊規範 / 坑 / 重要決策]

### 建議下一步
- [ ] 閱讀 [特定檔案]（最複雜的部分）
- [ ] 執行 [指令] 啟動本地環境
- [ ] 詢問 [問題] 確認業務邏輯
```

---

## 分工原則

| 角色 | 負責 Phase |
|------|------|
| Orchestrator（本 skill）| 全流程控制、摘要整合 |
| `smart-init` | Phase 0 讀取既有記憶與工作狀態 |
| `cli-delegate` 模式 B | Phase 1 大型 codebase 掃描 |
| `coding-workflow-core` Phase 0 | Phase 2 技術堆疊自動偵測 |
| `information-architecture` | Phase 4 功能地圖與路由整理 |
| `handoff` | Phase 5 輸出結構化摘要文件 |
