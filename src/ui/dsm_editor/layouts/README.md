# 佈局演算法套件

本套件提供多種專業的圖形佈局演算法，適用於不同類型的依賴關係視覺化：

## 📊 演算法總覽

| 演算法 | 適用場景 | 特點 | 狀態 |
|--------|----------|------|------|
| **階層式佈局** | 有向圖、流程圖 | **完整杉山方法**、循環處理、虛擬節點 | ✅ **重新實現** |
| **正交式佈局** | 整齊排列、網格化 | 規則網格、易讀性高 | ✅ 完成 |
| **力導向佈局** | 自然分佈、無明顯層級 | 物理模擬、自然群聚 | ✅ 完成 |

## 🔧 核心功能

### 階層式佈局 (Hierarchical Layout) **[重新實現]**

**檔案**: `hierarchical.py`

**核心演算法**: **完整杉山方法 (Complete Sugiyama Framework)**

**重大更新** 🎉：
- 🆕 **完整的四階段杉山框架實現**
- 🆕 **虛擬節點系統**：自動處理跨層邊
- 🆕 **專業交叉減少**：重心法迭代優化
- 🆕 **智能循環移除**：DFS + 反轉邊策略
- 🆕 **座標優化**：專業的座標分配算法

**四階段架構**:
1. **循環移除 (Cycle Removal)**: DFS 基礎的反轉邊策略
2. **層級分配 (Layer Assignment)**: 最長路徑法 + 虛擬節點插入
3. **交叉減少 (Crossing Reduction)**: 重心法雙向掃描優化
4. **座標分配 (Coordinate Assignment)**: 精確座標計算

**主要特性**:
- ✅ **虛擬節點自動處理**：跨層邊自動插入虛擬節點
- ✅ **循環智能處理**：自動檢測並反轉邊來打破循環
- ✅ **交叉最小化**：專業的重心法減少邊線交叉
- ✅ **孤立節點專門處理**：智能分離孤立節點
- ✅ **方向控制**：支援 TB/LR 兩種佈局方向
- ✅ **性能優化**：迭代終止條件，避免過度計算

**API 使用**:
```python
from .layouts import layout_hierarchical

positions = layout_hierarchical(
    wbs_df,
    edges=edges_set,
    direction="TB",          # "TB" 或 "LR"  
    layer_spacing=200,       # 層間距
    node_spacing=150,        # 節點間距
    isolated_spacing=100     # 孤立節點間距
)
```

**進階使用** - 直接使用杉山引擎:
```python
from .layouts import SugiyamaLayout

layout_engine = SugiyamaLayout()
coordinates = layout_engine.layout(wbs_df, edges)

# 獲取詳細信息
print(f"虛擬節點數: {len(layout_engine.virtual_nodes)}")
print(f"反轉邊數: {len(layout_engine.reversed_edges)}")
print(f"層級數: {len(set(layout_engine.layers.values()))}")
```

**技術細節**:
- 虛擬節點格式: `v_0, v_1, ...`
- 反轉邊記錄: `layout_engine.reversed_edges`
- 層級信息: `layout_engine.layers`
- 交叉計數: `layout_engine._count_all_crossings()`

### 正交式佈局 (Orthogonal Layout)

**檔案**: `orthogonal.py`

**核心演算法**: 網格排列

**主要特性**:
- ✅ 整齊網格：規則的矩形網格排列
- ✅ 群組支援：支援按屬性分組排列  
- ✅ 自適應間距：根據節點數量自動調整
- ✅ 最小重疊：智能間距避免視覺衝突

**API 使用**:
```python
from .layouts import layout_orthogonal

positions = layout_orthogonal(
    wbs_df,
    cols=5,                  # 列數，None 為自動
    spacing=120,             # 節點間距
    group_by=None           # 群組欄位名稱
)
```

### 力導向佈局 (Force-Directed Layout)

**檔案**: `force_directed.py`

**核心演算法**: Fruchterman-Reingold + 智能回退

**主要特性**:
- ✅ 物理模擬：基於彈簧力和排斥力的自然分佈
- ✅ 智能回退：無邊時自動切換到網格佈局
- ✅ 參數自適應：根據圖形規模自動調整參數
- ✅ 約束支援：支援固定節點的約束佈局

**API 使用**:
```python
from .layouts import layout_force_directed

positions = layout_force_directed(
    wbs_df,
    edges=edges_set,
    iterations=100,          # 迭代次數
    k_spring=1.0,           # 彈簧力係數
    k_repulsion=1.0,        # 排斥力係數
    scale=300,              # 佈局縮放
    seed=42                 # 隨機種子
)
```

## 🧪 測試與驗證

### 測試案例

**1. 簡單 DAG 測試**:
```python
task_ids = ['A', 'B', 'C', 'D', 'E', 'F']
edges = {('A', 'B'), ('A', 'C'), ('B', 'D'), ('C', 'D'), ('D', 'E'), ('E', 'F')}
```

**2. 循環圖測試**:
```python
edges = {('A', 'B'), ('B', 'C'), ('C', 'A'), ('A', 'D'), ('D', 'E')}
# 自動檢測並處理循環
```

**3. 跨層邊測試**:
```python
edges = {('Start', 'L1'), ('L1', 'L2'), ('L2', 'End'), ('Start', 'End')}
# 自動插入虛擬節點處理跨層邊
```

### 性能指標

- **交叉數最小化**: 通過重心法迭代優化
- **虛擬節點數**: 自動插入，處理跨層邊
- **層級分布**: 使用最長路徑法優化
- **計算效率**: 早期終止條件，避免過度迭代

## 📝 更新日誌

### v2.0.0 - 完整杉山方法實現
- 🎉 **重大更新**: 完整實現杉山方法四階段框架
- 🆕 虛擬節點系統：自動處理跨層邊
- 🆕 專業交叉減少：重心法迭代優化
- 🆕 智能循環處理：DFS + 反轉邊策略
- 🆕 座標優化算法：精確的座標分配
- 🔧 性能優化：智能終止條件
- 📚 完整的 API 文檔和測試案例

### v1.x - 基礎實現
- ✅ 基本階層分層
- ✅ SCC 檢測與合併
- ✅ 孤立節點處理
- ✅ 方向控制

## 🔗 相關資源

- **理論參考**: `docs/references/layout_algorithms_reference.md`
- **測試程式**: `sugiyama/test_sugiyama_layout.py`  
- **使用指南**: `sugiyama/how_to_use.md`
- **主要文獻**: Sugiyama Framework, Graphviz dot layout