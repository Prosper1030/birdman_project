<!-- AI/人工自動任務與重大異動/bug/決策日誌，回溯必查。 -->

# Birdman Project | AI_LOG.md

## 格式範例（僅供參考，請依實際專案移除或覆蓋）

## 2025-08-05 | ChatGPT：新增 RCPSP GUI 資源設定與結果顯示
- 目標：在 GUI 中整合 RCPSP 求解結果並允許自訂資源容量
- 結果：完成資源設定對話框與排程結果呈現，並加入單元測試驗證

## 2025-08-05 | ChatGPT：補齊函式繁體中文註解
- 目標：檢查並補充 src 目錄下所有函式的繁體中文 Google Style docstring
- 結果：完成 docstring 統一與格式修正，並通過 pytest 與 flake8

## 2025-01-09 | Claude Code：完善專案文件生態系統
- 目標：全面優化專案文件結構與協作流程
- 執行內容：
  - 更新 README.md：根據實際 CLI 功能重寫，新增完整使用範例與技術架構說明
  - 同步 PROJECT_INTENT.md：更新文件路徑與職責說明，確保與實際文件結構一致
  - 簡化 requirements.txt：移除精確版本限制，改用相容性範圍，提升安裝成功率
  - 優化測試策略：區分程式碼變更與文件變更的測試需求，避免文件修改時執行不必要的測試
- 結果：建立了更高效、更實用的專案文件生態系統，降低開發與協作成本

## 2025-01-09 | Claude Code：重構 AGENTS.md 符合 Codex 規範
- 目標：根據 OpenAI Codex 對 AGENTS.md 的規範要求，重構文件格式與內容
- 執行內容：
  - 重新組織為 Codex 友善的指令格式
  - 新增強制性程式檢查指令（pytest、flake8、應用程式測試）
  - 明確定義程式碼風格、命名規範、檔案組織結構
  - 補充技術架構說明與核心元件介紹
  - 規範 Git/PR 流程與 commit message 格式
  - 強化多 AI 系統間的協作規則
- 結果：AGENTS.md 現在完全符合 Codex 期望，提供明確的技術指令與品質檢查要求

## 2025-01-09 | Claude Code：整合並完善 CLAUDE.md
- 目標：根據 Requirements.md、AGENTS.md、PROJECT_INTENT.md 等主要文件，全面更新 CLAUDE.md
- 執行內容：
  - 新增文件階層說明與衝突解決原則
  - 補充 RACP 演算法、多技能群組成員建模、學術行事曆整合等核心技術
  - 強化 AI 協作規範與同步機制
  - 詳細說明資料格式規範（WBS、DSM、Resources）
  - 整合與其他 AI 系統（Codex、Copilot）的協作原則
- 結果：CLAUDE.md 已與專案主要文件保持一致，AI 協作規範更加完整

## 2024-08-03 20:50 | Codex：自動補全WBS組別
- 目標：依 Resources.csv 批次補全 WBS.csv 的 Eligible_Groups
- 結果：完成，2項未配對，gap已寫入AI_SYNC_README.md

## 2024-08-03 18:00 | Prosper（人工修改）
- 目標：重構 requirements.md，補RCPSP規格
- 結果：已同步AI_SYNC_README.md

---

> 正式紀錄請覆蓋本範例內容，僅保留每次AI/人工重要異動之精簡紀錄即可。

