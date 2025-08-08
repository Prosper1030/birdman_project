#!/usr/bin/env python3
"""
yEd 風格 Edge Routing 系統 - 完整實現
支援正交路由、智慧避障、多邊線分散
"""

# [前面的代碼保持不變，從這裡繼續...]

# ===================== 事件處理與互動 =====================

class EdgeInteractionHandler:
    """邊線互動處理器"""
    
    def __init__(self, edge_item: 'EnhancedEdgeItem'):
        self.edge_item = edge_item
        self.is_hovering = False
        self.is_selected = False
        
    def on_hover_enter(self):
        """滑鼠進入事件"""
        self.is_hovering = True
        self.edge_item.setPen(self.edge_item.hoverPen)
        
    def on_hover_leave(self):
        """滑鼠離開事件"""
        self.is_hovering = False
        if not self.is_selected:
            self.edge_item.setPen(self.edge_item.normalPen)
            
    def on_selection_changed(self, selected: bool):
        """選擇狀態變更"""
        self.is_selected = selected
        if selected:
            self.edge_item.setPen(self.edge_item.selectedPen)
        elif not self.is_hovering:
            self.edge_item.setPen(self.edge_item.normalPen)


# ===================== 路由動畫系統 =====================

class RoutingAnimator(QObject):
    """路由動畫控制器 - 提供平滑的路由轉換效果"""
    
    animation_finished = pyqtSignal()
    
    def __init__(self, edge_item: 'EnhancedEdgeItem'):
        super().__init__()
        self.edge_item = edge_item
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_step)
        
        # 動畫參數
        self.start_path: Optional[QPainterPath] = None
        self.end_path: Optional[QPainterPath] = None
        self.current_progress = 0.0
        self.animation_duration = 300  # ms
        self.animation_steps = 20
        self.step_duration = self.animation_duration / self.animation_steps
        
    def animate_to_path(self, new_path: QPainterPath):
        """動畫過渡到新路徑"""
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            
        self.start_path = QPainterPath(self.edge_item.path())
        self.end_path = new_path
        self.current_progress = 0.0
        
        self.animation_timer.setInterval(int(self.step_duration))
        self.animation_timer.start()
        
    def _animate_step(self):
        """動畫步進"""
        self.current_progress += 1.0 / self.animation_steps
        
        if self.current_progress >= 1.0:
            self.edge_item.setPath(self.end_path)
            self.animation_timer.stop()
            self.animation_finished.emit()
        else:
            # 使用緩動函數
            t = self._ease_in_out_cubic(self.current_progress)
            interpolated_path = self._interpolate_paths(
                self.start_path, self.end_path, t
            )
            self.edge_item.setPath(interpolated_path)
            
    def _ease_in_out_cubic(self, t: float) -> float:
        """緩動函數 - Cubic ease-in-out"""
        if t < 0.5:
            return 4 * t * t * t
        p = 2 * t - 2
        return 1 + p * p * p / 2
        
    def _interpolate_paths(
        self, 
        path1: QPainterPath, 
        path2: QPainterPath, 
        t: float
    ) -> QPainterPath:
        """路徑插值"""
        # 簡化版本：線性插值關鍵點
        result = QPainterPath()
        
        # 獲取路徑的多邊形近似
        poly1 = path1.toSubpathPolygons()
        poly2 = path2.toSubpathPolygons()
        
        if poly1 and poly2 and len(poly1[0]) == len(poly2[0]):
            points = []
            for i in range(len(poly1[0])):
                p1 = poly1[0][i]
                p2 = poly2[0][i]
                
                # 線性插值
                x = p1.x() * (1 - t) + p2.x() * t
                y = p1.y() * (1 - t) + p2.y() * t
                points.append(QPointF(x, y))
                
            if points:
                result.moveTo(points[0])
                for p in points[1:]:
                    result.lineTo(p)
        else:
            # 後備：直接使用目標路徑
            return QPainterPath(path2)
            
        return result


# ===================== 路由策略管理器 =====================

class RoutingStrategyManager:
    """路由策略管理器 - 根據場景選擇最佳路由策略"""
    
    def __init__(self):
        self.strategies = {
            'dense': self.DenseLayoutStrategy(),
            'sparse': self.SparseLayoutStrategy(),
            'hierarchical': self.HierarchicalLayoutStrategy(),
            'circular': self.CircularLayoutStrategy()
        }
        self.current_strategy = 'dense'
        
    class DenseLayoutStrategy:
        """密集佈局策略"""
        def get_routing_style(self) -> RoutingStyle:
            return RoutingStyle.ORTHOGONAL
            
        def get_grid_size(self) -> float:
            return 5.0  # 更細的網格
            
        def get_bend_penalty(self) -> float:
            return 8.0  # 更高的彎曲懲罰
            
    class SparseLayoutStrategy:
        """稀疏佈局策略"""
        def get_routing_style(self) -> RoutingStyle:
            return RoutingStyle.POLYLINE
            
        def get_grid_size(self) -> float:
            return 15.0  # 較粗的網格
            
        def get_bend_penalty(self) -> float:
            return 3.0  # 較低的彎曲懲罰
            
    class HierarchicalLayoutStrategy:
        """層次佈局策略"""
        def get_routing_style(self) -> RoutingStyle:
            return RoutingStyle.ORTHOGONAL
            
        def get_grid_size(self) -> float:
            return 10.0
            
        def get_bend_penalty(self) -> float:
            return 5.0
            
    class CircularLayoutStrategy:
        """環形佈局策略"""
        def get_routing_style(self) -> RoutingStyle:
            return RoutingStyle.CURVED
            
        def get_grid_size(self) -> float:
            return 10.0
            
        def get_bend_penalty(self) -> float:
            return 2.0
            
    def analyze_layout(self, nodes: List['TaskNode']) -> str:
        """分析佈局類型"""
        if not nodes:
            return 'sparse'
            
        # 計算節點密度
        total_area = 0
        for node in nodes:
            rect = node.sceneBoundingRect()
            total_area += rect.width() * rect.height()
            
        scene_rect = nodes[0].scene().sceneRect()
        scene_area = scene_rect.width() * scene_rect.height()
        
        density = total_area / scene_area if scene_area > 0 else 0
        
        # 檢查是否為層次結構
        if self._is_hierarchical(nodes):
            return 'hierarchical'
            
        # 檢查是否為環形結構
        if self._is_circular(nodes):
            return 'circular'
            
        # 基於密度選擇
        if density > 0.3:
            return 'dense'
        else:
            return 'sparse'
            
    def _is_hierarchical(self, nodes: List['TaskNode']) -> bool:
        """檢查是否為層次佈局"""
        # 簡化檢查：Y座標是否呈現層次分佈
        y_positions = [node.pos().y() for node in nodes]
        y_positions.sort()
        
        if len(y_positions) < 3:
            return False
            
        # 檢查是否有明顯的層次間距
        gaps = []
        for i in range(1, len(y_positions)):
            gaps.append(y_positions[i] - y_positions[i-1])
            
        avg_gap = sum(gaps) / len(gaps)
        large_gaps = [g for g in gaps if g > avg_gap * 2]
        
        return len(large_gaps) >= 2
        
    def _is_circular(self, nodes: List['TaskNode']) -> bool:
        """檢查是否為環形佈局"""
        if len(nodes) < 4:
            return False
            
        # 計算中心點
        center_x = sum(n.pos().x() for n in nodes) / len(nodes)
        center_y = sum(n.pos().y() for n in nodes) / len(nodes)
        center = QPointF(center_x, center_y)
        
        # 計算到中心的距離
        distances = []
        for node in nodes:
            dx = node.pos().x() - center.x()
            dy = node.pos().y() - center.y()
            distances.append(math.sqrt(dx * dx + dy * dy))
            
        # 檢查距離的一致性
        avg_dist = sum(distances) / len(distances)
        variance = sum((d - avg_dist) ** 2 for d in distances) / len(distances)
        std_dev = math.sqrt(variance)
        
        # 如果標準差較小，可能是環形佈局
        return std_dev / avg_dist < 0.3 if avg_dist > 0 else False
        
    def get_current_strategy(self):
        """獲取當前策略"""
        return self.strategies[self.current_strategy]
        
    def set_strategy(self, strategy_name: str):
        """設定策略"""
        if strategy_name in self.strategies:
            self.current_strategy = strategy_name


# ===================== 效能監控器 =====================

class PerformanceMonitor:
    """效能監控器 - 追蹤和優化路由效能"""
    
    def __init__(self):
        self.metrics = {
            'routing_times': [],
            'path_lengths': [],
            'bend_counts': [],
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_routes': 0
        }
        self.performance_threshold = 100  # ms
        
    def record_routing(self, result: RoutingResult):
        """記錄路由結果"""
        self.metrics['routing_times'].append(result.computation_time * 1000)
        self.metrics['path_lengths'].append(result.length)
        self.metrics['bend_counts'].append(result.bends)
        
        if not result.success:
            self.metrics['failed_routes'] += 1
            
    def get_average_time(self) -> float:
        """獲取平均路由時間"""
        times = self.metrics['routing_times']
        return sum(times) / len(times) if times else 0
        
    def get_performance_score(self) -> float:
        """計算效能分數 (0-100)"""
        if not self.metrics['routing_times']:
            return 100
            
        avg_time = self.get_average_time()
        cache_ratio = (self.metrics['cache_hits'] / 
                      (self.metrics['cache_hits'] + self.metrics['cache_misses'] + 1))
        failure_rate = (self.metrics['failed_routes'] / 
                       len(self.metrics['routing_times']))
        
        # 計算分數
        time_score = max(0, 100 - (avg_time / self.performance_threshold) * 50)
        cache_score = cache_ratio * 30
        success_score = (1 - failure_rate) * 20
        
        return time_score + cache_score + success_score
        
    def suggest_optimizations(self) -> List[str]:
        """建議優化措施"""
        suggestions = []
        
        avg_time = self.get_average_time()
        if avg_time > self.performance_threshold:
            suggestions.append("考慮增加網格大小以提升效能")
            suggestions.append("啟用路徑快取")
            
        if self.metrics['failed_routes'] > len(self.metrics['routing_times']) * 0.1:
            suggestions.append("調整節點間距以減少路由失敗")
            
        avg_bends = (sum(self.metrics['bend_counts']) / 
                    len(self.metrics['bend_counts']) if self.metrics['bend_counts'] else 0)
        if avg_bends > 5:
            suggestions.append("考慮使用更簡單的路由風格")
            
        return suggestions


# ===================== 完整的 EnhancedEdgeItem (續) =====================

class EnhancedEdgeItem(QGraphicsPathItem):
    """增強的 EdgeItem - 整合所有功能"""
    
    # [前面的代碼保持不變...]
    
    def hoverEnterEvent(self, event):
        """滑鼠進入事件"""
        super().hoverEnterEvent(event)
        if hasattr(self, 'interaction_handler'):
            self.interaction_handler.on_hover_enter()
            
    def hoverLeaveEvent(self, event):
        """滑鼠離開事件"""
        super().hoverLeaveEvent(event)
        if hasattr(self, 'interaction_handler'):
            self.interaction_handler.on_hover_leave()
            
    def itemChange(self, change, value):
        """項目變更事件"""
        if change == QGraphicsItem.ItemSelectedChange:
            if hasattr(self, 'interaction_handler'):
                self.interaction_handler.on_selection_changed(value)
        return super().itemChange(change, value)
        
    def contextMenuEvent(self, event):
        """右鍵選單"""
        from PyQt5.QtWidgets import QMenu, QAction
        
        menu = QMenu()
        
        # 路由風格選項
        style_menu = menu.addMenu("路由風格")
        
        orthogonal_action = QAction("正交路由", menu)
        orthogonal_action.triggered.connect(
            lambda: self.changeRoutingStyle(RoutingStyle.ORTHOGONAL)
        )
        style_menu.addAction(orthogonal_action)
        
        polyline_action = QAction("多邊形路由", menu)
        polyline_action.triggered.connect(
            lambda: self.changeRoutingStyle(RoutingStyle.POLYLINE)
        )
        style_menu.addAction(polyline_action)
        
        straight_action = QAction("直線", menu)
        straight_action.triggered.connect(
            lambda: self.changeRoutingStyle(RoutingStyle.STRAIGHT)
        )
        style_menu.addAction(straight_action)
        
        menu.addSeparator()
        
        # 重新路由
        reroute_action = QAction("重新路由", menu)
        reroute_action.triggered.connect(self.forceReroute)
        menu.addAction(reroute_action)
        
        # 顯示統計
        if self._routing_result:
            menu.addSeparator()
            info_action = QAction(
                f"長度: {self._routing_result.length:.1f}, "
                f"彎曲: {self._routing_result.bends}", 
                menu
            )
            info_action.setEnabled(False)
            menu.addAction(info_action)
            
        menu.exec_(event.screenPos())
        
    def changeRoutingStyle(self, style: RoutingStyle):
        """改變路由風格"""
        self._routing_style = style
        self.forceReroute()
        
    def forceReroute(self):
        """強制重新路由"""
        self.invalidateRoute()
        self.updatePath()
        
    def setHighlight(self, highlight: bool):
        """設定高亮狀態"""
        if highlight:
            pen = QPen(Qt.yellow, 4, Qt.SolidLine)
            self.setPen(pen)
        else:
            self.setPen(self.normalPen)


# ===================== 場景管理器整合 =====================

class SceneEdgeManager:
    """場景級邊線管理器 - 管理所有邊線的路由"""
    
    def __init__(self, scene):
        self.scene = scene
        self.edges: List[EnhancedEdgeItem] = []
        self.router = YEdStyleEdgeRouter(scene.sceneRect())
        self.strategy_manager = RoutingStrategyManager()
        self.performance_monitor = PerformanceMonitor()
        
        # 批次路由控制
        self.batch_routing_enabled = True
        self.routing_queue = deque()
        
        # 初始化 EnhancedEdgeItem 的類別路由器
        EnhancedEdgeItem.initialize_router(scene.sceneRect())
        
    def add_edge(self, edge: EnhancedEdgeItem):
        """添加邊線"""
        self.edges.append(edge)
        self.scene.addItem(edge)
        
    def remove_edge(self, edge: EnhancedEdgeItem):
        """移除邊線"""
        if edge in self.edges:
            self.edges.remove(edge)
            self.scene.removeItem(edge)
            
    def route_all_edges(self):
        """路由所有邊線"""
        # 分析佈局
        nodes = self._get_all_nodes()
        layout_type = self.strategy_manager.analyze_layout(nodes)
        self.strategy_manager.set_strategy(layout_type)
        
        # 清除並重建障礙物
        self.router.clear_all()
        for node in nodes:
            self.router.add_node_obstacle(node.sceneBoundingRect())
            
        # 批次路由
        start_time = time.time()
        
        for edge in self.edges:
            edge.updatePath()
            
        total_time = time.time() - start_time
        print(f"路由 {len(self.edges)} 條邊線耗時: {total_time*1000:.2f}ms")
        
        # 更新效能統計
        score = self.performance_monitor.get_performance_score()
        print(f"效能分數: {score:.1f}/100")
        
        suggestions = self.performance_monitor.suggest_optimizations()
        if suggestions:
            print("優化建議:")
            for s in suggestions:
                print(f"  - {s}")
                
    def _get_all_nodes(self) -> List['TaskNode']:
        """獲取所有節點"""
        nodes = []
        for item in self.scene.items():
            if hasattr(item, 'taskId'):  # 假設節點有 taskId 屬性
                nodes.append(item)
        return nodes
        
    def highlight_path(self, src_id: str, dst_id: str):
        """高亮指定路徑"""
        for edge in self.edges:
            if (edge.src.taskId == src_id and edge.dst.taskId == dst_id):
                edge.setHighlight(True)
            else:
                edge.setHighlight(False)
                
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        stats = self.router.get_statistics()
        stats['total_edges'] = len(self.edges)
        stats['performance_score'] = self.performance_monitor.get_performance_score()
        return stats


# ===================== 使用範例 =====================

def example_usage():
    """使用範例"""
    from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsView
    
    app = QApplication([])
    
    # 創建場景
    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 1000, 800)
    
    # 創建邊線管理器
    edge_manager = SceneEdgeManager(scene)
    
    # 創建一些測試節點（需要實際的 TaskNode 類）
    # nodes = create_test_nodes()
    
    # 創建邊線
    # edge = EnhancedEdgeItem(nodes[0], nodes[1])
    # edge_manager.add_edge(edge)
    
    # 執行路由
    # edge_manager.route_all_edges()
    
    # 創建視圖
    view = QGraphicsView(scene)
    view.show()
    
    app.exec_()


if __name__ == "__main__":
    print("yEd 風格 Edge Routing 系統載入完成")
    print("主要功能:")
    print("  - 正交路由 (Orthogonal Routing)")
    print("  - 智慧避障 (Obstacle Avoidance)")
    print("  - 多邊線分散 (Parallel Edge Handling)")
    print("  - 路徑優化 (Path Optimization)")
    print("  - 效能監控 (Performance Monitoring)")
    print("  - 動畫支援 (Animation Support)")
