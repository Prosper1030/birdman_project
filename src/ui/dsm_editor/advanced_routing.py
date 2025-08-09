"""
Advanced Edge Routing Engine for DSM Editor
Based on research: yEd's orthogonal visibility graphs with A* pathfinding

Implements:
1. Orthogonal Visibility Graph construction
2. A* pathfinding with Manhattan routing
3. Multi-edge handling and collision avoidance
4. Real-time performance optimizations
"""

import math
import heapq
from typing import List, Tuple, Dict, Set, Optional, NamedTuple
from dataclasses import dataclass
from PyQt5.QtCore import QPointF, QRectF, QTimer
from PyQt5.QtGui import QPainterPath
import time


@dataclass
class RoutingNode:
    """路由圖中的節點"""
    x: float
    y: float
    node_id: str = ""
    node_type: str = "waypoint"  # "source", "target", "waypoint", "obstacle"
    
    def __hash__(self):
        return hash((self.x, self.y, self.node_id))
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


@dataclass 
class RoutingEdge:
    """路由圖中的邊"""
    start: RoutingNode
    end: RoutingNode
    cost: float
    edge_type: str = "orthogonal"  # "orthogonal", "diagonal"


class VisibilityGraph:
    """正交可見性圖 - yEd 核心演算法"""
    
    def __init__(self):
        self.nodes: Set[RoutingNode] = set()
        self.edges: List[RoutingEdge] = []
        self.obstacles: List[QRectF] = []
        
    def add_obstacle(self, rect: QRectF, obstacle_id: str = ""):
        """添加障礙物 (節點邊界框)"""
        self.obstacles.append(rect)
        
        # 為每個障礙物創建 8 個連接點 (corners + midpoints)
        corners_and_midpoints = [
            RoutingNode(rect.left(), rect.top(), f"{obstacle_id}_tl"),
            RoutingNode(rect.right(), rect.top(), f"{obstacle_id}_tr"), 
            RoutingNode(rect.right(), rect.bottom(), f"{obstacle_id}_br"),
            RoutingNode(rect.left(), rect.bottom(), f"{obstacle_id}_bl"),
            RoutingNode(rect.center().x(), rect.top(), f"{obstacle_id}_tm"),
            RoutingNode(rect.right(), rect.center().y(), f"{obstacle_id}_rm"),
            RoutingNode(rect.center().x(), rect.bottom(), f"{obstacle_id}_bm"),
            RoutingNode(rect.left(), rect.center().y(), f"{obstacle_id}_lm"),
        ]
        
        self.nodes.update(corners_and_midpoints)
    
    def build_visibility_edges(self):
        """構建正交可見性邊 - 基於 opus 研究的方法"""
        self.edges.clear()
        nodes_list = list(self.nodes)
        
        for i, node1 in enumerate(nodes_list):
            for node2 in nodes_list[i+1:]:
                # 只考慮正交方向的連接 (Manhattan routing)
                if self._is_orthogonal(node1, node2):
                    if self._is_visible(node1, node2):
                        cost = self._calculate_cost(node1, node2)
                        self.edges.append(RoutingEdge(node1, node2, cost))
                        self.edges.append(RoutingEdge(node2, node1, cost))
    
    def _is_orthogonal(self, node1: RoutingNode, node2: RoutingNode) -> bool:
        """檢查兩節點是否在正交方向上"""
        return node1.x == node2.x or node1.y == node2.y
    
    def _is_visible(self, node1: RoutingNode, node2: RoutingNode) -> bool:
        """檢查兩節點間是否可見 (無障礙物阻擋)"""
        line_rect = QRectF(
            min(node1.x, node2.x), min(node1.y, node2.y),
            abs(node2.x - node1.x), abs(node2.y - node1.y)
        )
        
        # 擴大線條為細長矩形進行碰撞檢測
        if line_rect.width() == 0:
            line_rect.setWidth(2)  # 垂直線
        if line_rect.height() == 0:
            line_rect.setHeight(2)  # 水平線
            
        for obstacle in self.obstacles:
            if obstacle.intersects(line_rect):
                # 精確檢查是否真的被障礙物內部阻擋
                if self._line_intersects_rect_interior(node1, node2, obstacle):
                    return False
        
        return True
    
    def _line_intersects_rect_interior(self, node1: RoutingNode, node2: RoutingNode, rect: QRectF) -> bool:
        """檢查線段是否穿越矩形內部"""
        # 簡化實現：檢查線段中點是否在矩形內部
        mid_x = (node1.x + node2.x) / 2
        mid_y = (node1.y + node2.y) / 2
        return rect.contains(mid_x, mid_y)
    
    def _calculate_cost(self, node1: RoutingNode, node2: RoutingNode) -> float:
        """計算邊的成本 - Manhattan 距離"""
        return abs(node2.x - node1.x) + abs(node2.y - node1.y)


class AStarPathfinder:
    """A* 路徑搜尋 - 基於 opus 研究的增強啟發式"""
    
    def __init__(self, visibility_graph: VisibilityGraph):
        self.graph = visibility_graph
        self.adjacency: Dict[RoutingNode, List[RoutingEdge]] = {}
        self._build_adjacency_list()
    
    def _build_adjacency_list(self):
        """構建鄰接表以提升性能"""
        self.adjacency.clear()
        for edge in self.graph.edges:
            if edge.start not in self.adjacency:
                self.adjacency[edge.start] = []
            self.adjacency[edge.start].append(edge)
    
    def find_path(self, start: RoutingNode, goal: RoutingNode) -> List[RoutingNode]:
        """使用 A* 尋找最短路徑 - 包含 opus 研究的 tie-breaking"""
        
        # Priority queue: (f_cost, g_cost, node)
        open_set = [(0, 0, start)]
        came_from: Dict[RoutingNode, RoutingNode] = {}
        g_cost: Dict[RoutingNode, float] = {start: 0}
        f_cost: Dict[RoutingNode, float] = {start: self._enhanced_heuristic(start, goal, start)}
        
        closed_set: Set[RoutingNode] = set()
        
        while open_set:
            current_f, current_g, current = heapq.heappop(open_set)
            
            if current == goal:
                return self._reconstruct_path(came_from, current)
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            # 探索鄰居
            if current in self.adjacency:
                for edge in self.adjacency[current]:
                    neighbor = edge.end
                    tentative_g = g_cost[current] + edge.cost
                    
                    if neighbor in closed_set:
                        continue
                    
                    if neighbor not in g_cost or tentative_g < g_cost[neighbor]:
                        came_from[neighbor] = current
                        g_cost[neighbor] = tentative_g
                        f_cost[neighbor] = tentative_g + self._enhanced_heuristic(neighbor, goal, start)
                        heapq.heappush(open_set, (f_cost[neighbor], tentative_g, neighbor))
        
        return []  # 無路徑
    
    def _enhanced_heuristic(self, node: RoutingNode, goal: RoutingNode, start: RoutingNode) -> float:
        """增強啟發式函數 - 實現 opus 研究中的 tie-breaking"""
        # 基礎 Manhattan 距離
        base_distance = abs(node.x - goal.x) + abs(node.y - goal.y)
        
        # Tie-breaking for straighter paths (from opus research)
        dx1, dy1 = node.x - goal.x, node.y - goal.y
        dx2, dy2 = start.x - goal.x, start.y - goal.y
        cross = abs(dx1 * dy2 - dx2 * dy1)
        
        # 轉彎懲罰 - 鼓勵較少的方向改變
        bend_penalty = 0
        if hasattr(node, 'direction'):
            # 如果有方向資訊，對轉彎施加懲罰
            bend_penalty = 2.0
        
        return base_distance + cross * 0.001 + bend_penalty
    
    def _reconstruct_path(self, came_from: Dict[RoutingNode, RoutingNode], current: RoutingNode) -> List[RoutingNode]:
        """重建路徑"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return path[::-1]


class EdgeRoutingEngine:
    """邊線路由引擎主類別 - 整合 yEd 風格路由"""
    
    def __init__(self):
        self.visibility_graph = VisibilityGraph()
        self.pathfinder = AStarPathfinder(self.visibility_graph)
        self.minimum_edge_distance = 8  # 最小邊線間距
        self.optimization_enabled = True
        
        # 性能優化 - 延遲重計算
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._delayed_update)
        self.pending_update = False
    
    def set_obstacles(self, node_rects: List[Tuple[QRectF, str]]):
        """設定障礙物 (節點邊界框)"""
        self.visibility_graph.nodes.clear()
        self.visibility_graph.edges.clear()
        self.visibility_graph.obstacles.clear()
        
        for rect, node_id in node_rects:
            # 擴大障礙物邊界，為邊線預留空間
            expanded_rect = rect.adjusted(-self.minimum_edge_distance, -self.minimum_edge_distance, 
                                        self.minimum_edge_distance, self.minimum_edge_distance)
            self.visibility_graph.add_obstacle(expanded_rect, node_id)
        
        self.visibility_graph.build_visibility_edges()
        self.pathfinder._build_adjacency_list()
    
    def route_edge(self, start_pos: QPointF, end_pos: QPointF) -> QPainterPath:
        """路由單條邊線 - 返回 QPainterPath"""
        start_node = RoutingNode(start_pos.x(), start_pos.y(), "source")
        end_node = RoutingNode(end_pos.x(), end_pos.y(), "target")
        
        # 添加起點和終點到圖中
        self.visibility_graph.nodes.add(start_node)
        self.visibility_graph.nodes.add(end_node)
        
        # 為起點和終點建立連接
        self._connect_endpoints(start_node, end_node)
        
        # 尋找路徑
        path_nodes = self.pathfinder.find_path(start_node, end_node)
        
        # 清理臨時節點
        self.visibility_graph.nodes.discard(start_node)
        self.visibility_graph.nodes.discard(end_node)
        
        if not path_nodes:
            # 回退到直線連接
            return self._create_direct_path(start_pos, end_pos)
        
        return self._create_orthogonal_path(path_nodes)
    
    def _connect_endpoints(self, start: RoutingNode, end: RoutingNode):
        """為起點和終點建立可見性連接"""
        all_nodes = list(self.visibility_graph.nodes)
        
        for node in all_nodes:
            # 連接起點
            if self.visibility_graph._is_orthogonal(start, node) and \
               self.visibility_graph._is_visible(start, node):
                cost = self.visibility_graph._calculate_cost(start, node)
                self.visibility_graph.edges.extend([
                    RoutingEdge(start, node, cost),
                    RoutingEdge(node, start, cost)
                ])
            
            # 連接終點
            if self.visibility_graph._is_orthogonal(end, node) and \
               self.visibility_graph._is_visible(end, node):
                cost = self.visibility_graph._calculate_cost(end, node)
                self.visibility_graph.edges.extend([
                    RoutingEdge(end, node, cost),
                    RoutingEdge(node, end, cost)
                ])
        
        # 更新鄰接表
        self.pathfinder._build_adjacency_list()
    
    def _create_orthogonal_path(self, path_nodes: List[RoutingNode]) -> QPainterPath:
        """創建正交路徑 - Manhattan routing"""
        if len(path_nodes) < 2:
            return QPainterPath()
        
        path = QPainterPath()
        path.moveTo(path_nodes[0].x, path_nodes[0].y)
        
        for node in path_nodes[1:]:
            path.lineTo(node.x, node.y)
        
        return path
    
    def _create_direct_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        """創建直線路徑 - 回退方案"""
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)
        return path
    
    def request_update(self):
        """請求延遲更新 - 性能優化"""
        if not self.pending_update:
            self.pending_update = True
            self.update_timer.start(200)  # 200ms 延遲
    
    def _delayed_update(self):
        """延遲更新執行"""
        self.pending_update = False
        # 這裡可以觸發重新路由所有邊線的信號
        
    def get_performance_stats(self) -> Dict[str, float]:
        """獲取性能統計資訊"""
        return {
            "nodes": len(self.visibility_graph.nodes),
            "edges": len(self.visibility_graph.edges),
            "obstacles": len(self.visibility_graph.obstacles)
        }


# 測試和示例使用
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
    from PyQt5.QtCore import QRectF
    
    app = QApplication(sys.argv)
    
    # 創建路由引擎測試
    router = EdgeRoutingEngine()
    
    # 設定測試障礙物
    obstacles = [
        (QRectF(100, 100, 80, 60), "node1"),
        (QRectF(250, 200, 80, 60), "node2"),
        (QRectF(150, 300, 80, 60), "node3"),
    ]
    
    router.set_obstacles(obstacles)
    
    # 測試路由
    start_time = time.time()
    routed_path = router.route_edge(QPointF(50, 50), QPointF(400, 400))
    end_time = time.time()
    
    print(f"路由計算時間: {(end_time - start_time) * 1000:.2f}ms")
    print(f"性能統計: {router.get_performance_stats()}")
    
    sys.exit()


class AdvancedEdgeRouter:
    """
    高級邊線路由器 - 整合 yEd 風格的正交路由功能
    
    提供完整的正交路由接口，整合可見性圖和 A* 路徑搜尋，
    為 EdgeRouterManager 提供高級路由能力。
    """
    
    def __init__(self):
        """初始化高級路由器"""
        self.routing_engine = EdgeRoutingEngine()
        self.cache_enabled = True
        self.routing_cache = {}
        
    def route_edge(self, start_pos, end_pos, obstacles=None):
        """
        路由單條邊線 - 主要接口
        
        Args:
            start_pos: 起始位置 (QPointF)
            end_pos: 結束位置 (QPointF) 
            obstacles: 障礙物列表 (List[QRectF])
            
        Returns:
            路徑點列表 [QPointF, ...]
        """
        from PyQt5.QtCore import QPointF
        
        # 快取檢查
        cache_key = None
        if self.cache_enabled:
            cache_key = self._create_cache_key(start_pos, end_pos, obstacles)
            if cache_key in self.routing_cache:
                cached_path = self.routing_cache[cache_key]
                return [QPointF(x, y) for x, y in cached_path]
        
        try:
            # 設置障礙物
            if obstacles:
                obstacle_data = [(rect, f"obstacle_{i}") for i, rect in enumerate(obstacles)]
                self.routing_engine.set_obstacles(obstacle_data)
            
            # 執行路由
            path = self.routing_engine.route_edge(start_pos, end_pos)
            
            # 將 QPainterPath 轉換為點列表
            points = self._painter_path_to_points(path)
            
            # 快取結果
            if self.cache_enabled and cache_key:
                self.routing_cache[cache_key] = [(p.x(), p.y()) for p in points]
                # 限制快取大小
                if len(self.routing_cache) > 100:
                    # 移除最舊的一半條目
                    keys_to_remove = list(self.routing_cache.keys())[:50]
                    for key in keys_to_remove:
                        del self.routing_cache[key]
            
            return points
            
        except Exception as e:
            print(f"高級路由失敗: {e}")
            # 回退到直線
            from PyQt5.QtCore import QPointF
            return [QPointF(start_pos.x(), start_pos.y()), QPointF(end_pos.x(), end_pos.y())]
    
    def _painter_path_to_points(self, path):
        """
        將 QPainterPath 轉換為點列表
        
        Args:
            path: QPainterPath 對象
            
        Returns:
            QPointF 列表
        """
        from PyQt5.QtCore import QPointF
        
        points = []
        
        # 提取路徑中的所有點
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            point = QPointF(element.x, element.y)
            
            # 避免重複點
            if not points or (points[-1] - point).manhattanLength() > 1.0:
                points.append(point)
        
        # 確保至少有起點和終點
        if not points:
            current_pos = path.currentPosition()
            points = [QPointF(current_pos.x(), current_pos.y())]
        
        return points
    
    def _create_cache_key(self, start_pos, end_pos, obstacles):
        """
        創建快取鍵
        
        Args:
            start_pos: 起始位置
            end_pos: 結束位置
            obstacles: 障礙物列表
            
        Returns:
            快取鍵字符串
        """
        # 簡化的快取鍵，基於主要參數
        start_key = f"{int(start_pos.x())},{int(start_pos.y())}"
        end_key = f"{int(end_pos.x())},{int(end_pos.y())}"
        
        obstacles_key = ""
        if obstacles:
            # 只考慮前幾個障礙物以避免鍵過長
            for i, rect in enumerate(obstacles[:5]):
                obstacles_key += f"_{int(rect.x())},{int(rect.y())},{int(rect.width())},{int(rect.height())}"
        
        return f"{start_key}-{end_key}{obstacles_key}"
    
    def clear_cache(self):
        """清空路由快取"""
        self.routing_cache.clear()
        print("路由快取已清空")
    
    def set_cache_enabled(self, enabled: bool):
        """設置是否啟用快取"""
        self.cache_enabled = enabled
        if not enabled:
            self.clear_cache()
    
    def get_stats(self):
        """
        獲取路由器統計信息
        
        Returns:
            統計信息字典
        """
        engine_stats = self.routing_engine.get_performance_stats()
        return {
            **engine_stats,
            "cache_size": len(self.routing_cache),
            "cache_enabled": self.cache_enabled
        }
    
    def optimize_for_large_graphs(self, enable: bool = True):
        """
        為大型圖形優化路由器性能
        
        Args:
            enable: 是否啟用優化模式
        """
        if enable:
            # 啟用性能優化
            self.routing_engine.optimization_enabled = True
            self.routing_engine.minimum_edge_distance = 12  # 增加最小距離
            self.cache_enabled = True
            print("已啟用大型圖形優化模式")
        else:
            # 恢復標準模式
            self.routing_engine.optimization_enabled = True
            self.routing_engine.minimum_edge_distance = 8
            print("已恢復標準路由模式")