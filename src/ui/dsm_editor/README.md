# DSM Editor 模組化架構

DSM Editor 是一個視覺化的依賴結構矩陣 (Dependency Structure Matrix) 編輯器，採用 yEd 風格的圖形介面，支援節點拖拽、連線編輯、多種佈局算法等功能。

## 📁 架構概覽

本模組已完成重構，從單一巨型檔案 (2316行) 拆分為 10 個職責分明的模組：

```
src/ui/dsm_editor/
├── __init__.py              # 模組入口，統一導出 API
├── main_editor.py           # 主編輯器類 (389行)
├── scene.py                 # 場景管理 (244行)
├── view.py                  # 視圖組件 (205行)
├── nodes.py                 # 節點相關類 (454行)
├── edges.py                 # 邊線相關類 (652行)
├── commands.py              # 命令模式類 (139行)
├── handles.py               # 調整手柄 (269行)
├── routing.py               # 簡單路由器 (66行)
├── layouts.py               # 階層式佈局演算法 (294行)
└── README.md                # 本說明文件
```

## 🚀 快速開始

### 基本使用

```python
from src.ui.dsm_editor import DsmEditor
import pandas as pd

# 建立 WBS 資料
wbs_df = pd.DataFrame({
    'Task ID': ['A26-001', 'A26-002', 'A26-003'],
    'Name': ['設計階段', '製造階段', '測試階段'],
    'Property': ['A', 'S', 'D']
})

# 建立編輯器實例
editor = DsmEditor(wbs_df)
editor.show()  # 顯示編輯器視窗
```

### 完整啟動範例

```python
# 使用 GUI 啟動器
from src.gui_qt import launch_editor

app, editor = launch_editor(wbs_df)
app.exec_()  # 執行 Qt 應用程式
```

## 📦 核心組件說明

### 🎮 主編輯器 (main_editor.py)

**`DsmEditor`** - 主要的編輯器視窗類別

- **功能**：統一管理整個編輯器的 UI、資料、和行為
- **職責**：選單列、工具列、佈局算法、命令執行、檔案操作
- **關鍵方法**：
  - `loadWbs(wbs_df)` - 載入 WBS 資料
  - `applyLayout(algorithm)` - 套用佈局算法
  - `executeCommand(command)` - 執行可撤銷命令
  - `exportDsm()` - 匯出 DSM 矩陣

### 🖼️ 場景管理 (scene.py)

**`DsmScene`** - 管理圖形場景和連線操作

- **功能**：節點與邊線的場景管理、連線模式控制
- **職責**：連線操作、場景事件處理、臨時連線管理
- **關鍵功能**：
  - yEd 風格的連線模式
  - 多固定點折線連線
  - 即時連線預覽

### 👁️ 視圖組件 (view.py)

**`CanvasView`** - 提供縮放、平移、框選功能的視圖

- **功能**：畫布視圖控制、使用者互動
- **職責**：滾輪縮放、中鍵平移、橡皮筋框選、網格顯示
- **特色**：
  - OpenGL 硬體加速 (如果可用)
  - 效能優化的背景繪製
  - 智能更新區域

### 🔗 節點管理 (nodes.py)

**`TaskNode`** - 代表工作任務的圖形節點

- **功能**：節點視覺化、互動行為、狀態管理
- **職責**：節點拖拽、選取、連線、調整大小、右鍵選單
- **yEd 風格特色**：
  - 精準的滑鼠行為邏輯
  - 選取/未選取狀態分明
  - 8個調整把手

### ➡️ 邊線系統 (edges.py)

**`EdgeItem`** - 代表依賴關係的箭頭連線
**`GlowArrowHead`** - 支援發光效果的箭頭

- **功能**：精確邊線繪製、視覺回饋、選取管理
- **職責**：邊線路徑計算、箭頭繪製、懸停效果、選取狀態
- **高級特色**：
  - 精確的邊界交點計算
  - yEd 風格發光效果
  - 雙向邊線分離
  - Shift+懸停高亮

### ⚡ 命令系統 (commands.py)

實現完整的撤銷/重做功能：

- **`AddNodeCommand`** - 新增節點
- **`AddEdgeCommand`** - 新增邊線
- **`RemoveEdgeCommand`** - 移除邊線
- **`MoveNodeCommand`** - 移動節點
- **`ResizeNodeCommand`** - 調整節點大小

### 🔧 調整手柄 (handles.py)

**`ResizeHandle`** - yEd 風格的節點調整把手

- **功能**：8個方向的節點大小調整
- **特色**：保持中心點固定、即時連線更新、精確游標樣式

### 🛤️ 路由系統 (routing.py)

**`SimpleEdgeRouter`** - 基本的直線路由器

- **用途**：提供簡單的點對點連線
- **擴展性**：可升級為智能路由

### 📐 佈局系統 (layouts.py)

**階層式佈局演算法** - 從 src/layouts/ 整合移入

- **功能**：基於拓樸排序的層次佈局、SCC 循環依賴處理
- **特色**：Longest-Path 分層演算法、網格對齊、客製化參數
- **模式**：簡單網格佈局、階層式分層、循環回退處理

## 🎨 主要功能特色

### ✨ yEd 風格的專業體驗

- **精準滑鼠邏輯**：選取、拖拽、連線行為完全符合 yEd 標準
- **視覺回饋**：懸停發光、選取高亮、降彩度效果
- **專業佈局**：階層式、正交式、力導向佈局算法

### 🎯 完整的編輯功能

- **節點操作**：拖拽移動、8方向調整、右鍵編輯
- **連線操作**：拖拽連線、多固定點折線、即時預覽
- **批量操作**：框選、多選、批量刪除

### ⚡ 效能優化

- **智能重繪**：最小區域更新、緩存背景
- **硬體加速**：OpenGL 支援、平滑渲染
- **記憶體優化**：精確的幾何計算緩存

## 🔧 開發者指南

### 擴展新功能

1. **新增節點類型**：繼承 `TaskNode` 類
2. **自訂邊線樣式**：繼承 `EdgeItem` 類
3. **新佈局算法**：在 `main_editor.py` 中新增方法
4. **智能路由**：使用 `advanced_routing.py` 的功能

### 除錯模式

```python
# 啟用詳細日誌
import logging
logging.basicConfig(level=logging.DEBUG)

# 或使用 run_dsm_editor.py 的除錯模式
python run_dsm_editor.py --debug
```

### 效能調優

- **大量節點**：考慮使用場景 LOD (Level of Detail)
- **複雜連線**：啟用高級路由引擎
- **記憶體限制**：調整場景範圍和緩存策略

## 📋 API 參考

### 主要類別導出

```python
from src.ui.dsm_editor import (
    # 主要類別
    DsmEditor,
    
    # 枚舉
    EditorState, LayoutAlgorithm,
    
    # UI 組件
    TaskNode, EdgeItem, GlowArrowHead,
    DsmScene, CanvasView, ResizeHandle,
    
    # 路由功能
    SimpleEdgeRouter,
    
    # 命令模式
    Command, AddNodeCommand, AddEdgeCommand,
    RemoveEdgeCommand, MoveNodeCommand, ResizeNodeCommand
)
```

### 常用操作範例

```python
# 程式化建立依賴關係
editor.addDependency(node1, node2)

# 套用佈局
editor.applyLayout(LayoutAlgorithm.HIERARCHICAL)

# 匯出 DSM
dsm_matrix = editor.buildDsmMatrix()

# 撤銷/重做
editor.undo()
editor.redo()
```

## 🔄 升級說明

本次重構完全向後相容，原有的 API 和使用方式保持不變。主要改進：

### ✅ 改進之處

- **可維護性提升** - 模組化架構便於修改和除錯
- **載入速度** - 按需載入減少啟動時間  
- **記憶體效率** - 更精確的物件管理
- **擴展性** - 新功能更容易整合

### 🗂️ 遷移指南

如果您之前直接導入 `dsm_editor.py` 的內部類別：

```python
# 舊方式 (已廢棄)
from src.ui.dsm_editor import TaskNode, EdgeItem

# 新方式 (推薦)
from src.ui.dsm_editor import TaskNode, EdgeItem
```

導入路徑保持不變，但現在來自模組化的實現。

## 🤝 貢獻指南

1. **修改核心邏輯**：主要在 `main_editor.py`
2. **視覺改進**：編輯 `nodes.py` 或 `edges.py`
3. **新增互動**：修改 `scene.py` 或 `view.py`
4. **效能優化**：檢查各模組的緩存和更新邏輯

## 📞 技術支援

- **功能問題**：檢查對應模組的實現
- **效能問題**：關注 `view.py` 的渲染邏輯
- **佈局問題**：參考 `layouts.py` 中的階層式演算法
- **路由問題**：檢查 `routing.py` 的基礎路由功能

---

**版本**：重構版 v2.0  
**相容性**：完全向後相容  
**效能**：大幅提升  
**維護性**：極大改善