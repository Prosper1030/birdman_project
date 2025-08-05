<!-- 本檔記錄全專案文件結構、協作邏輯、AI/協作者須知，務必先讀完 -->

# Birdman Project | PROJECT_INTENT.md

## 專案文件結構與 AI/協作設計理念

本文件用於說明本專案的**文件設計邏輯、協作規範、AI/成員溝通規則、痛點來源與核心目的**，讓所有 AI Agent（ChatGPT、Claude、Gemini、Grok 等）、人工協作者、新成員都能第一時間掌握專案檔案用途、前後關係與開發優先順序。

---

## 1. 為什麼要設計這套文件/目錄？

### 1.1 核心痛點
- 初期文件/代碼分散、命名混亂，AI/成員難以同步理解「主需求」「規格決策」「現況/缺口（gap）」「異動」等。
- 各 LLM 協作時 context 易斷線，常產生重複、誤解、版本衝突。
- 需求不明、版本不同步，導致分工、PR、AI 產物品質降低。

### 1.2 設計目標
- 所有**規格/決策/現況/異動/bug/gap/待辦**一律檔案化，依責任分層與標準格式維護。
- AI/人工協作必須**先讀規格再執行任務**，並於每次異動後自動記錄。
- 讓所有 LLM agent 能**快速掌握專案現狀、文件分工、規範依據**，並能 trace 異動。
- 實現 AI/人工內容「可追蹤、可溯源、易同步」，人工 review 精確。

---

## 2. 主要檔案用途/前後邏輯（所有檔案均已於 AGENTS.md 詳列，以下為精華說明）

### docs/Requirements.md
- **唯一技術需求中心**，1000+ 行完整技術規格書，包含 RACP 演算法、RCPSP 求解、學術行事曆整合、多技能群組建模等所有架構與技術細節。

### AGENTS.md  
- **AI 協作主規範**，符合 OpenAI Codex 標準的指令格式，包含強制性程式檢查、程式碼風格、技術架構說明、工作流程等。Codex 優先參考此文件。

### CLAUDE.md
- **Claude Code 專用指引**，包含開發指令、架構說明、常見問題解決方案等。當與 Requirements.md 衝突時，以 Requirements.md 為準。

### docs/long_term_roadmap.md
- **長期技術藍圖**，記錄多階段開發目標、演算法規劃、微服務架構轉換等未來擴展計畫。與 Requirements.md 區分短期與長期目標。

### docs/AI_SYNC_README.md
- **現況追蹤中心**，AI/人工任務執行後自動更新的現況、缺口、疑問、待辦清單。提供即時專案狀態。

### docs/AI_LOG.md
- **AI 操作日誌**，記錄所有 AI 重大異動、決策歷程、bug 修復、協作過程的完整追蹤。

### README.md
- **專案入口文件**，提供快速開始指南、實際功能說明、完整 CLI 使用範例。已根據實際程式碼功能更新。

---

## 3. 文件設計原則與 AI/協作目標

1. **多 LLM 跨平台協作的 context 完整性**：
   - 任何 AI agent 均能 reference 到主需求、規範、現況、異動流程，減少 context 遺失。
2. **痛點導向、可溯源、自動化**：
   - 所有異動皆有據可查，每位協作者能從現有文件迅速獲得規格/現況/缺口/SOP。
3. **AI 產物品質保障**：
   - 產出 code/docs 全按唯一規格、現況落地，且自動/手動 trace 變動，便於人工/AI review。
4. **團隊知識傳承與永續經營**：
   - 全檔案可追蹤、可版本控，新成員、AI agent 皆能一鍵理解、參與任務並追查歷史脈絡。

---

## 4. 你的困擾（AI/人類應該理解的現實問題）

- 規格、現況、需求分散，AI/人工常寫錯或 context 不全。
- LLM（特別是 code LLM）常無法同步主需求，創建新檔時 context 斷裂，導致冗餘與衝突。
- 多人/多 AI 並行作業時難以追蹤誰動過什麼、gap 是否補完、任務是否完成，協作審查低效。
- AI 產物 traceability 不足、易產生資訊孤島，人工 review 困難。
- 需 AI/人工能主動優化現有文件，產生「架構化、一致、可追蹤」內容。

---

## 5. 對 AI/協作者/Agent 的行動建議與規則

- 產出 code/docs **一律遵守 Requirements.md 規格**，有疑問先查 AGENTS.md 或寫入 AI_SYNC_README.md。
- 異動後同步 AI_LOG.md（重大）、AI_SYNC_README.md（gap/現況/疑問/待辦）。
- 新建/優化文件前**先 review 現有主文件/規範**，嚴禁任意分岔規格或產生不明新檔。
- 產生/修改內容時，應優先補齊主文件、避免資訊孤島或版本衝突。
- CLAUDE.md 只針對 Claude Code agent，若和主需求衝突，以 Requirements.md 為準。

---

## 6. 行動建議（給 AI 參考）

- 如需調整/優化/補齊文件，請先判斷「文件定位/用途」再修改，勿混淆規劃與落地。
- 發現 gap/規格不一致，**先寫入 AI_SYNC_README.md 並建議同步 Requirements.md**。
- 每次異動請務必記錄 AI_LOG.md，保持全 trace。
- 新功能或重構時，請參考 long_term_roadmap.md 但**以 Requirements.md 為唯一落地規格依據**。
- 產出內容後請自動 review requirements.md/AI_SYNC_README.md/AI_LOG.md 等，確保資訊一致。

---

**本文件必須同步維護，重大異動請於 AGENTS.md/README/Requirements.md 連動導引。**

