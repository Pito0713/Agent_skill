# Project Context

> 專案架構、技術選型、重要決策的完整記錄。  
> 這是「為什麼這樣設計」的真相文件。

---

## 架構概覽

```
（填入系統架構圖或文字描述）

例：
Frontend (Next.js) → API Layer (Next.js API Routes / FastAPI)
                          ↓
                   Service Layer（業務邏輯）
                          ↓
                   Repository Layer（資料存取）
                          ↓
                   PostgreSQL + Redis Cache
```

---

## 技術選型記錄

### 前端框架

**選擇**：（填入）  
**考慮過**：（填入其他選項）  
**選擇原因**：（填入）  
**日期**：（填入）

---

### 資料庫

**選擇**：（填入）  
**考慮過**：（填入）  
**選擇原因**：（填入）  
**日期**：（填入）

---

### 認證方案

**選擇**：（填入）  
**考慮過**：（填入）  
**選擇原因**：（填入）  
**日期**：（填入）

---

## 重要架構決策（ADRs）

### ADR-001：採用 Orchestrator Skill 模式

**狀態**：已接受  
**日期**：2026-06-15

**背景**：原本的 skills 各自獨立，使用者需要手動決定呼叫哪個 skill，流程零散。

**決策**：建立 6 個 Orchestrator（code-review / new-feature / debug-flow / deploy-prep / ui-design-flow / onboarding），各自作為單一入口，協調多個子 skill / agent 完成端到端流程。

**後果**：
- 正面：使用者只需說出觸發詞，不需了解底層 skill 結構
- 負面/注意：Orchestrator 本身的維護成本較高，Phase 定義需保持一致

---

### ADR-002：Phase 跳過條件（Skip Conditions）

**狀態**：已接受  
**日期**：2026-06-16

**背景**：所有 Orchestrator 在早期版本中無論情境如何都執行全部 Phase，造成不必要的 token 消耗。

**決策**：為 6 個 Orchestrator 的可選 Phase 各加入 `⏭ 跳過條件`（共 17 條）與 `🚫 CRITICAL GATE`（5 個）。agy 交叉驗證確認設計合理性。

**後果**：
- 正面：預估節省 15–20% token，CRITICAL GATE 強制安全問題不被跳過
- 負面/注意：條件判斷依賴使用者輸入的明確程度

---

### ADR-003：引入 Lazy Engineer 模式

**狀態**：已接受  
**日期**：2026-06-17

**背景**：分析 Ponytail 專案後，發現其「決策梯」概念可以在生成程式碼前有效減少 over-engineering。實測顯示 65–90% output token 節省。

**決策**：以 Ponytail 概念為基礎，設計 `lazyengineer.md`（核心模式）與 `lazyengineer-review.md`（over-engineering 掃描），命名改為 lazyengineer 以貼近本專案語境。整合進 code-review Orchestrator 的 Phase 1.5。

**後果**：
- 正面：大幅降低 output token；輸出更可預期（不偷寫檔案、不自行跑測試）；取捨透明化（`lazyengineer: skip until` 標記）
- 負面/注意：AI 對「需求邊界」的判斷可能與開發者不一致；不適合上線功能或需要完整規格的場景

---

## 已知設計限制

> 知道不完美但有意為之的設計，避免新人重複質疑

| 限制 | 原因 | 預計改善時間 |
|------|------|------------|
| （填入） | （填入） | （填入） |

---

## 禁止改動的部分

> 有特殊原因不能動的程式碼或設定

- （填入）：原因 = （填入）

---

## 外部依賴

| 服務 | 用途 | 文件 |
|------|------|------|
| （填入） | （填入） | （填入） |

---

## 環境設定

### 必要環境變數

| 變數名 | 用途 | 取得方式 |
|--------|------|----------|
| `DATABASE_URL` | PostgreSQL 連線 | （填入） |
| `NEXTAUTH_SECRET` | Auth 加密 | `openssl rand -base64 32` |
| （填入） | （填入） | （填入） |

### 本地開發設定

```bash
# 初始化步驟（新成員照這個跑）
（填入）
```

---

## 版本歷史

| 版本 | 日期 | 變更摘要 |
|------|------|----------|
| v0.1 | （日期） | 初始建立 |
