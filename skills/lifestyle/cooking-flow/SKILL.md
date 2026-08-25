---
name: cooking-flow
description: |
  廚藝協調器，三模式：食譜產生、冰箱反查（食材→菜色）、週餐規劃（菜單→採購清單）。份量換算與加總一律走 script，不心算。 觸發：今天煮什麼、給我食譜、冰箱有什麼可以煮、幫我排一週菜單、採購清單、份量換算、什麼可以代替
metadata:
  trigger: 找食譜／冰箱剩食反查／排一週菜單與採購清單
  version: "1.0"
  last_updated: "2026-08-16"
---

# Cooking Flow（廚藝協調器）

> 三個模式共用同一套知識層與同一組 script。

---

## 職責切分（不可違反）

| 誰做 | 做什麼 |
|------|--------|
| **Script（確定性）** | 份量縮放、單位換算、烤溫／烤模轉換、採購清單加總 |
| **References（引用）** | 食材替代、味型搭配 |
| **LLM（你）** | 挑菜、寫步驟敘述、解釋取捨、判斷缺哪一味 |

**LLM 絕不自行心算任何份量、換算或加總。**
Script 失敗就據實回報失敗；references 沒有的就說沒有，再走網搜補充。

---

## 前置：開場三問（缺一不可，答完才動手）

這三項會整份改寫輸出，缺了等於白做：

1. **過敏原與飲食禁忌**（甲殼類、堅果、乳製品、蛋、麩質；素食／宗教限制）
2. **份數**（幾人份）
3. **可用設備**（爐口數、有無烤箱／氣炸鍋／電鍋／壓力鍋）

使用者已在同一 session 回答過就不重問，直接覆述確認。

---

## 知識來源優先序（每則資訊都標來源）

```
① knowledge/cooking/ vault（你的筆記，最高優先）
      ↓ 沒有
② references/*.md（本 skill 內建）
      ↓ 沒有
③ 委派 codex 網搜 → 標 [web]，明說未經驗證
```

**衝突時 vault 永遠贏**，並主動說明「你的筆記跟一般做法不同，我照你的」。

### ① 讀 vault

```bash
source "$HOME/Agent_skill/.env" 2>/dev/null
grep -rl "<關鍵字>" "$OBSIDIAN_VAULT_PATH/knowledge/cooking" --include="*.md" 2>/dev/null | head -5
```

`OBSIDIAN_VAULT_PATH` 未設定**不是錯誤**，降級只用 references 與網搜即可
（設定方式見 `skills/productivity/knowledge-search/SKILL.md`）。

### ③ 網搜補充

references 與 vault 都沒有、且答案會影響輸出時才查（不是每次都查），
走 `skills/engineering/cli-delegate/SKILL.md` 模式 A。回來的內容一律標 `[web]`，
並說明是外部來源、未經你驗證。

---

## 模式判斷

| 使用者說的 | 走哪個模式 |
|-----------|-----------|
| 想吃 X、給我 X 的食譜、X 怎麼做、幾人份怎麼調 | **A 食譜產生** |
| 冰箱有 A B C、這些能煮什麼、剩菜怎麼辦 | **B 冰箱反查** |
| 排一週菜單、幫我規劃這週、採購清單 | **E 週餐規劃** |
| 只問單一換算（幾克、幾度、幾人份差多少） | 直接跑 script，不跑完整流程 |

判不出來就問，不要猜（CLAUDE.md 鐵律 3）。

---

## 模式 A：食譜產生

1. 開場三問 → 查 vault 有無這道菜的個人版本
2. 定出食材與基準份量，寫成 JSON：

```bash
cd skills/lifestyle/cooking-flow/scripts
python3 scale.py recipe <食譜.json> --servings <人數>
```

食譜 JSON 欄位：`name`、`base_servings`、`ingredients[{item, amount, unit, to_taste?}]`。

- `item` 必填、`unit` 必須是認得的單位，**否則 script 直接報錯退出**（不會靜默補預設值）
- `amount` 只有在 `unit` 是「適量」「少許」時才可以省略；其餘情況缺了就是錯
- `to_taste: true` 的調味料**放大時不等比放大**（3 倍的鹽會鹹到不能吃），
  **縮小時照比例減**（8 人份的鹽留給 1 人份是 8 倍鹹，比放大更難救）

3. 需要單位／烤溫／烤模轉換時：

```bash
python3 scale.py convert 2 cup g --ingredient 麵粉
python3 scale.py temp 350 F
python3 scale.py pan --from 20 --to 23
```

4. 步驟敘述由你寫，但**每一步要給可判斷的完成訊號**（「炒到邊緣透明」而非「炒香」）
5. 照 `references/output-format.md` 模式 A 排版。使用者是**邊做邊看**，所以：
   關鍵控制點不集中成一節，拆進所屬步驟的 `⚠️` 行；`🔺` 只標最容易失敗的那一步；
   選配的變化寫進「＋ 加分調整」，不要混進步驟裡讓人分心

---

## 模式 B：冰箱反查

1. 列出使用者現有食材，**先問想吃哪個味型**（`references/flavor-pairing.md` 的地域表挑 2–3 個）
2. 用「四槽」檢查每個方案：鹹 / 鮮 / 酸甜 / 香。**缺哪一槽就明說缺哪一槽**，這比推薦具名菜色更有用
3. 缺的食材查 `references/substitutions.md`：
   - 有替代 → 給比例，**並說換掉會變什麼**
   - 標 ⚠️ 的（會改變成敗而非只改風味）→ 主動勸阻
   - 表裡沒有 → 說「這張表沒有」再決定要不要網搜
4. 標出**該先用掉**的食材（葉菜、海鮮、絞肉排在根莖與冷凍之前）

---

## 模式 E：週餐規劃

1. 問清楚：幾天、幾人、每天幾道、有無不想重複的菜
2. 排菜單時**刻意讓食材跨菜共用**（一把蔥用三餐，而不是買三把爛兩把）
3. 寫成菜單 JSON（`meals[{name, ingredients[{item, amount, unit}]}]`）後產清單：

```bash
cd skills/lifestyle/cooking-flow/scripts
python3 shopping_list.py <菜單.json>
```

輸出已依採買動線分區、標出每項食材被哪幾道菜用到（抽換菜色時才知道要刪什麼）。
**直接貼 script 輸出，不要自己重打一份**——重打就是引入錯誤的地方。

4. 補上「食材消耗順序」（易壞的排前面）與「這份菜單的取捨」

---

## vault 寫入鉤子（模式 D 的預留接口）

三模式輸出結束後**問一次**，使用者答應才寫。不強迫、不重複問。

```markdown
---
tags: [cooking, <菜名>, <味型>]
created: <YYYY-MM-DD>
servings: <份數>
---

# <菜名>

## 這次的版本
<食材與份量，直接貼 script 輸出>

## 實作記錄
| 日期 | 調整 | 結果 |
|------|------|------|
| <YYYY-MM-DD> | <這次改了什麼> | <太鹹／剛好／火太大> |

## 下次要改
<一次只寫一個最優先的改動點>
```

**「下次要改」一次只寫一項。** 同時改三個變因，下次就不知道是哪一項起了作用——
這是刻意練習的基本紀律：一次只動一個變因，才有可歸因的回饋。

同一道菜第二次以上被問到 → 先讀 vault 的「下次要改」，把它納入這次輸出並主動提起。

---

## 輸出前自我檢查（同時是禁止事項）

```
[ ] 開場三問已答（或本 session 已答過並覆述）——過敏原是安全問題，不是偏好問題
[ ] 數字全部來自 script 輸出，沒有一個是我心算的
[ ] 每則資訊都標了 [vault] / [ref] / [web] / [model]，[web] 與 [model] 已聲明未經驗證
[ ] 未經使用者同意不寫入 vault
```
