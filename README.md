# Birdman Project

**專案管理與排程最佳化工具**

本專案為成功大學航空太空工程系人力飛機專案設計的智慧型專案管理系統，整合 DSM 依賴分析、CPM 關鍵路徑、RCPSP 資源受限排程與蒙地卡羅風險模擬等核心功能。

## 快速開始

### 安裝
```bash
# 安裝相依套件
pip install -r requirements.txt

# 測試安裝
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json
```

### 啟動 GUI
```bash
python -m src.gui_qt
```

## 主要功能

### 🔄 DSM & WBS 處理
- 依賴結構矩陣 (DSM) 自動排序與循環依賴偵測
- 工作分解結構 (WBS) 驗證與任務屬性管理
- 強連通分量 (SCC) 分析與任務自動合併
- 支援任務風險因子 (TRF) 三維評估系統

### 📊 時程分析與最佳化
- **CPM 關鍵路徑分析**：自動計算最早/最晚時間與鬆弛時間
- **蒙地卡羅風險模擬**：Beta-PERT 分佈的隨機工期分析 (支援 1000+ 次模擬)
- **RCPSP 資源受限排程**：使用 OR-Tools 進行資源最佳化配置
- **多情境分析**：專家/新手 × 樂觀/最可能/悲觀/期望工時組合

### 📈 視覺化與匯出
- 分層式依賴關係圖 (支援大型專案捲動縮放)
- 動態甘特圖 (8 種情境即時切換)
- 淺色/深色主題一鍵切換
- 多格式匯出：CSV、Excel、SVG、PNG (300 DPI)

### 🖥️ 使用者介面
- **CLI 命令列**：適合批次處理與 CI/CD 整合
- **PyQt5 GUI**：9 個分頁的完整圖形介面，整合所有功能

## 系統需求

- **Python**: 3.10 以上版本
- **記憶體**: 建議 2GB 以上 (大型專案分析)
- **儲存空間**: 1GB 可用空間
- **平台**: Windows、Linux、macOS 跨平台支援

## 命令列使用

### 基本 DSM/WBS 處理
```bash
# 基本分析 (DSM 排序 + WBS 合併)
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json
```

### CPM 關鍵路徑分析
```bash
# 執行 CPM 分析
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json --cpm

# 指定工期欄位並匯出甘特圖
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json --cpm --duration-field Te_expert --export-gantt gantt.svg
```

### 蒙地卡羅風險模擬
```bash
# 1000 次模擬，85% 信心水準
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json --monte-carlo 1000 --mc-confidence 0.85
```

### RCPSP 資源最佳化
```bash
# 資源受限排程最佳化
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json --rcpsp-opt --resources sample_data/Resources.csv

# 匯出 RCPSP 甘特圖
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json --rcpsp-opt --resources sample_data/Resources.csv --export-rcpsp-gantt rcpsp_gantt.png
```

### 視覺化匯出
```bash
# 匯出依賴關係圖
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json --export-graph dependency_graph.svg
```

## GUI 圖形介面

### 啟動完整介面
```bash
python -m src.gui_qt
```

### 介面功能
- **檔案管理**：DSM/WBS/Resources 檔案選擇與預覽
- **即時分析**：一鍵執行所有分析功能
- **多分頁檢視**：
  - 排序 WBS/DSM：拓樸排序結果
  - 依賴關係圖：互動式圖表檢視
  - 合併 WBS/DSM：SCC 合併結果
  - CPM 分析結果：關鍵路徑詳細報告
  - 甘特圖：8 種情境動態切換
  - 蒙地卡羅模擬：次數/密度雙重圖表
  - 進階分析：RCPSP 等高級功能
- **主題切換**：深色/淺色模式
- **統一匯出**：檔案選單整合所有匯出功能

## 設定檔說明 (config.json)

### CPM 分析參數 (cmp_params)
- `work_hours_per_day`: 每日工作時數 (預設 8)
- `working_days_per_week`: 每週工作天數 (預設 5)
- `default_duration_field`: 預設工期欄位 (預設 "Te_newbie")
- `time_unit`: 時間單位 ("hours" 或 "days")

### 任務合併參數 (merge_k_params)
- `base`: 基礎係數 (預設 1.0)
- `trf_scale`: TRF 縮放係數 (預設 1.0)
- `trf_divisor`: TRF 除數 (預設 10.0)
- `n_coef`: 任務數量係數 (預設 0.1)
- `override`: 可選的覆寫 k 值

### 視覺化參數 (visualization_params)
- `node_color`: 一般節點顏色 (預設 "skyblue")
- `scc_color_palette`: SCC 群組顏色陣列
- `font_size`: 字型大小 (預設 8)

## 資料格式需求

### WBS.csv 必要欄位
- `Task_ID`: 任務唯一識別碼 (格式：屬性代號年份-流水號，如 A26-001)
- `Name`: 任務名稱
- `TRF`: 任務風險因子 (0-1 範圍)
- `Property`: 任務屬性分類 (0X, A, S, D, C, O, B, T, X, E, P, L, M)

### 工時估算欄位 (四點估時法)
- `O_expert/O_newbie`: 樂觀工時 (專家/新手)
- `M_expert/M_newbie`: 最可能工時
- `P_expert/P_newbie`: 悲觀工時
- `Te_expert/Te_newbie`: 期望工時

### RCPSP 額外欄位
- `Category`: 資源群組分類
- `ResourceDemand`: 資源需求量
- `Eligible_Groups`: 可執行該任務的組別清單

### DSM.csv 格式
- N×N 方陣，行列數相等
- 第一行/列為 Task_ID 列表
- 矩陣值為 0 或 1 (1 表示行任務依賴列任務)

### Resources.csv 格式
- `Group`: 資源群組名稱
- `Hr_Per_Week`: 每週可投入工時
- `Headcount_Cap`: 人力上限

## 範例資料

`sample_data/` 目錄包含完整的測試資料集：
- `DSM.csv`: 依賴結構矩陣範例
- `WBS.csv`: 工作分解結構範例 (包含所有必要欄位)
- `Resources.csv`: 資源配置範例

## 開發與測試

### 程式碼品質檢查
```bash
# 執行單元測試
pytest -q

# 程式碼風格檢查
flake8 src/ tests/ main.py --max-line-length=120
```

### 專案結構
```
birdman_project/
├── src/                    # 核心處理模組
│   ├── dsm_processor.py    # DSM 處理
│   ├── wbs_processor.py    # WBS 處理
│   ├── cpm_processor.py    # CPM 分析
│   ├── rcpsp_solver.py     # RCPSP 求解
│   ├── visualizer.py       # 視覺化
│   └── gui_qt.py          # PyQt5 GUI
├── tests/                  # 單元測試
├── sample_data/           # 範例資料
├── docs/                  # 技術文件
│   ├── Requirements.md    # 完整技術規格
│   └── AI_LOG.md         # 開發日誌
└── config.json           # 系統設定
```

## 技術支援

- **完整技術文件**: 請參閱 `docs/Requirements.md`
- **AI 協作規範**: 請參閱 `AGENTS.md`
- **問題回報**: [GitHub Issues](https://github.com/Prosper1030/birdman_project/issues)

## 授權

本專案為成功大學航空太空工程系內部開發工具。
