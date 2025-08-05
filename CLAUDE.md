# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

本文件為 Claude Code (claude.ai/code) 在此儲存庫中工作提供指導。

## Important: Documentation Hierarchy / 重要：文件階層

**必讀順序**：
1. **Requirements.md** - 唯一技術規格中心，所有架構、演算法、規範的最高權威
2. **AGENTS.md** - 完整協作規範與 AI SOP，包含詳細開發指南
3. **PROJECT_INTENT.md** - 專案設計理念與文件結構邏輯
4. **本文件 (CLAUDE.md)** - Claude Code 專用操作指引

**衝突解決原則**：當本文件與 Requirements.md 或 AGENTS.md 有衝突時，以 Requirements.md 為最高準則。

## Development Commands / 開發指令

### Testing and Linting / 測試與程式碼檢查
```bash
pytest              # 執行所有測試
pytest -q           # 安靜模式執行測試
flake8 src/ tests/ main.py --max-line-length=120  # 檢查程式碼格式，限制專案檔案範圍
```

**重要行為準則**：
- **純閱讀/分析任務**：不執行 pytest 或 flake8，避免浪費時間
- **程式碼修改後**：必須執行測試與程式碼檢查確保品質
- **文件修改**：通常不需要執行測試，除非涉及程式碼範例

### Running the Application / 執行應用程式
```bash
# 命令列介面
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json

# GUI 圖形介面
python -m src.gui_qt                    # 完整 PyQt5 GUI
python src/ui/main_window.py           # 僅蒙地卡羅視窗

# 常用 CLI 選項
python main.py --dsm <dsm_file> --wbs <wbs_file> --config config.json --monte-carlo 1000
python main.py --dsm <dsm_file> --wbs <wbs_file> --config config.json --rcpsp-opt --resources Resources.csv
```

### Dependencies / 相依套件
```bash
pip install -r requirements.txt        # 安裝所有相依套件
```

### AI Logging and Synchronization / AI 日誌與同步
```bash
# 重要操作後須更新相關文件
# Important: Update relevant docs after major operations

# 1. 重大異動記錄到 AI_LOG.md
# 2. 現況/缺口更新到 docs/AI_SYNC_README.md  
# 3. 確保與 Requirements.md 規格一致
```

## Code Architecture / 程式架構

### Core Components / 核心元件

1. **DSM Processing / DSM 處理 (`src/dsm_processor.py`)**
   - 處理依賴結構矩陣 (Dependency Structure Matrix) 操作
   - 主要函數：`readDsm()`, `buildGraph()`, `computeLayersAndScc()`, `processDsm()`
   - 執行拓樸排序和強連通分量 (SCC) 分析

2. **WBS Processing / WBS 處理 (`src/wbs_processor.py`)**
   - 工作分解結構 (Work Breakdown Structure) 處理
   - 按 SCC 合併任務：`mergeByScc()`
   - ID 驗證：`validateIds()`

3. **CPM Analysis / CPM 分析 (`src/cpm_processor.py`)**
   - 關鍵路徑法 (Critical Path Method) 計算
   - 主要函數：`cpmForwardPass()`, `cpmBackwardPass()`, `findCriticalPath()`
   - 蒙地卡羅模擬：`monteCarloSchedule()`
   - 預設使用 `Te_newbie` 欄位進行工期計算
   - 支援 Beta-PERT 分佈的風險分析

4. **RCPSP Solver / RCPSP 求解器 (`src/rcpsp_solver.py`)**
   - 資源受限專案排程問題 (Resource-Constrained Project Scheduling Problem) 求解
   - 使用 OR-Tools 進行最佳化
   - 支援多技能群組成員與動態資源分配
   - 整合學術行事曆約束與學生可用性建模

5. **Visualization / 視覺化 (`src/visualizer.py`)**
   - 依賴關係圖和甘特圖
   - 支援淺色/深色主題
   - 匯出格式：SVG、PNG

6. **GUI Interface / GUI 介面 (`src/gui_qt.py`)**
   - 基於 PyQt5 的進階 GUI，採用分頁介面
   - 整合所有處理功能
   - 支援主題切換 (QDarkStyle)

### Project Structure / 專案結構

- **`main.py`**: CLI 進入點，包含參數解析
- **`src/`**: 核心處理模組
- **`src/ui/`**: GUI 元件和模型
- **`sample_data/`**: 測試資料 (DSM.csv, WBS.csv, Resources.csv)
- **`tests/`**: 所有處理器的單元測試
- **`config.json`**: 合併參數、視覺化和 CPM 設定的配置檔

### Key Data Flow / 關鍵資料流程

1. 讀取 DSM (依賴矩陣) 和 WBS (任務分解)
2. 建立依賴圖並執行拓樸排序
3. 識別 SCC 並合併同一 SCC 內的任務
4. 生成新的 Task ID：`M<Year>-<流水號>[<原Task_ID列表>]`
5. 使用公式計算合併後工期：`k = 1 + sqrt((ΣTRF / n) * 10) / 10 + 0.05 * (n - 1)`
6. 執行 CPM 分析、蒙地卡羅模擬或 RCPSP 最佳化
7. 生成視覺化圖表並匯出結果

### Task Merging Algorithm / 任務合併演算法

**合併規則**：
- 同一 SCC 內的任務會被合併為單一新任務
- 新 Task ID 格式：`M<Year>-<流水號>[<原Task_ID列表>]`
- 工期計算公式：`合併時間 = 原時間總和 × k`
- k 係數公式：`k = base + sqrt((ΣTRF / n) * trf_scale / trf_divisor) + n_coef * (n - 1)`

**參數說明** (config.json 中的 merge_k_params)：
- `base`: 基礎係數 (預設 1.0)
- `trf_scale`: TRF 縮放係數 (預設 1.0)  
- `trf_divisor`: TRF 除數 (預設 10.0)
- `n_coef`: 任務數量係數 (預設 0.1)
- `override`: 可選的覆寫 k 值

### Advanced Features / 進階功能

**RACP (Resource Availability Cost Problem) 支援**
- 反推最小人力配置演算法
- 多技能群組成員建模與最佳化
- 學生團隊動態可用性處理

**學術行事曆整合**
- 支援 CalDAV、Google Calendar、Microsoft Graph API
- 智慧衝突偵測與解決機制
- 學期、考試期間的動態排程調整

**TRF (Task Risk Factor) 三維評估系統**
- 技術新穎性 (Novelty) - 權重 40%
- 內在複雜度 (Complexity) - 權重 40%  
- 外部依賴性 (Dependency) - 權重 20%

### Configuration / 配置說明

`config.json` 檔案包含三個主要區塊：
- `cmp_params`: 工作時數、預設工期欄位 (`Te_newbie`)、時間單位
- `merge_k_params`: 任務合併演算法參數
- `visualization_params`: 圖表顏色和字型設定

### Data Formats / 資料格式規範

**WBS (Work Breakdown Structure) 必要欄位**
- `Task_ID`: 採用「屬性代號年份-流水號」格式 (如 A26-001)
- `Name`: 任務名稱（支援中英文）
- `TRF`: 任務風險因子 (0-1 範圍)
- `Property`: 任務屬性分類 (0X, A, S, D, C, O, B, T, X, E, P, L, M)
- `Eligible_Groups`: 可執行該任務的組別清單
- `ResourceDemand`: 資源需求量（整數值）
- 工時估算：O/M/P/Te 的 expert/newbie 版本

**DSM (Design Structure Matrix) 格式**
- N×N 方陣，行列數相等
- 矩陣值為 0 或 1，1 表示行任務依賴列任務
- 支援循環依賴檢測與 SCC 分析

**Resources 資源配置**
- `Group`: 資源群組名稱
- `Hr_Per_Week`: 每週可投入工時
- `Headcount_Cap`: 人力上限
- 支援多技能群組成員建模

### Important Implementation Notes / 重要實作注意事項

- **Matplotlib 後端**: 使用 `matplotlib.use('Agg')` 避免與 PyQt5 介面衝突
- **時間單位**: CPM 分析預設使用小時，優先使用 `Te_newbie` 工期欄位
- **中文字型支援**: 應用程式包含 Windows/macOS/Linux 的自動中文字型偵測
- **主題切換**: GUI 支援淺色和深色模式的即時切換
- **匯出功能**: 統一整合到檔案選單以保持一致性

### Common Issues and Solutions / 常見問題與解決方案

1. **循環依賴問題**
   ```python
   # 當 DSM 中存在循環依賴時，會自動進行 SCC 分析
   # 同一 SCC 內的任務會被合併以解決循環
   ```

2. **GUI 主題切換問題**
   ```python
   # 確保使用 Agg backend 避免額外視窗
   import matplotlib
   matplotlib.use('Agg')
   ```

3. **中文字型顯示問題**
   ```python
   # 應用程式會自動偵測系統中文字型
   # Windows: msyh.ttc, macOS: STHeitiLight.ttc, Linux: NotoSansCJK
   ```

### Testing / 測試

- 單元測試涵蓋所有核心處理器
- 測試檔案命名規則：`test_<module_name>.py`
- `sample_data/` 目錄包含整合測試用的範例資料

### Development Workflow / 開發流程

**AI 協作規範**（依據 AGENTS.md 與 PROJECT_INTENT.md）：

1. **開始任務前**：
   - 先讀取 Requirements.md 瞭解技術規格
   - 檢查 docs/AI_SYNC_README.md 了解現況與缺口
   - 確認 AGENTS.md 中的相關 SOP

2. **開發過程中**：
   - 執行 `pytest` 和 `flake8` 確保程式碼品質
   - 從最新 main 分支建立 feature 分支
   - 使用 sample_data 中的測試資料驗證功能
   - 遵循 Requirements.md 的技術規格，不得擅自偏離

3. **任務完成後**：
   - 重大異動記錄到 docs/AI_LOG.md
   - 更新 docs/AI_SYNC_README.md 的現況、缺口、待辦事項
   - 如發現規格衝突，記錄到 AI_SYNC_README.md 並標記疑問
   - 功能完成後立即合併到 main 分支

4. **衝突解決原則**：
   - 發現文件間衝突時，以 Requirements.md 為最高準則
   - 不得擅自創建新的主要文件
   - 所有變更必須與現有主規格文件邏輯一致

### Language and Communication / 語言與溝通規範

- 所有註解、文件和使用者介面文字應使用繁體中文
- 程式碼命名適當時採用 camelCase
- 錯誤訊息和 GUI 元件使用繁體中文
- 與使用者的所有互動都使用繁體中文

### File Structure and Responsibilities / 檔案結構與職責

**核心文件職責分工**：
- **Requirements.md**: 技術規格、演算法、架構的唯一權威來源
- **AGENTS.md**: 完整協作規範、開發 SOP、AI 行為準則
- **PROJECT_INTENT.md**: 專案設計理念、文件結構邏輯說明
- **AI_LOG.md**: AI/人工重大異動、決策、bug 修復日誌
- **AI_SYNC_README.md**: 現況摘要、缺口分析、待辦事項追蹤
- **long_term_roadmap.md**: 長期技術發展藍圖與多階段規劃

**docs/ 目錄結構**：
```
docs/
├── Requirements.md          # 技術需求規格書
├── AI_LOG.md               # AI 操作日誌
├── AI_SYNC_README.md       # 同步狀態追蹤
└── long_term_roadmap.md    # 長期發展路線圖
```

### Integration with Other AI Systems / 與其他 AI 系統整合

本專案採用多 AI 協作模式：
- **Claude Code**: 需求分析、程式碼修改、問題診斷
- **OpenAI Codex**: 雲端沙盒程式碼實作
- **GitHub Copilot**: 程式碼輔助生成 (Claude Sonnet 3.5/3.7/4)

**協作原則**：
1. 優先讀取 AGENTS.md 了解協作規範
2. Codex 以 AGENTS.md 為主要參考，Claude Code 以本文件為輔助
3. 所有 AI 產出必須符合 Requirements.md 技術規格
4. 異動後統一更新 AI_LOG.md 和 AI_SYNC_README.md