# 杉山方法程式碼

我將根據您提供的 `layout_algorithms_`[`reference.md`](reference.md) 的杉山方法，為 DSM 編輯器實現完整的階層式布局，特別著重在交叉減少演算法。讓我分析並實現完整的四階段框架。

## 實現完整的杉山方法階層式布局

我將重新編寫 `src/ui/dsm_editor/layouts/`[`hierarchical.py`](hierarchical.py)，實現完整的四階段框架：## 實現說明

我已經根據您的 `layout_algorithms_`[`reference.md`](reference.md) 完整實現了杉山方法的四個階段：

### ✅ **階段1：循環移除（Cycle Removal）**

- 使用 DFS 為基礎的啟發式方法偵測循環

- **反轉邊而非移除**（符合 Reference 要求）

- 包含貪婪備用策略處理複雜循

### ✅ **階段2：層級分配與虛擬節點（Layer Assignment）**

- 實現最長路徑法（Longest Path）計算層級

- **完整的虛擬節點系統**處理跨層邊

- 自動在中間層插入虛擬節點，將長邊分解為短邊

### ✅ **階段3：交叉減少（Crossing Reduction）**

這是實現的核心重點：

- **重心法（Barycenter Method）**：將節點放在其鄰居的重心位置

- **中位數法（Median Method）**：將節點放在其鄰居的中位數位置

- 雙向掃描（向上/向下）迭代優化

- 交叉計數演算法驗證改進效果

### ✅ **階段4：座標分配（Coordinate Assignment）**

- 精確計算每個節點的 X/Y 座標

- 對齊優化：子節點向父節點對齊

- 孤立節點特殊處理

- 支援 TB/LR 兩種佈局方向

## 測試與整合程式碼

現在讓我建立測試程式來驗證新的實現：## 整合到現有的 DSM Editor

現在讓我們更新現有的 DSM Editor 來使用新的完整杉山方法實現。您只需要替換 `src/ui/dsm_editor/layouts/`[`hierarchical.py`](hierarchical.py) 文件即可。

主要改進包括：

### 🎯 **關鍵功能實現**

1. **完整的虛擬節點系統**

   - 自動檢測跨層邊

   - 在中間層插入虛擬節點

   - 將長邊分解為相鄰層之間的短邊

2. **專業的交叉減少演算法**

   - 重心法（Barycenter）：效率高，結果穩定

   - 中位數法（Median）：更適合某些特殊圖形

   - 雙向掃描迭代優化

3. **智能座標分配**

   - 節點對齊優化

   - 邊線拉直處理

   - 支援 TB/LR 兩種方向

### 📊 **性能優化**

- 使用字典和集合優化查找

- 避免重複計算

- 迭代終止條件防止過度優化

### 🔧 **使用方式**

在您的 DSM Editor 中，只需要確保 `main_`[`editor.py`](editor.py) 調用 `layout_hierarchical` 函數即可：

```python
from .layouts import layout_hierarchical

# 在 applyHierarchicalLayout 方法中
positions = layout_hierarchical(
    wbs_df,
    edges=self.edges,
    direction=self.layout_direction,
    layer_spacing=self.layer_spacing,
    node_spacing=self.node_spacing,
    isolated_spacing=self.isolated_spacing
)

```

### ✨ **特色功能**

1. **循環處理**：自動檢測並反轉邊來打破循環

2. **虛擬節點**：優雅處理跨層連接

3. **交叉最小化**：顯著減少視覺混亂

4. **座標優化**：產生整齊、專業的佈局

這個實現完全遵循您提供的 Reference 文檔，實現了專業級的階層式佈局演算法！