# yEd Edge Routing 系統整合指南

## 快速開始

### 1. 基本整合

```python
from yed_edge_routing import EnhancedEdgeItem, SceneEdgeManager

# 在您的主視窗初始化時
def init_scene(self):
    self.scene = QGraphicsScene()
    self.edge_manager = SceneEdgeManager(self.scene)
    
    # 初始化路由器
    EnhancedEdgeItem.initialize_router(self.scene.sceneRect())
```

### 2. 替換現有的 EdgeItem

```python
# 原本的程式碼
edge = EdgeItem(src_node, dst_node)

# 改為
edge = EnhancedEdgeItem(src_node, dst_node)
self.edge_manager.add_edge(edge)
```

### 3. 節點移動時更新路由

```python
class TaskNode(QGraphicsRectItem):
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # 更新所有連接的邊線
            for edge in self.edges:
                edge.invalidateRoute()
                edge.updatePath()
        return super().itemChange(change, value)
```

## 進階功能

### 路由風格設定

```python
# 全域設定
router.configure(
    default_style=RoutingStyle.ORTHOGONAL,
    corner_radius=5.0,
    node_padding=10.0,
    enable_smoothing=True
)

# 個別邊線設定
edge.changeRoutingStyle(RoutingStyle.POLYLINE)
```

### 效能優化

```python
# 啟用批次路由
edge_manager.batch_routing_enabled = True

# 調整網格大小（較大的值 = 更快但較不精確）
router = YEdStyleEdgeRouter(scene_rect, grid_size=20.0)

# 啟用路徑快取
router.configure(enable_caching=True)
```

### 處理多重邊線

```python
# 系統會自動處理平行邊線
edge1 = EnhancedEdgeItem(nodeA, nodeB)
edge2 = EnhancedEdgeItem(nodeA, nodeB)
edge3 = EnhancedEdgeItem(nodeB, nodeA)  # 反向邊線

# 邊線會自動分散排列
```

### 動畫效果

```python
# 啟用路由動畫
edge.animator = RoutingAnimator(edge)
edge.animator.animation_duration = 500  # ms

# 當路徑改變時會自動動畫
edge.updatePath()  # 會觸發動畫
```

## 自訂擴展

### 自訂路由策略

```python
class CustomStrategy:
    def get_routing_style(self) -> RoutingStyle:
        return RoutingStyle.ORTHOGONAL
    
    def get_bend_penalty(self) -> float:
        return 10.0

strategy_manager.strategies['custom'] = CustomStrategy()
strategy_manager.set_strategy('custom')
```

### 自訂障礙物

```python
# 添加任意矩形作為障礙物
obstacle_rect = QRectF(100, 100, 50, 50)
router.grid.add_node_obstacle(obstacle_rect, padding=5.0)
```

### 路由事件處理

```python
# 連接信號
router.routing_started.connect(self.on_routing_started)
router.routing_completed.connect(self.on_routing_completed)
router.progress_updated.connect(self.on_progress_updated)

def on_routing_completed(self, result: RoutingResult):
    if result.success:
        print(f"路由成功：長度={result.length:.1f}, 彎曲={result.bends}")
    else:
        print("路由失敗，使用直線")
```

## 效能調校

### 場景大小優化

- **小場景** (<500x500): 使用 grid_size=5
- **中場景** (500-2000): 使用 grid_size=10
- **大場景** (>2000): 使用 grid_size=20

### 節點密度優化

- **稀疏** (<20 節點): 使用 POLYLINE 風格
- **中等** (20-50 節點): 使用 ORTHOGONAL 風格
- **密集** (>50 節點): 考慮分層或分組

### 記憶體優化

```python
# 定期清理快取
router.pathfinder.clear_cache()

# 限制快取大小
if router.pathfinder.get_cache_stats()['cache_size'] > 1000:
    router.pathfinder.clear_cache()
```

## 偵錯與監控

### 效能監控

```python
# 獲取統計資訊
stats = edge_manager.get_statistics()
print(f"總邊數: {stats['total_edges']}")
print(f"平均路由時間: {stats.get('average_time', 0):.2f}ms")
print(f"快取命中率: {stats['hits']}/{stats['hits']+stats['misses']}")
```

### 視覺偵錯

```python
# 顯示網格
def show_grid(scene, grid):
    for y in range(grid.height):
        for x in range(grid.width):
            if grid.is_blocked(GridPoint(x, y)):
                rect = QGraphicsRectItem(
                    x * grid.grid_size,
                    y * grid.grid_size,
                    grid.grid_size,
                    grid.grid_size
                )
                rect.setBrush(QBrush(QColor(255, 0, 0, 50)))
                scene.addItem(rect)
```

## 常見問題

### Q: 邊線穿過節點？
A: 確保在路由前添加所有節點作為障礙物：
```python
for node in nodes:
    router.add_node_obstacle(node.sceneBoundingRect())
```

### Q: 路由太慢？
A: 嘗試：
1. 增加 grid_size
2. 啟用快取
3. 使用批次路由
4. 減少 bend_penalty

### Q: 邊線重疊？
A: 使用平行邊線管理器：
```python
edge_manager.parallel_manager.base_spacing = 10.0  # 增加間距
```

### Q: 動畫不流暢？
A: 調整動畫參數：
```python
animator.animation_steps = 10  # 減少步數
animator.animation_duration = 200  # 縮短時間
```

## 完整範例

```python
class MyGraphWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        
        # 初始化場景
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 1000, 800)
        self.setScene(self.scene)
        
        # 初始化邊線管理器
        self.edge_manager = SceneEdgeManager(self.scene)
        
        # 配置路由器
        self.edge_manager.router.configure(
            default_style=RoutingStyle.ORTHOGONAL,
            corner_radius=5.0,
            node_padding=10.0,
            enable_smoothing=True,
            enable_caching=True
        )
        
        # 創建節點
        self.nodes = {}
        self.create_test_nodes()
        
        # 創建邊線
        self.create_test_edges()
        
    def create_test_nodes(self):
        """創建測試節點"""
        positions = [
            (100, 100), (300, 100), (500, 100),
            (100, 300), (300, 300), (500, 300),
            (100, 500), (300, 500), (500, 500)
        ]
        
        for i, (x, y) in enumerate(positions):
            node = TaskNode(f"Node_{i}")
            node.setPos(x, y)
            self.scene.addItem(node)
            self.nodes[f"Node_{i}"] = node
            
            # 添加為障礙物
            self.edge_manager.router.add_node_obstacle(
                node.sceneBoundingRect()
            )
    
    def create_test_edges(self):
        """創建測試邊線"""
        connections = [
            ("Node_0", "Node_1"),
            ("Node_1", "Node_2"),
            ("Node_0", "Node_3"),
            ("Node_1", "Node_4"),
            ("Node_2", "Node_5"),
            ("Node_3", "Node_6"),
            ("Node_4", "Node_7"),
            ("Node_5", "Node_8"),
            ("Node_4", "Node_8"),  # 對角線
            ("Node_3", "Node_5"),  # 交叉
        ]
        
        for src_id, dst_id in connections:
            src_node = self.nodes[src_id]
            dst_node = self.nodes[dst_id]
            
            edge = EnhancedEdgeItem(src_node, dst_node)
            self.edge_manager.add_edge(edge)
    
    def contextMenuEvent(self, event):
        """右鍵選單"""
        menu = QMenu()
        
        # 路由所有邊線
        route_all = QAction("重新路由所有邊線", self)
        route_all.triggered.connect(self.edge_manager.route_all_edges)
        menu.addAction(route_all)
        
        # 顯示統計
        show_stats = QAction("顯示統計", self)
        show_stats.triggered.connect(self.show_statistics)
        menu.addAction(show_stats)
        
        # 切換網格顯示
        toggle_grid = QAction("切換網格顯示", self)
        toggle_grid.triggered.connect(self.toggle_grid_display)
        menu.addAction(toggle_grid)
        
        menu.exec_(event.globalPos())
    
    def show_statistics(self):
        """顯示統計資訊"""
        stats = self.edge_manager.get_statistics()
        
        from PyQt5.QtWidgets import QMessageBox
        
        msg = QMessageBox()
        msg.setWindowTitle("路由統計")
        msg.setText(
            f"總邊數: {stats['total_edges']}\n"
            f"成功路由: {stats['successful_routes']}\n"
            f"失敗路由: {stats['failed_routes']}\n"
            f"平均彎曲: {stats['average_bends']:.1f}\n"
            f"快取命中: {stats['hits']}\n"
            f"快取未中: {stats['misses']}\n"
            f"效能分數: {stats['performance_score']:.1f}/100"
        )
        msg.exec_()
    
    def toggle_grid_display(self):
        """切換網格顯示"""
        # 實現網格顯示邏輯
        pass
```

## 進階主題

### 1. 自訂路由演算法

```python
class CustomPathfinder(AStarPathfinder):
    """自訂路徑搜尋器"""
    
    def _heuristic_with_tiebreaking(self, current, goal, start):
        """自訂啟發函數"""
        # 使用歐幾里得距離而非曼哈頓距離
        dx = current.x - goal.x
        dy = current.y - goal.y
        euclidean = math.sqrt(dx * dx + dy * dy)
        
        # 添加自訂 tie-breaking
        # 偏好水平/垂直移動
        alignment_bonus = 0
        if current.x == goal.x or current.y == goal.y:
            alignment_bonus = -0.5
        
        return euclidean + alignment_bonus

# 使用自訂路徑搜尋器
router.pathfinder = CustomPathfinder(router.grid)
```

### 2. 路由約束

```python
class ConstrainedRouter(YEdStyleEdgeRouter):
    """帶約束的路由器"""
    
    def __init__(self, scene_rect, grid_size=10.0):
        super().__init__(scene_rect, grid_size)
        self.constraints = []
    
    def add_constraint(self, constraint):
        """添加路由約束"""
        self.constraints.append(constraint)
    
    def route_edge(self, source_rect, target_rect, **kwargs):
        """考慮約束的路由"""
        # 檢查約束
        for constraint in self.constraints:
            if not constraint.is_satisfied(source_rect, target_rect):
                # 調整路由參數
                kwargs['routing_style'] = constraint.get_alternative_style()
        
        return super().route_edge(source_rect, target_rect, **kwargs)

class MinimumDistanceConstraint:
    """最小距離約束"""
    def __init__(self, min_distance=50):
        self.min_distance = min_distance
    
    def is_satisfied(self, src_rect, dst_rect):
        distance = math.sqrt(
            (src_rect.center().x() - dst_rect.center().x()) ** 2 +
            (src_rect.center().y() - dst_rect.center().y()) ** 2
        )
        return distance >= self.min_distance
    
    def get_alternative_style(self):
        return RoutingStyle.STRAIGHT
```

### 3. 互動式路由編輯

```python
class InteractiveEdgeItem(EnhancedEdgeItem):
    """支援互動編輯的邊線"""
    
    def __init__(self, src, dst):
        super().__init__(src, dst)
        self.control_points = []
        self.editing_mode = False
    
    def enable_editing(self):
        """啟用編輯模式"""
        self.editing_mode = True
        self._create_control_points()
    
    def _create_control_points(self):
        """創建控制點"""
        if self._routing_result and self._routing_result.segments:
            for i, segment in enumerate(self._routing_result.segments):
                if i > 0:  # 在轉角處創建控制點
                    control = ControlPointItem(segment.start, self)
                    self.control_points.append(control)
    
    def update_from_control_points(self):
        """根據控制點更新路徑"""
        if not self.control_points:
            return
        
        path = QPainterPath()
        path.moveTo(self.src.sceneBoundingRect().center())
        
        for control in self.control_points:
            path.lineTo(control.pos())
        
        path.lineTo(self.dst.sceneBoundingRect().center())
        self.setPath(path)

class ControlPointItem(QGraphicsEllipseItem):
    """路徑控制點"""
    
    def __init__(self, pos, edge_item):
        super().__init__(-5, -5, 10, 10)
        self.edge_item = edge_item
        self.setPos(pos)
        
        self.setBrush(QBrush(Qt.blue))
        self.setPen(QPen(Qt.darkBlue, 2))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10)
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.edge_item.update_from_control_points()
        return super().itemChange(change, value)
```

### 4. 路由群組

```python
class EdgeGroup:
    """邊線群組 - 管理相關邊線"""
    
    def __init__(self, name):
        self.name = name
        self.edges = []
        self.color = QColor(Qt.black)
        self.style = RoutingStyle.ORTHOGONAL
    
    def add_edge(self, edge):
        """添加邊線到群組"""
        self.edges.append(edge)
        self._apply_group_style(edge)
    
    def _apply_group_style(self, edge):
        """應用群組樣式"""
        pen = QPen(self.color, 2)
        edge.setPen(pen)
        edge.changeRoutingStyle(self.style)
    
    def set_color(self, color):
        """設定群組顏色"""
        self.color = color
        for edge in self.edges:
            pen = QPen(self.color, 2)
            edge.setPen(pen)
    
    def route_all(self):
        """路由群組中的所有邊線"""
        for edge in self.edges:
            edge.updatePath()

class EdgeGroupManager:
    """邊線群組管理器"""
    
    def __init__(self):
        self.groups = {}
    
    def create_group(self, name):
        """創建群組"""
        if name not in self.groups:
            self.groups[name] = EdgeGroup(name)
        return self.groups[name]
    
    def assign_edge_to_group(self, edge, group_name):
        """將邊線分配到群組"""
        if group_name in self.groups:
            self.groups[group_name].add_edge(edge)
    
    def color_by_groups(self, color_map):
        """根據群組著色"""
        for group_name, color in color_map.items():
            if group_name in self.groups:
                self.groups[group_name].set_color(color)
```

### 5. 匯出和匯入路由

```python
class RoutingSerializer:
    """路由序列化器"""
    
    @staticmethod
    def export_routing(edge_item):
        """匯出路由資料"""
        if not edge_item._routing_result:
            return None
        
        data = {
            'source_id': edge_item.src.taskId if hasattr(edge_item.src, 'taskId') else '',
            'target_id': edge_item.dst.taskId if hasattr(edge_item.dst, 'taskId') else '',
            'style': edge_item._routing_style.value if hasattr(edge_item, '_routing_style') else 'orthogonal',
            'path_points': [],
            'bends': edge_item._routing_result.bends,
            'length': edge_item._routing_result.length
        }
        
        # 匯出路徑點
        path = edge_item.path()
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            data['path_points'].append({
                'x': element.x,
                'y': element.y,
                'type': 'move' if i == 0 else 'line'
            })
        
        return data
    
    @staticmethod
    def import_routing(edge_item, data):
        """匯入路由資料"""
        if not data or 'path_points' not in data:
            return False
        
        # 重建路徑
        path = QPainterPath()
        for i, point in enumerate(data['path_points']):
            if point['type'] == 'move':
                path.moveTo(point['x'], point['y'])
            else:
                path.lineTo(point['x'], point['y'])
        
        edge_item.setPath(path)
        return True
    
    @staticmethod
    def export_all_edges(edge_manager):
        """匯出所有邊線"""
        data = {
            'version': '1.0',
            'timestamp': time.time(),
            'edges': []
        }
        
        for edge in edge_manager.edges:
            edge_data = RoutingSerializer.export_routing(edge)
            if edge_data:
                data['edges'].append(edge_data)
        
        return json.dumps(data, indent=2)
    
    @staticmethod
    def import_all_edges(edge_manager, json_data):
        """匯入所有邊線"""
        data = json.loads(json_data)
        
        success_count = 0
        for edge_data in data.get('edges', []):
            # 尋找對應的邊線
            for edge in edge_manager.edges:
                if (hasattr(edge.src, 'taskId') and 
                    hasattr(edge.dst, 'taskId') and
                    edge.src.taskId == edge_data['source_id'] and
                    edge.dst.taskId == edge_data['target_id']):
                    
                    if RoutingSerializer.import_routing(edge, edge_data):
                        success_count += 1
                    break
        
        return success_count
```

## 疑難排解

### 問題：路由計算超時
**解決方案：**
```python
# 設定超時限制
router.config['max_computation_time'] = 200  # ms

# 使用簡化的路由
router.config['default_style'] = RoutingStyle.STRAIGHT
```

### 問題：記憶體使用過高
**解決方案：**
```python
# 定期清理
def cleanup_routing_cache():
    router.pathfinder.clear_cache()
    router.grid.quadtree = QuadTree(scene_rect)
    
# 每 100 次路由後清理
if router.stats['total_routes'] % 100 == 0:
    cleanup_routing_cache()
```

### 問題：邊線抖動
**解決方案：**
```python
# 使用去抖動
class DebouncedEdgeItem(EnhancedEdgeItem):
    def __init__(self, src, dst):
        super().__init__(src, dst)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._do_update)
        self.update_timer.setSingleShot(True)
    
    def updatePath(self):
        # 延遲更新
        self.update_timer.stop()
        self.update_timer.start(100)  # 100ms 延遲
    
    def _do_update(self):
        super().updatePath()
```
        