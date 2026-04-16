# Birdman Project

此工具根據 DSM 與 WBS 檔案計算任務依賴層級並輸出排序後的 WBS。

DSM 矩陣中，若某列某欄的值為 `1`，代表該列任務必須等待該欄任務完成。
建圖時會將此視為「欄任務 -> 列任務」的邊。

## 執行方式

```bash
python3 main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv
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

## 使用方式

### CLI

```bash
python3 main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv
```

執行後會在目前目錄產生 `sorted_wbs.csv`、`merged_wbs.csv` 及 `sorted_dsm.csv`。

### GUI

```bash
python3 -m src.gui_qt
```

使用視窗選擇檔案後執行，畫面中央會預覽資料，可放大或縮小。分析完成後，可依需求按下按鈕匯出 `sorted_wbs.csv`、`merged_wbs.csv` 或 `sorted_dsm.csv`。

### DSM 編輯器 (快速測試工具)

```bash
python3 run_dsm_editor.py                                      # 使用預設 sample 資料
python3 run_dsm_editor.py --wbs path/to/WBS.csv                # 只載入 WBS，從空白依賴圖開始
python3 run_dsm_editor.py --wbs path/to/WBS.csv --dsm path/to/DSM.csv
python3 run_dsm_editor.py --help                               # 顯示說明
```

直接啟動視覺化的 DSM 依賴關係編輯器，支援載入既有 DSM、連線編輯、循環 SCC 提示、工作階段 autosave 與安全匯出。

補充文件：

- [DSM 編輯器使用流程](docs/dsm_editor_workflow.md)
- [DSM 編輯器 Web 化可行性評估](docs/dsm_editor_web_feasibility.md)

## 安裝套件

```bash
bash scripts/setup_mac.sh
```

此腳本會在專案根目錄建立 `.venv`，並安裝 `requirements.txt` 內的必要套件。

如果你想手動安裝，也可以使用：

```bash
python3 -m pip install -r requirements.txt
```

## macOS / Mac mini 啟動方式

建議先執行一次安裝腳本：

```bash
bash scripts/setup_mac.sh
```

安裝完成後可使用以下方式啟動：

```bash
./start_birdman_gui.command    # 啟動主 GUI
./start_dsm_editor.command     # 啟動 DSM 編輯器
```

這些啟動檔會自動切回專案根目錄，因此不必手動 `cd` 到專案資料夾，也能正確抓到 `config.json` 與 `sample_data/`。

## 範例資料

`sample_data/` 內含 DSM.csv 與 WBS.csv，可供測試。

## 測試

安裝套件後，可直接於專案根目錄執行 `pytest`，驗證主要功能是否正常。

```bash
pytest
```
