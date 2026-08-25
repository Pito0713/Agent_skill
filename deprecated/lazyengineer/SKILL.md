---
name: lazyengineer
description: |
  Lazy Senior 模式，強制走完六關決策梯，確保只寫必要的最小程式碼。 觸發：精簡一下、有更簡單的寫法嗎、不要 over-engineering、能不能更少、lazyengineer、lazy mode、這段太複雜了
metadata:
  trigger: 要求精簡實作 / 質疑寫法過複雜 / 進入 lazy 模式時觸發
  version: "1.0"
  last_updated: "2026-06-22"
---

> 🚫 **已停用（2026-08-25）**
>
> 本檔已移出 `skills/`，**不在 `skills/index.json`、不在 `skills/llms.txt`、不會被任何 harness 掃到**，
> agent 不會主動讀取或觸發它。保留在此僅作為文件參考與歷史依據。
>
> **停用理由**：0 使用；與 lazyengineer-review 本質同一把尺，決策梯已內聯進 code-review Phase 1.5
>
> 要復用：把整個目錄搬回 `skills/<分類>/`，在 `index.json` 與 `llms.txt` 補回同一筆路由資料，
> 跑 `python3 bin/gen-skill-frontmatter.py --write` 重生 frontmatter，再跑 `bash setup.sh`。
> 政策與完整清單見 `deprecated/README.md`。

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

---

## ✅ 正確做法 / ❌ 常見錯誤

```
✅ 動手前先問「這個需要存在嗎？」，能不寫就不寫
✅ 先查 stdlib / 框架內建 / 已安裝套件，再考慮自己實作
✅ 刪除 > 重構 > 新增（先考慮能不能刪掉這個需求）
✅ 取捨用 // lazyengineer: skip [描述] until [觸發條件] 標記，方便追蹤

❌ 用「彈性」、「可擴展性」合理化沒有現實需求的抽象層
❌ 「先把架構做好之後再精簡」（這個「之後」永遠不會到來）
❌ 把「看起來聰明的程式碼」（多層 closure、泛型套泛型）等同於「好的程式碼」
❌ 在三條鐵律範圍內（輸入驗證 / 錯誤處理 / 安全）也想省，這樣不叫 lazy，叫 negligent
```
