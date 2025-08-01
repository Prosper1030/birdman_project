# Birdman Project

## 最新更新

- 改進甘特圖功能
  - 優化圖表顯示效果
  - 支援水平和垂直捲動
  - 增加外部邊距空間
  - 支援 SVG/PNG 格式匯出
- CPM 分析優化
  - 使用工時（小時）作為時間單位
  - 移除天數轉換功能，提供更精確的時間計算
  - 優化關鍵路徑顯示

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

4. **匯出功能**
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
- 深色模式支援：可切換介面主題，包含圖表樣式

## 使用方式

### CLI

```bash
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --config config.json
```
執行後會在目前目錄產生 `sorted_wbs.csv`、`merged_wbs.csv` 及 `sorted_dsm.csv`。
若加上 `--cmp` 參數，會同時輸出 `cmp_analysis.csv`，並可使用 `--export-gantt` 匯出甘特圖、`--export-graph` 匯出依賴關係圖。工期欄位可透過 `--duration-field` 指定。

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

2. **視覺化功能**

   - 多分頁檢視（原始資料、排序結果、合併結果）
   - 分層式依賴關係圖顯示
   - 支援圖表縮放與捲動
   - 可匯出高品質 SVG/PNG 格式圖表
   - DSM 中的依賴關係以紅色醒目標示
   - 深色/淺色主題切換

3. **參數調整**
   - k 係數參數設定對話框
   - 支援 Override 功能
   - 設定值自動保存

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

## 範例資料

`sample_data/` 內含 DSM.csv 與 WBS.csv，可供測試。

## 測試

安裝套件後，可直接於專案根目錄執行 `pytest`，驗證主要功能是否正常。

```bash
pytest
```
