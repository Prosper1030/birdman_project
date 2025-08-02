# Birdman Project

## 最新更新

- 改進甘特圖功能
  - 優化圖表顯示效果
  - 支援水平和垂直捲動
  - 增加外部邊距空間
  - 支援 SVG/PNG 格式匯出
- 介面精簡化
  - 匯入與匯出統一整合至「檔案」選單
  - 「設定與輸入」分頁移除檔案選擇按鈕，僅顯示路徑資訊
- CPM 分析優化
  - 使用工時（小時）作為時間單位
- 移除天數轉換功能，提供更精確的時間計算
- 優化關鍵路徑顯示
- 修正浮點數誤差導致關鍵任務判斷失效
- 合併後依賴關係圖新增節點上色，合併節點以淡珊瑚色標示
- 修正依賴關係圖節點顏色顯示異常
- 重構圖表容器，切換主題時重新建立畫布避免殘影
- 執行完整分析時自動計算八種情境，預設顯示「新手 - 期望時間」
- 新增「匯入資料夾」選項，可同時載入 WBS 與 DSM
- 改進深色/淺色模式切換，依賴圖與甘特圖的背景與文字顏色能即時更新
- 修正合併後依賴圖層級計算並強制繪製箭頭
- 蒙地卡羅模擬可選擇新手或專家數據
- 甘特圖標題顯示當前情境與總工時

## 功能說明

1. **基本分析**
   - DSM 排序與合併
   - WBS 層次分析
   - 依賴關係圖生成
2. **視覺化功能**

   - 分層式依賴關係圖顯示
   - 支援圖表縮放與捲動
   - 甘特圖時間軸優化
   - 支援深色/淺色主題切換

3. **CPM 分析**

   - 工時計算（小時為單位）
   - 關鍵路徑識別
   - 甘特圖視覺化
   - 完整的時程資訊
   - 預設使用 `Te_newbie` 作為 CPM 計算工期欄位
   - 新增蒙地卡羅模擬，可評估工期分佈
   - 模擬角色可切換新手或專家
4. **RCPSP 排程**
   - 透過 OR-Tools 求解資源受限排程
   - 使用 --rcpsp-opt 取得優化結果


5. **匯出功能**
   - 支援 SVG/PNG 格式
   - 高品質圖表輸出
   - 分析結果 CSV 匯出

此工具根據 DSM 與 WBS 檔案計算任務依賴層級，輸出排序後的 WBS，並提供 CPM 分析功能。

DSM 矩陣中，若某列某欄的值為 `1`，代表該列任務必須等待該欄任務完成。
建圖時會將此視為「欄任務 -> 列任務」的邊。

## 環境需求

建議使用 **Python 3.10** 以上版本，並先安裝 `requirements.txt` 內的相依套件。

## 執行方式

```bash
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json
```

完成後會在目前目錄生成 `sorted_wbs.csv`、`merged_wbs.csv`，以及 `sorted_dsm.csv`。

此專案為鳥人間團隊開發的 DSM/WBS 處理工具，提供拓撲排序、強連通分量分析與任務合併等功能，並具備簡易 GUI。

## 主要功能

- 讀取 DSM 與 WBS 並驗證資料
- DSM 拓撲排序、下三角化與 SCC 分析
- WBS 依排序重排並加入 Layer、SCC_ID
- 同一 SCC 任務自動合併並計算工時
- 合併時自動判斷 Task ID 年份並建立新任務編號，若年份不一致將報錯
- 新合併任務的 Name 欄位預設留空
- 以 CSV 匯出排序與合併結果
- GUI 可在 DSM 分頁正確顯示 Task ID 行表頭
- 依賴性視覺化：新分頁展示任務間依賴圖及 SCC 群組
- k 係數參數設定：透過對話框調整合併演算法參數
- 主題選單支援深色/淺色切換

## 使用方式

### CLI

```bash
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json
```
執行後會在目前目錄產生 `sorted_wbs.csv`、`merged_wbs.csv` 及 `sorted_dsm.csv`。
若加上 `--cmp` 參數，會同時輸出 `cmp_analysis.csv`，並可使用 `--export-gantt` 匯出甘特圖、`--export-graph` 匯出依賴關係圖。工期欄位可透過 `--duration-field` 指定。
若需評估工期分佈，可加入 `--monte-carlo 500` 執行 500 次模擬，信心水準可用 `--mc-confidence 0.9` 指定（預設為 0.9）。

若需執行資源受限排程，可加入 `--rcpsp-opt`，將產生 `rcpsp_schedule.csv`。
### GUI（推薦 PyQt5 進階版）

#### PyQt5 進階 GUI

```bash
pip install -r requirements.txt
python -m src.gui_qt
```

#### 進階 GUI 功能

1. **檔案操作**

   - 支援選擇 DSM/WBS 檔案
   - 即時預覽資料內容
   - CSV 格式匯出結果
   - 匯出合併後 DSM（CSV 與 Excel）

2. **視覺化功能**

   - 多分頁檢視（原始資料、排序結果、合併結果）
   - 分層式依賴關係圖顯示
   - 支援圖表縮放與捲動
   - 可匯出高品質 SVG/PNG 格式圖表
   - DSM 中的依賴關係以紅色醒目標示
   - 深色/淺色主題切換
   - 匯出原始與合併後依賴關係圖
   - 匯出甘特圖與 CPM 分析結果
   - CPM 分析結果可匯出乾淨報告（CSV/Excel）
   - CPM 分析可切換 O、P、M、TE 或 All Scenarios
   - CPM 分析結果分頁具備情境切換選單
   - 甘特圖上方顯示總工時並依 CPM 結果排序任務
   - 甘特圖標題同步顯示情境與總工時

3. **參數調整**
   - k 係數參數設定對話框
   - 支援 Override 功能
   - 設定值自動保存至 config.json

功能：

- 多分頁切換（原始/排序/合併/DSM 預覽）
- 表格預覽（像 Excel，可橫向捲動、欄位標題清楚）
- DSM 依賴格自動標紅
- 匯出功能完整
- 新增依賴關係圖分頁，能以圖形呈現任務依賴

## 依賴視覺化範例

(此處可放入依賴關係圖截圖)

> **僅提供 PyQt5 版 GUI，請確保已安裝對應套件。**

## 安裝套件

```bash
pip install -r requirements.txt
```

執行此指令會同時安裝 `networkx` 等必要套件。

## 系統設定 (config.json)

此檔記錄執行流程所需的設定，主要區塊包括：

1. **cmp_params**
   - `work_hours_per_day`：每日工作小時數。
   - `working_days_per_week`：每週工作天數。
   - `default_duration_field`：CPM 分析預設使用的工期欄位，若未額外指定即採用此欄位，預設為 `"Te_newbie"`。
   - `project_start_date`：專案開始日期，可為空值。
   - `time_unit`：時間單位，預設為 `"hours"`。
2. **merge_k_params**
   - `override`：直接覆寫合併計算的 k 值。
   - `base`：基礎係數，固定為 1.0。
   - `trf_scale`：TRF 轉換比例，用於調整估算幅度。
   - `trf_divisor`：TRF 除數，平滑複雜度對 k 值的影響。
   - `n_coef`：數量係數，根據合併任務數量調整權重。
3. **visualization_params**
   - `node_color`：一般節點顏色。
   - `scc_color_palette`：SCC 群組顏色陣列。
   - `font_size`：字型大小。

## WBS.csv 欄位詳解

- `TRF`：任務複雜度係數，數值不得為負。
- `M_expert`：專家評估的最可能工時。
- `O_expert`：專家的樂觀工時。
- `P_expert`：專家的悲觀工時。
- `Te_expert`：依 PERT 公式 `(O + 4*M_expert + P) / 6` 計算的期望工時。
- `K_adj`：估算新手工時的調整係數。
- `O_newbie`、`M_newbie`、`P_newbie`：將專家對應的時間乘以 `K_adj` 後得出的新手估算工時。
- `Te_newbie`：根據新手時間以 PERT 公式計算出的期望工時，也是系統新的預設工時。

## 範例資料

`sample_data/` 內含 DSM.csv 與 WBS.csv，可供測試。

## 測試

安裝套件後，可直接於專案根目錄執行 `pytest`，驗證主要功能是否正常。

```bash
pytest
```
安裝完成後，也可執行 `flake8` 確保程式碼格式一致。

```bash
flake8
```