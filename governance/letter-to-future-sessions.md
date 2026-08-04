# 給未來 Session 的信（G）

> 首版寫於 2026-07-03；本版改寫於 2026-07-07（三 harness 制度統一那一輪）。
> 你（讀這封信的模型）多半比寫信的模型小。這不是問題——制度的目的就是讓你不需要跟我一樣強。照檔案做，比聰明更重要。
> 你可能在 Claude Code、Codex 或 Antigravity（agy）任何一家讀到這封信：三家共用同一份正本（`~/Agent_skill`），規則對你們一視同仁。

---

## 第一件事：這個 repo 現在是三個 harness 的全域正本，改它的波及面比你以為的大

2026-07-07 起，`setup.sh` 除了 Claude 的 `~/.claude/skills`、`~/.claude/governance`，還把 `~/.codex/AGENTS.md` 與 `~/.gemini/GEMINI.md` symlink 到本 repo 的索引檔。意思是：

- 你改 `AGENTS.md` 一行，**這台機器上所有專案的所有 Codex session 立即生效**；GEMINI.md 對 agy 同理
- 改動前問自己：這是「這個 repo 的事」、「所有專案的事」、還是「三個 harness 的事」？越往後越謹慎，權限分級見 `maintenance-protocol.md`
- 換新機器：先 `bash ~/Agent_skill/setup.sh`，否則 Codex / agy 讀不到任何制度（靜默失效，不會報錯）

## 第二件事：這個環境的真實瓶頸是重工，不是 token 單價

2026-07 的實測結論：最貴的不是模型費用，是卡死一小時沒產出、朝錯方向修一輪、把假 bug 當真 bug 修、scope 越滾越大沒人敢收尾。所以：

- 多花一點 token 在「切工單、驗收、仲裁」上是**划算的**（tech-lead-mode 的存在理由）
- 看到自己在「省 token」而跳過驗證步驟時，你正在犯這個環境已經付過學費的錯

## 第三件事：使用者的工作模式

- 他同時用三個 harness（Claude、Codex、agy）+ 多 session 操作同一批 repo——`git status` 出現非預期變更是**常態**不是異常，處理協議在 judgment-rubrics R3 和 lessons 2026-07-03 條；跨 harness 交接一律走 `~/.agent-sessions/<專案>/latest.md`
- 他吃直球：發現他的邏輯漏洞直接講，他自己在索引檔寫了「不為友善而同意」
- 他要「極短摘要先行」——長輸出放檔案，對話裡給結論

---

## 這套制度最可能的退化方式（與預防法）

| 退化 | 徵兆 | 預防 |
|------|------|------|
| **三份索引漂移**（本制度最大風險）| AGENTS.md / GEMINI.md 的 inline 段被單邊改動；索引檔開始長正文 | 改任一索引必跑 maintenance-protocol §7 四查（可執行指令）；新內容 >10 行進正本 |
| **某 harness 的結論沒回寫正本** | agy / Codex session 做完事，latest.md 還是上週的 | 收工自檢一題「學到的落正本了嗎」（§6）；Codex Memories 保持關閉、agy brain 不作數，逼結論走 latest.md |
| 全域 symlink 被覆蓋成實體檔 | 某 harness 自動更新時把 `~/.codex/AGENTS.md` 寫成一般檔案 | 開工自檢 `ls -l`，發現實體檔 → 停下來問（可能含未回寫的內容，不可直接覆蓋）|
| 型號表過期 | model-orchestration §5 的型號已下架 / 改名 | 事實錯誤屬 🟢 級，查證後當場修，並更新「查證日期」|
| 路由表長回來 | 有人覺得「加一行到索引比較方便」 | maintenance-protocol 🔴 明文禁止；新 skill 只進 llms.txt |
| lessons.md 變垃圾場 | 一次性手滑也被記錄，300 行沒人讀 | 寫入門檻（下次還會有人踩才寫）+ 30 條精簡門檻 |
| 驗證被「趕時間」跳過 | 回報裡出現「應該會過」「邏輯上正確」 | R2 明文：這些字眼 = 進行中，不是完成 |

最根本的退化：**下一個模型覺得自己夠聰明，不需要查表**。制度不是因為你笨，是因為 context 會斷、session 會換、記憶會漂。寫檔案的那個模型也照著檔案做。

---

## 誠實標註：2026-07-07 這輪產出中，信心最低的部分

1. **Codex 整欄純屬文件查證、零本機實測**：型號（gpt-5.5/5.4/5.4-mini）、effort 值、32KiB 上限、subagent 用法全部來自 developers.openai.com，本機 `~/.codex/config.toml` 是 GUI app 骨架、看不出實際用法。第一個 Codex session 開工時，請把 §5 Codex 欄逐項對照實際可選值，錯了照 🟢 級修
2. **agy 的 `TypeName` / `Workspace` 參數**：來自 2026-07-04 某 agy session 的二手回報，至今無人驗證。第一個要委派的 agy session：先看工具 schema，驗完把「未驗證」標註拿掉或改正
3. **agy 解鎖的安全面**：2026-07-07 依使用者決定移除了 `~/.gemini/settings.json` 與 `~/.agents/settings.json` 的 excludeTools 全域唯讀鎖。若日後發現 agy 誤寫檔案造成事故，這是根因候選，備份在同目錄 `*.2026-07-07.bak`
4. **「被導向 Opus 4.8 的請求是否消耗原方案額度」**：查不到，未確認。要答案只能到平台 usage 頁實測
5. **agy model picker 掛羊頭的傳聞**：僅社群回報，未經確認，寫進 harness-diagnosis 時已標註

## 未完成 / 交接事項

- **其他機器**需重跑 `bash ~/Agent_skill/setup.sh` 才有四條 symlink（本機 2026-07-07 已完成並實測）
- 下游專案的專案層 AGENTS.md / GEMINI.md 注入（inject.sh 目前只管 CLAUDE.md）——全域 symlink 已覆蓋大多數需求，專案層等真的需要再做
- commits 未 push 是本 repo 常態（使用者指示只 commit，push 另外說）——接手時看到未 push 不要自作主張推
- ~~`memory/project-context.md` 的技術選型欄位仍是模板占位~~ → **2026-08-04 已刪除**。那些空欄位（架構概覽 / 技術選型 / 環境設定 / 外部依賴等，共 17 處「（填入）」）在制度倉庫永遠不會有內容，卻被連續 4 份 handoff 當成待辦掃到。刪除理由與「不要加回來」寫在該檔同名段落

制度補得了執行品質，補不了品味與模糊題。遇到時：升級模型、外部第二意見、或明說做不到。這句話值得每個 session 重讀一次。
