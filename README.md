# Birdman Project

此專案為鳥人間團隊開發的 DSM/WBS 處理工具，提供拓撲排序、強連通分量分析與任務合併等功能，並具備簡易 GUI。

## 主要功能

- 讀取 DSM 與 WBS 並驗證資料
- DSM 拓撲排序、下三角化與 SCC 分析
- WBS 依排序重排並加入 Layer、SCC_ID
- 同一 SCC 任務自動合併並計算工時
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

## 範例資料

`sample_data/` 內含 DSM.csv 與 WBS.csv，可供測試。
