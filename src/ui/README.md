# src/ui/ 目錄架構說明

本目錄實現專案的使用者介面 (UI) 架構，採用清晰的功能分離與模組化設計。

## 📁 目錄結構

```
src/ui/
├── README.md                    # 本檔案
├── __init__.py                  # UI 模組統一匯出入口
├── main_app/                    # 🏠 主應用程式 (多求解器頁面)
│   ├── __init__.py             
│   ├── main_window.py           # 主視窗與分頁管理
│   └── workers.py               # 背景工作執行緒 (蒙地卡羅等)
├── dsm_editor/                  # ✏️ DSM 依賴關係編輯器
│   ├── __init__.py
│   ├── main_editor.py           # 編輯器主入口與功能整合
│   ├── nodes.py                 # 任務節點 (yEd 風格互動)
│   ├── edges.py                 # 連線邊與箭頭效果
│   ├── scene.py                 # 圖形場景管理
│   ├── view.py                  # 畫布檢視 (縮放/平移/選取)
│   ├── handles.py               # 節點調整把手 (8 方向縮放)
│   ├── commands.py              # 撤銷/重做命令系統
│   ├── routing.py               # 邊線路由演算法
│   └── layouts.py               # 階層式佈局演算法
└── shared/                      # 🔧 共用 UI 元件
    ├── __init__.py
    ├── models.py                # 表格資料模型 (Pandas 整合)
    └── selection_styles.py      # 通用選取樣式管理器
```

## 🏠 主應用程式 (`main_app/`)

### 功能概述
整合多種專案管理求解器的主頁面，提供統一的操作介面。

### 核心元件

#### `main_window.py` - 主視窗
- **分頁管理**: 蒙地卡羅模擬、CPM 分析、RCPSP 求解、RACP 分析
- **參數設定**: 角色選擇 (新手/專家)、迭代次數、資源檔案
- **結果展示**: 即時統計數據、機率分布圖、甘特圖生成
- **執行緒管理**: 背景執行防止 UI 凍結

#### `workers.py` - 背景工作
- **蒙地卡羅工作者**: `MonteCarloWorker` 類別
- **Beta-PERT 抽樣**: 支援 O/M/P 三點估算分佈
- **進度回報**: 即時更新模擬進度條  
- **執行緒安全**: 支援中途停止與結果回傳

### 使用範例

```python
from src.ui import MainWindow

# 啟動主應用程式
app = MainWindow()
app.show()
```

## ✏️ DSM 編輯器 (`dsm_editor/`)

### 功能概述
提供 yEd 風格的依賴關係視覺化編輯器，支援拖拽、連線、佈局等進階功能。

### 核心元件

#### `main_editor.py` - 編輯器主入口
- **檔案管理**: DSM/WBS 匯入匯出、格式驗證
- **佈局引擎**: 階層式佈局、網格對齊、自動排列
- **功能整合**: 統一管理所有子元件與工具列

#### `nodes.py` - 任務節點
- **yEd 風格互動**: 點擊選取、拖拽移動、右鍵選單
- **視覺狀態**: 懸停高亮、選取標示、連線模式指示
- **調整把手**: 8 方向縮放控制 (整合自 `handles.py`)
- **智慧行為**: 選取狀態下僅允許拖拽，防止誤觸連線

```python
# 節點互動邏輯 (yEd 標準)
# 1. 點擊未選取節點 → 選取該節點
# 2. 拖拽選取節點 → 移動位置  
# 3. 從未選取節點拖出 → 開始連線模式
# 4. 右鍵節點 → 顯示編輯選單
```

#### `edges.py` - 連線邊
- **精確路由**: 節點邊界自動偵測、箭頭方向計算
- **視覺效果**: 光暈箭頭、選取高亮、懸停回饋
- **路徑更新**: 節點移動時自動重新計算路徑

#### `scene.py` - 圖形場景
- **連線管理**: 兩階段連線、臨時預覽線、多點連接
- **碰撞檢測**: 精確的滑鼠事件處理與物件偵測
- **場景狀態**: 連線模式、選取模式的統一管理

#### `view.py` - 畫布檢視
- **檢視控制**: 滑鼠縮放、平移、框選多重選取
- **網格對齊**: 可選的網格吸附功能
- **效能最佳化**: OpenGL 加速、視圖範圍裁剪

#### `commands.py` - 命令系統
- **撤銷/重做**: 基於命令模式的操作歷史
- **支援操作**: 節點移動、新增邊、刪除邊、節點縮放
- **批次操作**: 多重選取的統一處理

#### `routing.py` - 邊線路由
- **簡易路由器**: `SimpleEdgeRouter` 提供基礎直線連接
- **可擴展性**: 為未來複雜路由演算法預留介面

#### `layouts.py` - 佈局演算法
- **階層式佈局**: 基於拓樸排序的分層佈局
- **循環處理**: 自動偵測並解決 SCC 循環依賴  
- **客製參數**: 層間距、節點間距、方向控制

### 使用範例

```python  
from src.ui import DsmEditor

# 開啟 DSM 編輯器
editor = DsmEditor()
editor.loadFromFiles('dsm.csv', 'wbs.csv')
editor.show()
```

## 🔧 共用元件 (`shared/`)

### 功能概述
提供主應用程式與 DSM 編輯器都會使用的通用 UI 工具。

### 核心元件

#### `models.py` - 表格資料模型  
- **`PandasModel`**: DataFrame 的 Qt 表格模型
- **DSM 模式**: 支援依賴矩陣的特殊顯示 (1 值紅色標示)
- **動態更新**: 資料變更時自動更新檢視

#### `selection_styles.py` - 選取樣式管理
- **`SelectionStyleManager`**: 統一的選取視覺效果
- **降彩度效果**: selected 狀態自動降低顏色飽和度
- **提亮效果**: hovered 狀態自動提高顏色亮度
- **多重選取**: `MultiSelectionManager` 支援複選操作
- **邊線選取**: `EdgeSelectionHelper` 提供邊線專用選取邏輯

### 設計模式

#### 選取狀態視覺化
```python
# 自動產生選取樣式，保持視覺一致性
selected_brush = SelectionStyleManager.create_selection_brush(original_brush, "selected")
hovered_pen = SelectionStyleManager.create_selection_pen(original_pen, "hovered")
```

## 🔄 UI 架構設計原則

### 1. 功能分離
- **主應用程式**: 專注數據分析與結果展示
- **DSM 編輯器**: 專注圖形互動與依賴編輯
- **共用元件**: 避免重複開發，維持一致性

### 2. 模組化設計
- 每個功能模組獨立開發與測試
- 清晰的介面定義，降低耦合度
- 便於功能擴展與維護

### 3. 一致性原則
- 統一的選取樣式與互動邏輯
- 一致的錯誤處理與使用者回饋
- 標準化的匯入匯出流程

### 4. 效能最佳化
- 背景執行緒防止 UI 凍結
- OpenGL 硬體加速支援
- 智慧重繪與視圖裁剪

## 🎨 視覺設計特色

### yEd 風格互動
- 熟悉的節點選取與拖拽行為
- 直觀的連線建立流程
- 專業的調整把手與視覺回饋

### 主題支援
- 淺色與深色主題自動切換
- 高對比度的選取指示
- 中文字型跨平台相容性

### 可訪問性
- 清晰的視覺層次與對比
- 鍵盤快速鍵支援 
- 螢幕閱讀器友善設計

## 🚀 快速開始

### 匯入所有 UI 元件
```python
from src.ui import (
    MainWindow,         # 主應用程式
    MonteCarloWorker,   # 背景工作
    DsmEditor,          # DSM 編輯器
    PandasModel,        # 表格模型
    SelectionStyleManager  # 選取樣式
)
```

### 啟動完整 GUI
```python
# 方法 1: 透過主程式啟動
python -m src.gui_qt

# 方法 2: 直接啟動主視窗
python src/ui/main_app/main_window.py
```

## 🔧 客製化擴展

### 新增求解器分頁
1. 在 `main_app/main_window.py` 新增分頁建立函數
2. 實作對應的 `Worker` 類別處理背景計算
3. 更新 `__init__.py` 匯出新元件

### 擴展 DSM 編輯器功能  
1. 在 `dsm_editor/` 新增功能模組
2. 在 `main_editor.py` 整合新功能
3. 實作對應的 `Command` 類別支援撤銷

### 新增共用元件
1. 在 `shared/` 實作新的通用元件
2. 更新 `shared/__init__.py` 匯出
3. 在需要的地方匯入使用

## 📚 相關技術

### PyQt5 架構
- **Model-View-Controller**: 資料與視圖分離
- **Signal-Slot 機制**: 事件驅動的非同步通信
- **Graphics View Framework**: 高效能圖形渲染

### 設計模式
- **命令模式**: 撤銷/重做功能實作
- **觀察者模式**: UI 更新與資料同步
- **策略模式**: 佈局演算法與路由器的可替換設計

## 🐛 常見問題

### Q: 如何新增自訂節點類型？
A: 繼承 `TaskNode` 類別，重寫 `paint()` 方法自訂外觀。

### Q: 如何實作新的佈局演算法？
A: 在 `layouts.py` 新增函數，遵循現有的參數與回傳格式。

### Q: 如何支援新的檔案格式？
A: 在對應的處理器新增讀取函數，並在 `main_editor.py` 整合匯入選項。

## 📝 待辦功能

- [ ] 實作複雜邊線路由演算法
- [ ] 支援節點群組與摺疊功能  
- [ ] 新增更多佈局選項 (力導向、樹狀等)
- [ ] 實作協作編輯與版本控制
- [ ] 支援更多匯出格式 (PDF、SVG 等)