# AGENTS.md

## 0️⃣ 專案簡介

`birdman_project` 是針對鳥人間團隊專案管理與任務工時計算的 Python 工具，主要功能包括：

- 讀取 DSM（Dependency Structure Matrix）與 WBS（Work Breakdown Structure）
- 自動拓撲排序與下三角化 DSM
- 分層與強連通分量（SCC）分析
- 任務合併與新 Task_ID 生成
- 依據 TRF 與公式計算合併後工時
- 輸出排序後與合併後的 WBS
- 開發語言為 Python 3.10，採用 GUI 介面，可將結果以 CSV/Excel 匯入匯出

---

## 1️⃣ 輸入資料規格

### 1.1 DSM（Dependency Structure Matrix）

- 格式：CSV 方陣，大小為 N×N
- 標題：

  - Row 0：第 0 欄空白，之後每一欄為 Task_ID
  - Column 0：第 0 列為 Task_ID

- 矩陣值：

  - 0 → 無依賴
  - 1 → row 任務必須等待 col 任務完成

- 檢查要求：

  - 必須是方陣
  - Task_ID 唯一且與 WBS 對應
  - 無多餘空白列或欄

### 1.2 WBS（Work Breakdown Structure）

- 格式：CSV
- 必要欄位：

  - Task_ID（第一欄，唯一識別碼）
  - TRF（任務複雜度係數）

- 其他可選時間欄位：

  - O_expert、M_expert、P_expert、Te_expert
  - O_newbie、M_newbie、P_newbie、Te_newbie

- 檢查要求：

  - 所有 Task_ID 必須存在於 DSM
  - TRF 必須為正數或 0
  - 時間欄位若缺失，需給出提示或補 0

---

## 2️⃣ 核心功能與流程

### 2.1 DSM 下三角化與排序

- 讀取 DSM 並驗證格式
- 執行拓撲排序（Topological Sort）
- 轉換 DSM 為下三角矩陣（保證所有依賴在左上方）
- 產出排序後的 Task_ID 順序
- 注意：若出現循環依賴（Cycle），需先進行 SCC 分析並給使用者提示

### 2.2 強連通分量（SCC）與分層

- 使用 Tarjan 或 Kosaraju 演算法計算 SCC
- 為每個任務分配 SCC ID
- 將任務依層次（Layer）排序，SCC 內的任務會在同層
- 在 WBS 中新增一欄 SCC_ID 以標記結果

### 2.3 WBS 重新排序與標記

- 根據 DSM 排序結果與 SCC ID 將 WBS 重新排序
- 新增 Layer 與 SCC_ID 欄位
- 對於相同 SCC_ID 的任務以顏色標記（Excel）
- 輸出 `sorted_wbs.csv` 及 `sorted_wbs.xlsx`

### 2.4 任務合併與新 Task_ID 生成

- 將相同 SCC_ID 的任務合併為單一新任務
- 新任務命名規則：
  `M<Year>-<流水號>[<原Task_ID列表>]`
  例：`M25-001[A25-003,D25-006,C25-007]`

  - <Year>：手動設定或由系統讀取
  - <流水號>：由上到下，從 001 開始
  - <原 Task_ID 列表>：用逗號分隔，順序為合併前在 WBS 的先後順序

- 合併後將後續任務自動上移，保持連續編號

### 2.5 工時計算公式

- 對每個合併後任務，計算工時係數：

  ```
  k = 1 + sqrt((ΣTRF / n) * 10) / 10 + 0.05 * (n - 1)
  ```

  - ΣTRF：合併前所有任務 TRF 總和
  - n：合併的任務數

- 對每個時間欄位（O/M/P/Te 的 expert/newbie 版本）進行：

  ```
  合併時間 = 原時間總和 × k
  ```

### 2.6 輸出

- 排序後的 WBS（含 SCC_ID 與 Layer）
- 合併後的 WBS（含新 Task_ID、顏色標記、合併後時間）
- 可視化 DSM 或簡單依賴圖（可選）

---

## 3️⃣ GUI 功能

- 選擇 DSM.csv 與 WBS.csv
- 顯示排序與分層結果（可簡單表格）
- 按鈕匯出：

  - sorted_wbs.csv
  - merged_wbs.csv（含顏色）

---

## 4️⃣ 錯誤處理

- DSM 不是方陣 → 錯誤提示
- Task_ID 不匹配 → 錯誤提示
- 存在循環依賴 → 提示並顯示 SCC 內容

---

## 5️⃣ 格式與溝通規範

- **所有程式註解、說明、與使用者溝通皆需使用繁體中文**
- 所有介面、提示訊息、文件說明皆採繁體中文
- 程式碼撰寫需條理分明，註解清楚，每個核心步驟請加說明
- 每次產生 code 請附上簡易功能說明與範例使用說明
- 回答問題請條列重點、說明步驟，並盡量解釋原理
- 程式碼命名請統一 camelCase（如無特殊需求）
- 你可以根據需求隨時新增功能，只要補在 2️⃣ 核心功能與流程章節後即可

---

## 6️⃣ 未來擴充說明

- 本專案預留擴充性，未來可新增 CPM、Slack、蒙地卡羅/RCPSP 相關功能，請於 2️⃣ 核心功能與流程章節補充說明，並明確列出演算法、步驟與輸出規格。
- 新功能規範、流程或格式要求，亦可在 5️⃣ 章節內補充。
