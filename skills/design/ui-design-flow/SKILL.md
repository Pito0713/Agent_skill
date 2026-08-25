---
name: ui-design-flow
description: |
  UI 設計協調器，三模式：A 資訊架構、B 版面骨架 wireframe、C 視覺規格（顏色字型間距）。單一模式可獨立跑，三段串起來即完整頁面設計流程。 觸發：規劃 UI、設計這個頁面、UI 架構、幫我規劃導航、這些功能怎麼分類、資訊架構、IA、API 路由結構、頁面結構、wireframe、視覺風格、UI 風格建議
metadata:
  trigger: 規劃頁面／功能 UI；也涵蓋單獨要 IA、wireframe 或視覺規格的情況
  version: "2.0"
  last_updated: "2026-08-25"
---

# UI Design Flow（UI 設計協調器）

> 三個模式共用同一份查表 `references/design-patterns.md`。
> **模式可單獨跑，不必每次走完三段**——這是本 skill 最常被誤用的地方。

---

## 模式判斷（第一步，不要跳過）

| 使用者說的 | 走哪個模式 |
|-----------|-----------|
| 幫我規劃導航、這些功能怎麼分類、資訊架構、IA、API 路由結構 | **A 資訊架構** |
| 這個畫面要放什麼、幫我規劃頁面結構、wireframe | **B 版面骨架** |
| 幫我決定視覺風格、要用什麼顏色字型、UI 風格建議 | **C 視覺規格** |
| 規劃 UI、設計這個頁面、設計這個功能的 UI（範圍不明） | **完整流程 A→B→C→交接** |

判不出來就問，不要猜（CLAUDE.md 鐵律 3）。

**走完整流程前先問這四題**（單一模式只問跟該模式有關的）：

> 1. 這是什麼類型的頁面 / 功能？（表單 / 列表 / 儀表板 / 流程）
> 2. 目標使用者是誰？（一般用戶 / 管理者 / 開發者）
> 3. 有沒有現有的設計風格或品牌規範？
> 4. 最終要產出什麼？（wireframe / 視覺規格 / 直接實作）

---

## 模式 A：資訊架構

查 `references/design-patterns.md` §A。

```
[ ] 內容盤點：列出所有功能 / 頁面 / 資源，標出高頻項
[ ] 選架構模式（§A1 四選一）
[ ] 定義層級（§A2，最多 3-4 層）
[ ] 命名（§A3：使用者語言、動詞開頭、不歧義）
[ ] 驗收（§A4：3 次點擊可達？初次使用者看得懂？）
```

**輸出**：樹狀結構圖 + 路由清單（格式見 §A5）。有 API 需求時一併定出 endpoint 結構。

> ⏭ 完整流程中可跳過本模式：IA 已確定 / 現有路由不異動 / 只改單一 component 樣式 / 純視覺微調。

---

## 模式 B：版面骨架

查 `references/design-patterns.md` §B。

```
[ ] 定義這個畫面的主要用途與使用者要完成的任務
[ ] 列舉必要內容區塊，分主要 / 輔助
[ ] 選版面模式（§B1 五選一）
[ ] 標註互動元素（按鈕、表單、Modal、導航）
[ ] 標註 loading / empty / error 三狀態（§B2，缺一不可）
[ ] 驗收（§B3）
```

**輸出**：ASCII wireframe（格式見 §B4），桌面版優先。

> ⏭ 完整流程中可跳過本模式：已有設計稿或 Figma 連結 / 使用者明說跳過 / 只改視覺樣式不動版面。

---

## 模式 C：視覺規格

查 `references/design-patterns.md` §C。

```
[ ] 解析產品類型、目標用戶輪廓、品牌關鍵詞
[ ] 匹配風格（§C1：選 1 主 + 最多 2 備選）
[ ] 產出規格（§C2：顏色 / 字型 / 間距 / 圓角）
[ ] 對比度驗證 ≥ 4.5:1（§C3，無障礙硬門檻）
[ ] 需要時輸出對應的 Tailwind class 映射
```

**輸出**：視覺規格表（格式見 §C4）。

> ⏭ 完整流程中可跳過本模式：已有設計系統 / Tailwind config（只輸出 class 映射即可）/ 使用者說視覺後面再定。

---

## 完整流程：實作交接

三個模式跑完後，依確認的 wireframe + 視覺規格交接前端：

```
委派 agents/01-core-development/frontend-engineer.md
```

交接內容：

```
[ ] 頁面結構（對應模式 B 輸出）
[ ] Tailwind class 規格（對應模式 C 輸出）
[ ] 元件清單（哪些新建 / 哪些複用現有）
[ ] 互動行為說明（hover / active / disabled 狀態）
[ ] API 串接需求（對應模式 A 的 endpoint 結構）
```

**若需要 API 設計** → 同步觸發 `agents/01-core-development/api-architect.md`。

> ⏭ 跳過交接：使用者只要設計規格 / 有工程師自行看 wireframe 實作 / 本次目的是探索研究。

---

## 可選：codex 設計驗證

詢問使用者：「是否啟用 codex 驗證設計合理性？(y/n)」

**y：**（codex 依 `cli-delegate.md` 前置確認；codex 不可用時走模式 C 的 Claude Subagent Fallback）

```bash
# Bash tool timeout 建議 570000 ms（cli-delegate 模式 C）
codex exec -s read-only -c project_doc_max_bytes=0 "
以下是一個 UI 設計規劃，請從使用者體驗角度審查：

[貼入模式 A 的 IA 結構 + 模式 B 的 wireframe]

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

## 最終輸出（完整流程用；單一模式只輸出該段）

```
## UI 設計規劃報告
頁面 / 功能：[名稱]
目標使用者：[描述]

### 資訊架構（模式 A）
[層級結構 + 路由清單]

### Wireframe（模式 B）
[ASCII 版面草稿]

### 視覺規格（模式 C）
[顏色 / 字型 / 間距 / Tailwind class]

### 實作交接清單
- [ ] 元件清單
- [ ] API endpoint 清單
- [ ] 互動行為說明

codex 驗證：[通過 / 發現 N 個 UX 問題已調整 / 未啟用]
```

---

## 分工原則

| 角色 | 負責 |
|------|------|
| 本 skill | 模式判斷、三個模式的執行、設計決策整合 |
| `references/design-patterns.md` | 模式選項與規格查表（單一事實來源）|
| `frontend-engineer` | 實作交接 |
| `api-architect` | API 設計（若需要）|
| `cli-delegate` 模式 C | UX 合理性驗證 |
