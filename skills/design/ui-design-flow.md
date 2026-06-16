---
name: ui-design-flow
description: UI 設計規劃協調器。當使用者說「幫我規劃這個頁面」、「設計這個功能的 UI」、
  「這個畫面要怎麼做」、「幫我想 UI 架構」、「設計頁面流程」時觸發。
  從資訊架構 → 版面骨架 → 視覺風格 → 實作交接，完整走完設計流程。
---

# UI Design Flow — Orchestrator

## 觸發後第一步：釐清設計範圍

詢問使用者（若未說明）：
> 1. 這是什麼類型的頁面 / 功能？（表單 / 列表 / 儀表板 / 流程）
> 2. 目標使用者是誰？（一般用戶 / 管理者 / 開發者）
> 3. 有沒有現有的設計風格或品牌規範？
> 4. 最終要產出什麼？（wireframe / 視覺規格 / 直接實作）

確認後進入 Phase 1。

---

## Phase 1：資訊架構（IA）

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 2
> - 使用者確認「IA 已確定 / 現有路由不異動，直接進 wireframe」
> - 只修改單一 UI component 樣式，不影響導航 / 路由結構
> - 使用者說「只改這個按鈕 / 表單 / 顏色」（純視覺微調）

委派 `skills/design/information-architecture.md`：

```
[ ] 確認這個頁面在整體導航中的位置
[ ] 梳理功能清單，決定主次層級
[ ] 規劃頁面間的跳轉與路由結構
[ ] 若有 API 需求 → 定義對應的資料來源與 endpoint 結構
```

**輸出**：層級結構圖 + 路由清單 → 等待確認後進入 Phase 2

---

## Phase 2：版面骨架（Wireframe）

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 3
> - 使用者提供現有設計稿或 Figma 連結
> - 使用者明確說「跳過 wireframe，直接給視覺規格」
> - 只改視覺樣式（顏色 / 字型 / 間距），版面不異動

委派 `skills/design/wireframing.md`：

```
[ ] 依 IA 輸出規劃每個頁面的區塊配置
[ ] ASCII wireframe 呈現主要頁面（桌面版優先）
[ ] 標注互動元素（按鈕、表單、Modal、導航）
[ ] 標注空狀態 / 載入狀態 / 錯誤狀態
```

**輸出**：ASCII wireframe 草稿 → 等待確認後進入 Phase 3

---

## Phase 3：視覺風格（Visual Design）

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 4
> - 使用者確認「已有設計系統 / Tailwind config」，只輸出對應 class 映射
> - 使用者明確說「只需要 wireframe，不需要視覺規格」
> - 使用者說「先做 layout，視覺後面再定」

委派 `skills/design/ui-visual-design.md`：

```
[ ] 依產品類型與目標用戶推薦視覺風格（8 種預設選一）
[ ] 輸出顏色系統（primary / neutral / semantic）
[ ] 輸出字型規格（font family / size / weight）
[ ] 輸出間距規範（spacing scale）
[ ] Tailwind class 對應輸出（可直接使用）
```

**輸出**：視覺規格表 → 等待確認後進入 Phase 4

---

## Phase 4：實作交接

> ⏭ **跳過本 Phase**：滿足以下任一條件即跳過，直接進入 Phase 5
> - 使用者明確說「只需要設計規格，不需要實作交接」
> - 使用者說「有工程師會自己看 wireframe 實作」
> - 本次目的為探索 / 研究（非實作）

依確認的 wireframe + 視覺規格，交接給前端實作：

```
委派 agents/01-core-development/frontend-engineer.md
```

交接內容包含：
```
[ ] 頁面結構（對應 wireframe）
[ ] Tailwind class 規格（對應視覺風格）
[ ] 元件清單（哪些需要新建 / 複用現有）
[ ] 互動行為說明（hover / active / disabled 狀態）
[ ] API 串接需求（對應 Phase 1 的 endpoint 結構）
```

**若需要 API 設計** → 同步觸發 `agents/01-core-development/api-architect.md`

---

## Phase 5：Gemini 設計驗證（可選）

詢問使用者：「是否啟用 Gemini 驗證設計合理性？(y/n)」

**y：**
```bash
agy -p "
以下是一個 UI 設計規劃，請從使用者體驗角度審查：

[貼入 Phase 1 IA 結構 + Phase 2 wireframe]

請審查：
1. 資訊層級是否清晰，用戶能否快速找到目標
2. 操作流程是否有不必要的步驟
3. 是否有遺漏的狀態（空狀態 / 錯誤 / 載入）
4. 行動裝置適配是否有潛在問題

格式：[嚴重度] 問題描述 → 建議方向
嚴重度：HIGH / MEDIUM / LOW
繁體中文。"
```

---

## 最終輸出

```
## UI 設計規劃報告
頁面 / 功能：[名稱]
目標使用者：[描述]

### 資訊架構
[層級結構 + 路由清單]

### Wireframe
[ASCII 版面草稿]

### 視覺規格
[顏色 / 字型 / 間距 / Tailwind class]

### 實作交接清單
- [ ] 元件清單
- [ ] API endpoint 清單
- [ ] 互動行為說明

Gemini 驗證：[通過 / 發現 N 個 UX 問題已調整]
```

---

## 分工原則

| 角色 | 負責 Phase |
|------|------|
| Orchestrator（本 skill）| 全流程控制、設計決策整合 |
| `information-architecture` | Phase 1 IA 與路由結構 |
| `wireframing` | Phase 2 版面骨架 |
| `ui-visual-design` | Phase 3 視覺規格 |
| `frontend-engineer` | Phase 4 實作交接 |
| `api-architect` | Phase 4 API 設計（若需要）|
| `gemini-assist` 模式 C | Phase 5 UX 合理性驗證 |
