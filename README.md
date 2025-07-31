# Birdman Project

此工具根據 DSM 與 WBS 檔案計算任務依賴層級並輸出排序後的 WBS。

DSM 矩陣中，若某列某欄的值為 `1`，代表該列任務必須等待該欄任務完成。
建圖時會將此視為「欄任務 -> 列任務」的邊。

## 執行方式

```bash
python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv --year 25
```

完成後會在目前目錄生成 `sorted_wbs.csv`。
