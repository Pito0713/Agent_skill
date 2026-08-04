# TODO — 待辦與暫緩項目

> 記錄「已知但決定先不做」與「已知缺陷待修」。做完就刪除該項，不留已完成紀錄（歷史查 git log）。
> 格式：`## 標題` + 狀態 / 背景 / 待辦 / 決策者與日期。

---

## 交接檔並發控制：改 per-session 分檔 + git 化

**狀態**：🟡 **Phase D 已完成**（2026-08-04，ADR-017：git 化，解除漏洞 #3 #4）；
**Phase A–C 暫緩**（使用者決定先留計畫）——解的是並發覆蓋（漏洞 #1 #2 #5），
基率低：單人使用、2 個追蹤中專案、歷史發生 1 次且零損失。
原延後理由「避免與活躍的 WakaWaka session 撞規則」當日實查已消失（該 repo 工作區
clean、最後 commit 在 17 小時前）——現在不做是基率判斷，不是被擋住。

**問題**：`~/.agent-sessions/<專案>/latest.md` 是**單一共享可變檔案**，Claude 與 Codex
並行時靠 `maintenance-protocol §6`「讀 → 比對最後更新 → 合併 → 寫」的自律規約保護。
2026-07-23 20:05–20:08 WakaWaka 真實發生一次並發寫入（該輪交接檔自留「併發註記」，
`hook.log` 有 `20:07:22 BLOCK repo=/Users/wits/WakaWaka`），該次靠時間錯開才沒出事。

五個漏洞：

1. **TOCTOU**：讀與寫之間有時間窗。兩個 agent 都讀到同一舊版、各自合併、先後寫入 →
   後寫者連同對方的合併成果一起覆蓋，而且它「有照規則做」
2. **只有 L1 強制力**：規則寫在 markdown 給模型讀，忘了執行就是靜默整檔覆蓋，無機制阻擋
3. ~~**覆蓋即永久丟失**~~ → **已解除**（2026-08-04 Phase D：`~/.agent-sessions` 已 git 化）
4. ~~**無寫入者身分**~~ → **已解除**（2026-08-04 Phase D：標頭加 `> 寫入者：` 必填欄）
5. **「開工時間」對模型是主觀的**：沒有客觀時戳，實務上憑印象判斷「這比我記得的新」

**方案**：消除共享可變狀態，而非加鎖。每輪收工只**建一個新檔案**，檔名含時戳與
harness，寫入端天然不碰撞。

```
~/.agent-sessions/<專案>/
├── latest.md                          # 聚合產物，不手改
└── entries/
    ├── 20260723-155300-claude.md
    └── 20260723-200800-codex.md
```

- 檔名：`<YYYYMMDD>-<HHMMSS>-<harness>.md`（秒級 + harness 名，碰撞機率可忽略）
- `latest.md` = 最新一筆 entry 全文 + 檔尾附歷史 entries 索引（含時間、harness、
  一行焦點）。任何時候重跑聚合都得到一致結果
- entry 標頭增設 `> 寫入者：claude | codex | agy` 欄位（補漏洞 4）
- `~/.agent-sessions` 執行 `git init`，寫入後 auto-commit（補漏洞 3；不解決並發，
  但這是目前最大的實質風險，且成本最低）。`hook.log` 進 `.gitignore`

---

### 2026-08-04 實地重勘：三項事實與原描述不符

動手前重讀了 `handoff` / `project-dashboard` / `maintenance-protocol §6` /
`handoff-verifier` 與 `~/.agent-sessions` 實況，三處要更正：

1. **要遷移的是 2 份不是 7 份**——只剩 `WakaWaka`、`shopee`，其餘隨棄用專案消失
2. **四份索引檔（CLAUDE / AGENTS / GEMINI / CLAUDE.global）不用動**——它們只寫
   「觸發詞 + 開工先讀」，沒寫寫入機制。**因此不必跑 §7 索引防漂移四查**，
   風險面比原估小一圈
3. **延後理由已消失**——WakaWaka 工作區 clean、最後 commit 在 17 小時前

### 原描述的兩個過度宣稱（實作時不得沿用）

- **「沒有失敗模式」不成立**：`latest.md` 聚合產物**仍是共享可變檔**。兩個 agent
  同時 rebuild，後寫者可能產出少一筆的版本。真正的保證是**「entries 不可變 →
  資料永不遺失」**，不是「沒有並發」。最糟情況：latest.md 短暫落後一筆，下次
  rebuild 自愈。ADR 要照這個誠實版本寫，並用 write-temp + 原子 `mv` 收斂窗口
- **auto-commit 必須寫死在 `handoff` skill 內，絕不掛任何 git hook**——掛 hook
  就是第三次重演 post-commit 那個坑（ADR-014/015 禁止的自動寫入路徑）

### 基率評估（決定要不要做的關鍵）

實際風險基數：**單人使用、2 個追蹤中的專案、歷史上並發 1 次且靠時間錯開沒出事**。
下面 Phase A–C 解的是「並發覆蓋」（發生過 1 次、零損失），Phase D 解的是「覆蓋即
永久丟失」（唯一不可逆的那個，且成本最低）。**若要縮減範圍，先做 Phase D。**

### 實作 Phase（2026-08-04 規劃，使用者暫緩實作）

**Phase A — 寫入端**
- [ ] 新增 `bin/rebuild-latest.sh`：掃 `entries/*.md` → 依檔名時戳排序 → 產出
      `latest.md`。寫 temp 再 `mv` 原子換檔，冪等
- [ ] 新增 `bin/test-rebuild-latest.sh`：四象限（零 entry / 單筆 / 多筆排序 /
      重跑冪等 + 壞檔名略過）。陰性案例不可省（lessons 2026-07-31）

**Phase B — 規約端**
- [ ] `skills/productivity/handoff/SKILL.md` Phase 最終：改為「寫新 entry + 跑
      rebuild」，**刪除「重讀 / 比對時間 / 合併」整套規約**，entry 標頭加寫入者欄位
- [ ] `governance/maintenance-protocol.md §6`：改寫並發段落（觸發詞規則一字不動）
- [ ] `agents/06-governance/handoff-verifier.md`：格式查核改對 entry，新增一項
      「latest.md 與 entries/ 是否同步」

**Phase C — 讀取端**
- [ ] `skills/productivity/project-dashboard/SKILL.md`：聚合後 `latest.md` 前段格式
      不變 → 預期只加一行來源註記。**先實跑驗證再決定改不改**

**~~Phase D — git 化~~ 已完成**（2026-08-04，見 ADR-017 與 commit `a51315b`；
細項查 git log，此處不留已完成紀錄）。

> Phase D 原列的「`latest.md` → `entries/` 遷移」**移入 Phase A 相依**：沒有
> `bin/rebuild-latest.sh` 就搬檔，`project-dashboard` 的 `find -name "latest.md"`
> 會當場找不到。原列的 `WakaWaka/bug-menubar-white-flash.md` 該檔已不存在。

**Phase E — 落地（A–C 完成後才需要）**
- [ ] ADR 追加、README 版本條目、commit
- [ ] 驗收另委派冷啟動 subagent 對抗式審查（鐵律 2：驗證不自驗）

**取捨**：讀取多一層聚合；`entries/` 會累積（定期歸檔或只保留最近 N 筆全文）。
換來的是寫入端無衝突——不需要鎖、CAS、時間比對，也不依賴模型記得合併。

**實作前提**：三個 harness 讀同一份 handoff skill 正本，改完即全域生效；動手前確認
沒有其他 harness 的 session 正在跑，否則它會讀到改到一半的規則。

---

## hook 部署狀態改由腳本現算，不再手抄

**狀態**：🟡 待做（2026-08-04 的安裝漂移已修完，這是防復發的那一半）

**背景**：`enforcement-layers.md` 的「已安裝 N 份」是人工抄的快照。2026-08-04 實測
發現它宣稱 6 份、實際 0 份——文件說有防護而實際沒有，比明擺著沒有更危險。當下已
補裝四份並改寫該段為「現跑指令」，但清單本身仍是手抄。

**待辦**：

- [ ] 加 `bin/check-hook-install.sh`（唯讀）：對 `scan-downstream.sh` 的
      `KNOWN_DOWNSTREAMS` 逐一現算 `.git/hooks/pre-commit` 是否存在、md5 是否等於
      wrapper 正本，輸出表格
- [ ] 併進 `bin/scan-downstream.sh` 或維護協議健康檢查，讓「部署物與正本不一致」
      變成查得到而非靠人記得

---

## Codex discovery root 遷往官方路徑

**狀態**：🟡 待評估

**背景**：官方 manual 記載的穩定 roots 是 `$HOME/.agents/skills` 與 repo
`.agents/skills`；本機 Codex v0.145.0 實測亦支援目前使用的 `$CODEX_HOME/skills`
與 repo `.codex/skills`。目前等於依賴相容行為。

**待辦**：
- [ ] 確認官方 roots 在當前版本的實際行為（`~/.agents/skills` 現為 legacy 目錄，
      本流程不讀寫）
- [ ] 遷移時**只需改 `bin/setup-codex.sh` 與 `bin/inject-codex.sh`**，不影響
      Claude / agy——ADR-013 拆分的主要動機之一

---

## Codex / agy 側的常駐強制力不對等

**狀態**：🟡 已知取捨（ADR-013 記載，非缺陷）

**背景**：Claude 的 managed block 用 `@` 常駐載入 `rules/coding-standards.md` 與
`rules/security.md`，模型沒得選；Codex 沒有 `@` 語法且 AGENTS.md 有 32KiB 上限，
agy 同理，只能寫成「開工必讀」的文字要求。安全底線在 Claude 是機制保證、在
Codex/agy 是紀律要求。

**待辦（想讓 Codex 也變硬保證時）**：
- [ ] 評估走 hook（`.codex/hooks.json` 目前不分發）或把安全規範精簡後內嵌進
      AGENTS.md managed block（受 32KiB 上限約束，現況 AGENTS.md 約 5KB）

---

## inject 殘留偵測與下游 stale：FIX-3 已落地，尚有後續

**狀態**：🟡 部分完成（FIX-3 已落地，餘項無時效壓力）

**已完成（2026-07-27，FIX-3）**：`warn_legacy_content_outside_managed_block`（preflight 偵測 block 外死引用、只警告不刪）+ `bin/scan-downstream.sh`（唯讀掃下游 farm dangling）+ `bin/test-fix-3.sh`。

**尚未做**：
- [ ] 改名後**自動重跑下游 farm**仍未實作——目前 skill 改名後，各下游要人工跑 `inject.sh` 才會清 dangling（實例：WakaWaka 停在改名前，靠本次手動修）。可做：`setup` 後選擇性掃已知下游 + 提示重跑。
- [ ] **冗餘但功能正常的舊 body 偵測不到**（保守設計，避免 false-positive）：如 shopee/CLAUDE.md 仍有 6 條 `@` 當代格式常駐（能 resolve、但新設計已改由 on-demand），FIX-3 不會警告。要清得人工判斷。
- [ ] **加 deprecated-mount 掃描**（ADR-015 遺留）：列出下游指向已刪除 / 已停用 hook
      的掛載。動機是 ADR-014 的殘留掛載活了 4 天沒人發現——`inject.sh` 只有「安裝」
      沒有「移除」，**不安裝 ≠ 移除既有的**。不做通用反注入（會動下游未知設定，風險
      不對稱），沿用 FIX-3「只警告不刪」。
- [ ] 可選：加 opt-in `inject.sh --clean-legacy`，**只在 body 逐字比對到已知舊自動生成模板時**才移除，其餘一律保留——唯一能安全自動化清 body 的路徑。

**已知硬邊界（見 lessons 2026-07-27）**：farm 安裝寫 `.codex/`，Codex exec sandbox 擋、不能當此類 executor。
