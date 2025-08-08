# DSM 編輯器箭頭與路由系統修復任務

## 專案概述

這是一個基於 PyQt5 的依賴結構矩陣 (DSM) 編輯器專案，用於視覺化和編輯專案任務間的依賴關係。專案採用圖形化介面，支援拖拽式節點編輯和自動化佈局功能。

### 專案結構
```
birdman_project/
├── src/
│   ├── ui/
│   │   ├── dsm_editor.py          # 主編輯器類別 (核心問題所在)
│   │   ├── layout_dialogs.py      # yEd 風格佈局對話框
│   │   └── main_window.py         # 主視窗
│   ├── routing/                   # 路由系統 (新增)
│   │   ├── engine.py             # 路由引擎
│   │   └── enhanced_edge_item.py # 進階邊線項目
│   ├── layout/                   # 佈局系統
│   │   └── hierarchical.py       # 階層式佈局引擎
│   └── gui_qt.py                 # GUI 主入口
├── sample_data/                  # 測試資料
├── ROUTING_TASK.md              # 原始路由需求文檔
└── opus/                        # 進階演算法參考
```

## 核心問題描述

### 🎯 主要問題：邊線箭頭完全消失

**現象**：
- DSM 編輯器中的所有邊線都沒有箭頭顯示
- 原本應該有黑色三角形箭頭指向目標節點
- 連線功能正常，但視覺指向性完全缺失

**影響**：
- 使用者無法判斷依賴關係的方向性
- 嚴重影響 DSM 的可讀性和實用性

### 🐛 次要問題：連線模式錯誤

**現象**：
- 嘗試從節點拖拽建立新連線時程式崩潰
- 錯誤信息：`AttributeError: 'EnhancedEdgeItem' object has no attribute 'getConnectionPoint'`
- 錯誤發生在 `dsm_editor.py` 的 `updateTempConnection` 方法

**錯誤追蹤**：
```
File "src\ui\dsm_editor.py", line 1785, in updateTempConnection
    srcPos = self.tempEdge.getConnectionPoint(srcRect, srcCenter, dx, dy)
AttributeError: 'EnhancedEdgeItem' object has no attribute 'getConnectionPoint'
```

## 技術背景

### 當前架構
- **邊線系統**：使用 `EnhancedEdgeItem` (繼承自 `QGraphicsPathItem`)
- **路由引擎**：`RoutingEngine` 類負責路徑計算
- **箭頭系統**：應該由 `GlowArrowHead` 類處理
- **佈局系統**：`HierarchicalLayoutEngine` 提供 yEd 風格佈局

### 疑似問題根源
1. **路由引擎初始化**：`EnhancedEdgeItem.initialize_router()` 可能未被調用
2. **方法缺失**：`EnhancedEdgeItem` 缺少必要的介面方法
3. **箭頭創建**：`GlowArrowHead` 可能未正確附加到邊線
4. **場景整合**：箭頭物件可能未被正確添加到場景中

## 期望結果

### ✅ 主要目標
1. **所有邊線都有清晰可見的箭頭**
   - 黑色三角形箭頭指向目標節點
   - 箭頭大小適中且方向正確
   - 支援選取時的顏色變化（紅色）

2. **連線模式完全正常**
   - 從節點拖拽可建立新連線
   - 臨時連線有正確的箭頭預覽
   - 無任何 AttributeError 錯誤

3. **相容於現有功能**
   - 佈局系統正常運作
   - 節點拖拽不受影響
   - 檔案載入/儲存功能保持正常

### 🎨 視覺要求
- 箭頭尺寸：約 15 像素
- 正常狀態：黑色箭頭
- 選取狀態：紅色箭頭
- 臨時連線：灰色箭頭

## 相關程式碼位置

### 關鍵檔案
1. **`src/ui/dsm_editor.py`**
   - 第 1785 行：`updateTempConnection` 方法（錯誤位置）
   - DsmEditor 類的初始化部分
   - AddEdgeCommand 類（邊線創建）

2. **`src/routing/enhanced_edge_item.py`**
   - EnhancedEdgeItem 類
   - GlowArrowHead 類
   - 路由引擎初始化方法

3. **`src/routing/engine.py`**
   - RoutingEngine 類
   - 路由演算法核心

### 重要方法
- `EnhancedEdgeItem.__init__()` - 邊線初始化
- `EnhancedEdgeItem.initialize_router()` - 路由引擎初始化
- `GlowArrowHead.updatePosition()` - 箭頭位置更新
- `DsmEditor.__init__()` - 編輯器初始化

## 測試方式

### 驗證步驟
1. **啟動編輯器**：`python -m src.gui_qt`
2. **載入測試資料**：使用 `sample_data/` 中的 CSV 檔案
3. **檢查現有邊線**：確認是否有箭頭顯示
4. **測試新建連線**：嘗試從節點拖拽建立連線
5. **佈局測試**：使用「階層式」佈局檢查箭頭保持

### 成功標準
- [ ] 所有邊線都有箭頭
- [ ] 連線模式不會崩潰
- [ ] 箭頭方向正確
- [ ] 選取效果正常
- [ ] 佈局後箭頭保持顯示

## 額外資源

### 參考文檔
- `ROUTING_TASK.md` - 原始路由需求
- `opus/` 目錄 - 進階路由演算法範例
- `docs/Requirements.md` - 技術規格文檔

### 樣本資料
- `sample_data/DSM.csv` - 依賴矩陣
- `sample_data/WBS.csv` - 工作分解結構
- `sample_data/Resources.csv` - 資源配置

## 注意事項

1. **相容性**：確保修復不會影響現有的佈局和選取功能
2. **效能**：箭頭渲染不應顯著影響介面回應速度
3. **代碼品質**：遵循現有的代碼風格和架構模式
4. **錯誤處理**：適當的異常處理以避免崩潰

---

**總結**：這是一個視覺化問題修復任務，主要需要診斷和修復邊線箭頭顯示系統，並確保連線功能的穩定性。預期修復點集中在路由引擎初始化和箭頭物件的正確創建與附加。