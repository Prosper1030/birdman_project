# Birdman Project


此工具根據 DSM 與 WBS 檔案計算任務依賴層級並輸出排序後的 WBS。

DSM 矩陣中，若某列某欄的值為 `1`，代表該列任務必須等待該欄任務完成。
建圖時會將此視為「欄任務 -> 列任務」的邊。

## 執行方式

```bash
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv
```


完成後會在目前目錄生成 `sorted_wbs.csv` 與 `merged_wbs.csv`。

此專案為鳥人間團隊開發的 DSM/WBS 處理工具，提供拓撲排序、強連通分量分析與任務合併等功能，並具備簡易 GUI。

## 主要功能

- 讀取 DSM 與 WBS 並驗證資料
- DSM 拓撲排序、下三角化與 SCC 分析
- WBS 依排序重排並加入 Layer、SCC_ID
- 同一 SCC 任務自動合併並計算工時
- 合併時自動判斷 Task ID 年份並建立新任務編號，若年份不一致將報錯
- 新合併任務的 Name 欄位預設留空
- 以 CSV 匯出排序與合併結果

## 使用方式

### CLI

```bash
python main.py --dsm <DSM.csv> --wbs <WBS.csv>
```

執行後會在目前目錄產生 `sorted_wbs.csv` 與 `merged_wbs.csv`。

### GUI

```bash
python -m src.gui
```

使用視窗選擇檔案後執行，即可匯出結果。

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

