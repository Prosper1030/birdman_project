# Birdman Project

## 專案簡介
`Birdman Project` 是一套以 Python 實作的專案管理工具，可從 DSM 與 WBS 資料進行任務排序、合併與時程分析。工具整合命令列與 PyQt5 圖形介面，支援多種視覺化與模擬功能。

## 核心功能
- **DSM/WBS 處理**：讀取並驗證資料，完成拓樸排序與強連通分量分析。
- **任務合併**：自動合併同一 SCC 的任務，重新建立 Task ID 並計算工期。
- **依賴關係圖與甘特圖**：提供分層式依賴圖與甘特圖，可切換深色/淺色主題並匯出 SVG/PNG。
- **CPM 分析**：以小時為單位計算工期，找出關鍵路徑並產出詳細時程；預設使用 `Te_newbie` 欄位。
- **蒙地卡羅模擬**：採 Beta-PERT 分佈進行多次模擬，提供次數與密度兩種圖表模式並可匯出結果。
- **RCPSP 排程**：使用 OR-Tools 根據資源限制優化排程，輸出最佳開始時間。
- **GUI 介面**：PyQt5 進階介面整合檔案選取、視覺化、CPM、蒙地卡羅與 RCPSP 功能。
- **匯出功能**：排序後/合併後 WBS、DSM、依賴圖、甘特圖及分析結果皆可匯出。

## 安裝需求
- Python 3.10 以上版本。
- 先安裝相依套件：

```bash
pip install -r requirements.txt
```

## 命令列使用
基本範例：

```bash
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json
```

其他常用選項：
- `--monte-carlo 次數`：進行蒙地卡羅模擬。
- `--rcpsp-opt --resources Resources.csv`：執行 RCPSP 排程並輸出 `rcpsp_schedule.csv`。
- `--export-rcpsp-gantt PATH`：匯出 RCPSP 排程甘特圖。

## GUI 使用

```bash
python -m src.gui_qt        # 完整介面
python src/ui/main_window.py  # 單獨的蒙地卡羅視窗
```

## 系統設定 (config.json)
- **cmp_params**：`work_hours_per_day`、`working_days_per_week`、`default_duration_field`、`project_start_date`、`time_unit`。
- **merge_k_params**：合併演算法參數（`override`、`base`、`trf_scale`、`trf_divisor`、`n_coef`）。
- **visualization_params**：圖表顏色與字型設定（`node_color`、`scc_color_palette`、`font_size`）。

## WBS.csv 欄位
必需欄位：`Task_ID`、`TRF`、各角色工期 (如 `O_expert`、`M_expert`、`P_expert`、`Te_expert` 及其新手版本)，以及 `Te_newbie`。
若要使用 RCPSP，需另外提供 `Category` 與 `ResourceDemand` 欄位。

## 範例資料
`sample_data/` 內含 `DSM.csv`、`WBS.csv` 等測試資料，可直接用於演示與驗證。

## 測試與格式檢查

```bash
pytest
flake8
```
