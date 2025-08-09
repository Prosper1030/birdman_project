# src/ 目錄架構說明

本目錄包含專案的核心邏輯與 UI 模組，採用清晰的功能分層架構。

## 📁 目錄結構

```
src/
├── README.md                    # 本檔案
├── dsm_processor.py             # DSM (依賴結構矩陣) 處理器
├── wbs_processor.py             # WBS (工作分解結構) 處理器  
├── cpm_processor.py             # CPM (關鍵路徑法) 分析器
├── rcpsp_solver.py              # RCPSP (資源受限排程) 求解器
├── visualizer.py                # 視覺化圖表生成器
├── gui_qt.py                    # 主要 PyQt5 GUI 入口
└── ui/                          # UI 模組架構
    ├── main_app/                # 主應用程式 (多求解器頁面)
    ├── dsm_editor/              # DSM 依賴關係編輯器
    └── shared/                  # 共用 UI 元件
```

## 🔧 核心處理器模組

### DSM 處理器 (`dsm_processor.py`)
- **功能**: 處理依賴結構矩陣 (Dependency Structure Matrix) 操作
- **主要函數**: `readDsm()`, `buildGraph()`, `computeLayersAndScc()`, `processDsm()`
- **特色**: 執行拓樸排序和強連通分量 (SCC) 分析，自動解決循環依賴

### WBS 處理器 (`wbs_processor.py`) 
- **功能**: 工作分解結構 (Work Breakdown Structure) 處理與驗證
- **主要函數**: `mergeByScc()`, `validateIds()`
- **特色**: 按 SCC 智慧合併任務，生成符合專案規範的新 Task ID

### CPM 分析器 (`cmp_processor.py`)
- **功能**: 關鍵路徑法 (Critical Path Method) 計算與蒙地卡羅模擬
- **主要函數**: `cmpForwardPass()`, `cmpBackwardPass()`, `findCriticalPath()`, `monteCarloSchedule()`
- **特色**: 預設使用 `Te_newbie` 欄位，支援 Beta-PERT 分佈風險分析

### RCPSP 求解器 (`rcpsp_solver.py`)
- **功能**: 資源受限專案排程問題求解與最佳化
- **技術**: 使用 OR-Tools 進行最佳化計算
- **特色**: 支援多技能群組成員動態資源分配與學術行事曆約束

### 視覺化器 (`visualizer.py`)
- **功能**: 生成依賴關係圖、甘特圖等專案視覺化圖表
- **特色**: 支援淺色/深色主題，匯出 SVG、PNG 格式
- **字型**: 內建跨平台中文字型自動偵測

## 🎨 UI 模組架構

詳見 [`src/ui/README.md`](ui/README.md) 了解完整 UI 架構說明。

### 設計理念
- **功能分離**: 主應用程式與 DSM 編輯器完全分離
- **模組化**: 每個功能模組獨立開發與維護  
- **共用元件**: 通用 UI 工具統一管理，避免重複開發
- **擴展性**: 新功能可輕鬆整合到現有架構

## 📊 資料流程

1. **資料讀取**: DSM 和 WBS 檔案讀取與驗證
2. **圖形建立**: 建立依賴關係圖，執行拓樸排序  
3. **SCC 分析**: 識別強連通分量，合併循環依賴任務
4. **工期計算**: 使用改良公式計算合併後任務工期
5. **分析執行**: CPM 分析、蒙地卡羅模擬或 RCPSP 最佳化
6. **結果視覺化**: 生成圖表並匯出結果

## 🔄 任務合併演算法

### 合併規則
- 同一 SCC 內的任務自動合併為單一新任務
- 新 Task ID 格式：`M<Year>-<流水號>[<原Task_ID列表>]`
- 工期計算：`合併時間 = 原時間總和 × k`

### k 係數公式
```
k = base + sqrt((ΣTRF / n) * trf_scale / trf_divisor) + n_coef * (n - 1)
```

**參數說明** (可在 `config.json` 調整):
- `base`: 基礎係數 (預設 1.0)
- `trf_scale`: TRF 縮放係數 (預設 1.0)
- `trf_divisor`: TRF 除數 (預設 10.0)  
- `n_coef`: 任務數量係數 (預設 0.1)

## 🚀 快速開始

```bash
# CLI 介面
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json

# GUI 介面  
python -m src.gui_qt                    # 完整 PyQt5 GUI
python src/ui/main_window.py           # 僅蒙地卡羅視窗

# 測試與程式碼檢查
pytest                                 # 執行所有測試
flake8 src/ tests/ main.py --max-line-length=120  # 程式碼格式檢查
```

## 🔧 進階功能

### RACP (Resource Availability Cost Problem) 支援
- 反推最小人力配置演算法
- 多技能群組成員建模與最佳化
- 學生團隊動態可用性處理

### 學術行事曆整合
- 支援 CalDAV、Google Calendar、Microsoft Graph API
- 智慧衝突偵測與解決機制  
- 學期、考試期間的動態排程調整

### TRF (Task Risk Factor) 三維評估
- **技術新穎性** (Novelty) - 權重 40%
- **內在複雜度** (Complexity) - 權重 40%
- **外部依賴性** (Dependency) - 權重 20%

## 📝 配置檔說明

`config.json` 包含三個主要區塊:

- `cmp_params`: 工作時數、預設工期欄位、時間單位
- `merge_k_params`: 任務合併演算法參數
- `visualization_params`: 圖表顏色和字型設定

## 🧪 測試

- 單元測試涵蓋所有核心處理器
- 測試檔案位於 `tests/` 目錄
- `sample_data/` 目錄提供整合測試用範例資料

## 📚 相關文件

- **[Requirements.md](../docs/Requirements.md)**: 完整技術規格文檔
- **[AGENTS.md](../AGENTS.md)**: AI 協作開發規範  
- **[CLAUDE.md](../CLAUDE.md)**: Claude Code 操作指南