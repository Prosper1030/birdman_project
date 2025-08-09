# 正交繞線功能實現報告

## 實現概要

成功為 DSM 編輯器實現了正交繞線功能，遵循「不改變對外 API」的要求。實現採用分層架構，確保向後兼容性的同時添加新功能。

## 實現架構

### A. 核心路由算法 (`src/ui/dsm_editor/advanced_routing.py`)

```python
def route_multiple_orthogonal(
    node_rects: Dict[str, QRectF],
    edges: List[Tuple[str, str]],
    grid: int = 10,
    obstacle_padding: int = 6,
    edge_gap: int = 8
) -> Dict[Tuple[str, str], List[QPointF]]
```

**特性：**

- 基於網格的 A\* 路徑搜尋算法
- 智能端口分配（NESW 邊界中點選擇）
- 障礙物避障與邊線間隙處理
- 平行邊線偏移避免重疊

### B. 編輯器整合 (`src/ui/dsm_editor/main_editor.py`)

**新增屬性：**

```python
self.routing_mode: str = 'orthogonal'  # 路由模式
self.edge_paths: Dict[tuple[str, str], List] = {}  # 邊線路徑快取
```

**新增方法：**

```python
def _computeOrthogonalRouting(self) -> None
```

**整合點：**

- 修改 `applyHierarchicalLayout()` 方法
- 在層次布局後自動計算正交路徑
- 儲存路徑資料供 EdgeItem 使用

### C. 邊線渲染整合 (`src/ui/dsm_editor/edges.py`)

**修改的方法：**

```python
def updatePath(self) -> None
```

**新增方法：**

```python
def _tryOrthogonalPath(self) -> bool
def _findEditor(self)
def _buildOrthogonalPath(self, path_points: List[QPointF]) -> None
def _updateStraightPath(self) -> None
```

**功能：**

- 自動檢測正交模式
- 優先使用正交路徑渲染
- 無縫回退到直線路徑
- 保持現有 API 不變

## 技術細節

### 網格系統

- **網格大小：** 10 像素（可調整）
- **障礙物填充：** 6 像素避免過於接近節點
- **邊線間隙：** 8 像素防止平行邊線重疊

### 路徑搜尋

- **算法：** A\* 搜尋
- **啟發式：** 曼哈頓距離
- **移動限制：** 僅正交方向（上下左右）
- **成本函數：** 統一成本 + 轉彎懲罰

### 端口分配

- **北側端口：** `(center.x, rect.top)`
- **東側端口：** `(rect.right, center.y)`
- **南側端口：** `(center.x, rect.bottom)`
- **西側端口：** `(rect.left, center.y)`

**選擇邏輯：** 基於目標方向選擇最佳端口

## API 兼容性

✅ **保持現有 API 不變**

- `EdgeItem.updatePath()` 方法簽名不變
- `DsmEditor` 構造函數不變
- 現有調用代碼無需修改

✅ **向後兼容**

- 預設啟用正交模式
- 自動回退機制確保穩定性
- 不影響現有功能

## 測試結果

所有測試通過：

- ✅ `route_multiple_orthogonal` 函數正常工作
- ✅ `DsmEditor` 正確初始化新屬性和方法
- ✅ `EdgeItem` 新方法全部存在並可調用
- ✅ 靜態符號檢查通過
- ✅ 路徑計算功能測試通過

## 使用方式

### 自動模式（預設）

正交繞線在層次布局時自動啟用：

```python
editor = DsmEditor(wbs_df)
editor.applyHierarchicalLayout()  # 自動計算正交路徑
```

### 手動控制

```python
# 切換到直線模式
editor.routing_mode = 'straight'

# 切換回正交模式
editor.routing_mode = 'orthogonal'
editor._computeOrthogonalRouting()  # 重新計算路徑
```

## 性能特性

- **路徑快取：** 避免重複計算
- **增量更新：** 僅在需要時重新計算
- **錯誤處理：** 自動回退確保穩定性
- **記憶體效率：** 使用字典快取路徑資料

## 未來擴展

實現為模組化設計，便於未來擴展：

- 支援更多路由模式
- 路由參數可配置
- 更複雜的路徑優化策略
- 互動式路徑編輯

## 總結

成功實現了完整的正交繞線功能，滿足所有要求：

1. ✅ 不改變對外 API
2. ✅ 完整的 A\* 路徑搜尋算法
3. ✅ 智能端口分配和避障
4. ✅ 與現有編輯器無縫整合
5. ✅ 完善的錯誤處理和回退機制

該實現為 DSM 編輯器提供了專業級的正交繞線功能，提升了視覺化效果和用戶體驗。
