---
name: lazyengineer-review
description: |
  Over-Engineering 偵測審查，補充一般 code-review，專門找「可以刪什麼」：
  1. 用五種 tag（delete / stdlib / native / yagni / shrink）標記過度設計
  2. 只審查可刪減項目，不審查 correctness 或安全問題（那是 code-review 的工作）
  3. 輸出 net: -N lines 的可消除清單

  觸發場景：懷疑程式碼有過度設計、想找可以刪除或簡化的部分，或搭配 code-review 一起跑。
  示例觸發：「掃一下這段有沒有過度設計」「這段程式碼有什麼可以刪的」「lazyengineer review 一下這個 PR」
metadata:
  trigger: 懷疑過度設計 / 找可刪程式碼時觸發
  version: "1.0"
  last_updated: "2026-06-17"
---

# Lazy Engineer Review — Over-Engineering 偵測

> 這個 review 只問一件事：**這段程式碼裡有什麼是不需要存在的？**

---

## 觸發方式

搭配 code-review 使用，或獨立執行：

```
使用者說：「lazyengineer review」、「有沒有 over-engineering」、「可以刪什麼」
```

---

## 審查範圍

**只看過度設計，不看以下項目**（那是 `code-review.md` 的工作）：

```
❌ Correctness bugs
❌ 安全漏洞
❌ 效能問題
❌ 測試覆蓋率
```

---

## 五種 Tag 與意義

| Tag | 意義 | 輸出方向 |
|-----|------|---------|
| `delete:` | 死程式碼 / 從未被呼叫的功能 | 直接刪 |
| `stdlib:` | 自己手寫了標準庫已提供的東西 | 換用 stdlib |
| `native:` | 依賴 / 自訂程式碼重複了平台原生功能 | 換用平台能力 |
| `yagni:` | 只有一個實作的抽象 / 只有一個呼叫者的 wrapper | 拍平或刪除 |
| `shrink:` | 相同邏輯可以更少行達成 | 重寫更短 |

---

## 每筆發現格式

```
L行號: [tag] 描述。替換方案。
```

**範例：**

```
L12: stdlib: 手寫 email regex。改用 validator.js 或 URL 內建 API。
L34: yagni: UserRepository 只有一個實作 UserRepositoryImpl。直接用 class，刪 interface。
L67: delete: formatCurrency() 定義但從未被呼叫。
L89: shrink: 5 行的 null check 可用 optional chaining 一行搞定。
L102: native: 手寫 debounce。改用 lodash.debounce（已安裝）。
```

---

## 不標記的項目

```
✅ smoke test / 基本 assertion → 不算 bloat
✅ 明確被使用者要求的功能 → 不標記
✅ 安全相關驗證 → 不標記
✅ 有明確 TODO / lazyengineer: skip 標記的取捨 → 不標記
```

---

## 最終輸出格式

```
## Lazy Engineer Review

審查範圍：[git diff / 檔案名稱]

### 可消除的過度設計

L行號: [tag] 描述。替換方案。
...

### 本次不標記項目
- [說明為什麼某些看似複雜的地方是合理的]

---
net: -N lines possible
```

---

## 與 code-review.md 的分工

| 審查面向 | 負責 skill |
|---------|-----------|
| 邏輯 / 可讀性 | `code-review.md` Phase 1 |
| 安全漏洞 | `code-review.md` Phase 2 |
| 測試覆蓋 | `code-review.md` Phase 3 |
| **過度設計 / 可刪什麼** | **本 skill** |

兩者搭配使用時，先跑 `code-review`，再跑 `lazyengineer-review`。
