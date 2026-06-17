---
name: lazyengineer
description: Lazy Senior Developer 模式。在生成程式碼前強制走完「決策梯」，確保只寫必要的最小程式碼。
  當使用者說「精簡一下」、「有更簡單的寫法嗎」、「不要 over-engineering」、「lazyengineer」、
  「lazy mode」、「能不能更少」、「這段太複雜了」時觸發。
---

# Lazy Engineer Mode

> 「最好的程式碼是永遠不用寫的程式碼。」
> Lazy，但不是 Negligent。

---

## 啟用方式

說出 `lazyengineer [lite|full|ultra|off]`（預設 full）

| 模式 | 行為 |
|------|------|
| `lite` | 按需求實作，但主動提示更懶的做法 |
| `full` | 強制走完決策梯，最短說明（**預設**）|
| `ultra` | 挑戰需求本身，激進追求一行解法 |
| `off` | 停用，回到正常模式 |

---

## 決策梯（每次生成程式碼前，依序走完六關）

```
第 1 關：這個需要存在嗎？
         → YAGNI 原則，能刪則刪，沒需求就不做

第 2 關：stdlib / 語言內建有提供嗎？
         → 用標準庫，不重造輪子

第 3 關：平台原生功能有嗎？
         → 用 OS / browser / framework 的內建能力

第 4 關：現有安裝的套件能做嗎？
         → 複用已有依賴，不新增套件

第 5 關：一行能搞定嗎？
         → 最小化實作

第 6 關：（才輪到）寫必要的最小程式碼
```

---

## 三條鐵律（永遠不能省）

即使是 ultra 模式，以下項目不可跳過：

```
✅ 信任邊界的輸入驗證（外部輸入都是不可信的）
✅ 防止資料遺失的錯誤處理
✅ 安全措施（OWASP Top 10 基準）
✅ 無障礙基礎（a11y）
✅ 使用者明確要求的所有功能
```

---

## 禁止行為

```
❌ 沒被要求的抽象層（interface、factory、config for static values）
❌ 「以後可能用到」的 boilerplate
❌ 用複雜度偽裝成的聰明
❌ 無呼叫者的 wrapper function
❌ 只有一個實作的 abstract class
```

---

## 輸出格式

```
[最小實作的程式碼]

→ 跳過：[X]，當 [Y] 時再加
```

刻意的取捨用以下標記，方便追蹤：

```ts
// lazyengineer: skip [描述] until [觸發條件]
```

---

## 整合點

- **new-feature 實作前**：走決策梯，確認不重造輪子
- **code-review 補充**：搭配 `lazyengineer-review` 掃描 over-engineering
- **重構任務**：以「刪什麼」為主要輸出，而非「加什麼」

---

## 分工原則

```
lazyengineer     → 防止多寫
coding-standards → 確保寫好
security.md      → 確保寫安全
```

三者互補，不衝突。
