# DSM 編輯器 Web 化可行性評估

本文件用於評估 Birdman 專案的 DSM 編輯器是否適合從目前的 PyQt 版本延伸為 Web 版本。

## 1. 結論

目前建議：

- 先把 PyQt 版本穩定為正式可用工具
- 再逐步抽離可重用的資料與驗證邏輯
- 不建議在這個階段直接重寫成 Web

原因很簡單：目前最複雜、風險最高的部分不是資料格式，而是圖形互動與邊線路由。這些在 PyQt 版本已經有可用成果，但若直接搬到 Web，前端互動層幾乎需要重寫。

## 2. 可以直接沿用的部分

以下邏輯很適合保留為 Python 端或抽成中立資料層：

- WBS / DSM 的 CSV 載入格式
- `validateEditorInputs()` 的資料驗證規則
- DSM 矩陣與有向圖的互轉規則
- SCC 與循環摘要計算
- 工作階段快照格式
- autosave 的目錄結構與 `session.json` schema

這些都已經偏向資料規則，不依賴 PyQt 視圖本身，後續很適合抽成：

- `src/core/dsm_session.py`
- `src/core/dsm_validation.py`
- `src/core/dsm_snapshot.py`

## 3. 可以先抽成純 Python 的項目

若未來要做 Web，建議先抽以下三塊，再談前端：

### 3.1 驗證與資料模型

- WBS / DSM 驗證
- Session 狀態資料結構
- 匯出與恢復流程

### 3.2 圖形分析邏輯

- 邊集合與 DSM 矩陣轉換
- SCC 計算
- 循環摘要
- dirty 狀態判斷

### 3.3 工作階段持久化

- autosave
- 版本輪替
- 恢復判斷

若這三塊先抽好，Web 版前端只需要處理互動，不必重新發明資料規則。

## 4. Web 端幾乎必須重寫的部分

以下項目無法直接搬用，實務上要重寫：

- `QGraphicsScene / QGraphicsView` 畫布互動
- 節點拖曳、框選、縮放、對齊
- 邊線繪製與 hover / selected / highlight 效果
- yEd 風格正交邊線路由顯示
- 視窗快捷鍵與選單互動
- QMessageBox / QFileDialog 這類桌面 UI 流程

換句話說，PyQt 版本的 `nodes.py`、`edges.py`、`scene.py`、`view.py`、大部分 `main_editor.py`，在 Web 版只能當互動規格參考，不能直接視為可移植程式碼。

## 5. Web 技術選型建議

若未來要做 Web，建議方向如下：

- 前端：React + React Flow 或類似節點圖框架
- 邊線：前端自行畫 SVG path，正交路由可先做簡化版
- 後端：保留 Python，提供驗證、SCC、autosave、匯出 API
- 儲存：沿用目前 session snapshot 結構，再包成 API

不建議一開始就追求完全重現目前 PyQt 的 yEd 級路由效果，因為那會大幅拉長開發時間。

## 6. 主要風險

### 6.1 路由與互動成本高

Web 版若要做到目前這種邊線重繪、高亮、框選、拖曳與正交路由組合，工作量遠高於資料層。

### 6.2 使用者期望會上升

一旦做成 Web，使用者通常會期待：

- 多人共享
- 權限管理
- 歷程版本
- 多檔案管理
- 瀏覽器效能穩定

這些都不是單純「把桌面版搬上網頁」而已。

### 6.3 目前還沒有抽乾淨的核心層

現在雖然已經把 session / validation 往 `src/ui/dsm_editor/session.py` 集中，但 GUI 與資料邏輯仍有耦合。若現在直接轉 Web，等於一邊拆架構、一邊重寫前端，風險較高。

## 7. 建議的實施順序

### Phase 1

- 持續穩定 PyQt 版
- 補足文件與測試
- 把 session / validation / snapshot 邏輯抽成更明確的核心模組

### Phase 2

- 做一版很小的 Web prototype
- 只驗證載入 DSM、顯示節點、編輯邊、顯示 SCC
- 暫時不追求完整 yEd 風格正交路由

### Phase 3

- 視 prototype 結果決定是否擴充為正式產品
- 若要正式化，再補多人協作、後端 API、權限與部署

## 8. 目前最值得做的前置整理

若目標是讓未來 Web 化更順，眼前最值得做的不是直接寫前端，而是：

- 繼續縮小 `main_editor.py` 的責任
- 把快照與恢復流程從 UI 呼叫拆成獨立服務函式
- 定義清楚的 session 資料模型與匯出格式
- 讓更多測試直接驗證資料層而不是 GUI 行為

這樣未來不管是 PyQt、Web，甚至 CLI 批次工具，都能共用同一套核心邏輯。
