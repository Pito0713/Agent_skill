---
name: onboarding
description: 接手新專案協調器。當使用者說「幫我了解這個專案」、「我剛加入這個 repo」、
  「幫我看一下這個 codebase」、「這個專案是做什麼的」、「接手專案」時觸發。
  快速掌握專案架構、技術堆疊、關鍵模組，輸出可供後續 session 使用的專案摘要。
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

首先觸發 `skills/productivity/smart-init.md` 讀取現有記憶與工作狀態，
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
> 「是否啟用 Gemini 掃描整個 codebase？(y/n)」

**y：**
```bash
find ./src -name "*.ts" -o -name "*.py" -o -name "*.go" | \
  xargs cat | agy -p "
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

委派 `skills/design/information-architecture.md`（閱讀模式）：

```
[ ] 整理功能模組的層級關係
[ ] 釐清頁面 / 路由結構（前端專案）
[ ] 釐清 API endpoint 結構（後端專案）
```

**輸出**：功能地圖 + 路由 / API 清單

---

## Phase 5：輸出專案摘要文件

觸發 `skills/productivity/handoff.md`（生成模式）：

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
| `gemini-assist` 模式 B | Phase 1 大型 codebase 掃描 |
| `coding-workflow-core` Phase 0 | Phase 2 技術堆疊自動偵測 |
| `information-architecture` | Phase 4 功能地圖與路由整理 |
| `handoff` | Phase 5 輸出結構化摘要文件 |
