<!-- AI/人工自動任務與重大異動/bug/決策日誌，回溯必查。 -->

# Birdman Project | AI_LOG.md

## 格式範例（僅供參考，請依實際專案移除或覆蓋）

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

