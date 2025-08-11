"""
Advanced Edge Routing Engine for DSM Editor - yEd Style Implementation
實現真正的正交路由和避障功能

核心功能:
1. Gate 機制讓起終點能走出節點
2. 可見性圖構建與正交連線
3. A* 路徑搜尋與曼哈頓距離計算
4. ROI 優化和轉彎代價控制
5. 網格對齊和多邊避重疊
"""

import math
import heapq
from typing import List, Tuple, Dict, Set, Optional
from dataclasses import dataclass
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPainterPath


@dataclass
class RoutingNode:
    """路由圖中的節點"""
    x: float
    y: float
    node_id: str = ""
    node_type: str = "waypoint"  # "source", "target", "waypoint", "gate", "corner"
    
    def __hash__(self):
        return hash((round(self.x, 2), round(self.y, 2), self.node_id))
    
    def __eq__(self, other):
        return abs(self.x - other.x) < 0.1 and abs(self.y - other.y) < 0.1


class VisibilityGraph:
    """正交可見性圖 - 支援 gate 機制"""
    
    def __init__(self, grid_pitch: float = 20):
        self.nodes: Set[RoutingNode] = set()
        self.adjacency: Dict[RoutingNode, List[Tuple[RoutingNode, float]]] = {}
        self.obstacles: List[QRectF] = []
        self.grid_pitch = grid_pitch  # 格點對齊
        
    def add_obstacle(self, rect: QRectF, obstacle_id: str = ""):
        """添加障礙物並創建角點和中點"""
        self.obstacles.append(rect)
        
        # 為障礙物創建 8 個關鍵點 (4角點 + 4中點)
        corners_and_midpoints = [
            RoutingNode(rect.left(), rect.top(), f"{obstacle_id}_tl", "corner"),
            RoutingNode(rect.right(), rect.top(), f"{obstacle_id}_tr", "corner"), 
            RoutingNode(rect.right(), rect.bottom(), f"{obstacle_id}_br", "corner"),
            RoutingNode(rect.left(), rect.bottom(), f"{obstacle_id}_bl", "corner"),
            RoutingNode(rect.center().x(), rect.top(), f"{obstacle_id}_tm", "waypoint"),
            RoutingNode(rect.right(), rect.center().y(), f"{obstacle_id}_rm", "waypoint"),
            RoutingNode(rect.center().x(), rect.bottom(), f"{obstacle_id}_bm", "waypoint"),
            RoutingNode(rect.left(), rect.center().y(), f"{obstacle_id}_lm", "waypoint"),
        ]
        
        for node in corners_and_midpoints:
            self.add_node(node)

    def add_node(self, node: RoutingNode):
        """添加節點到圖中"""
        # 對齊到格點
        node.x = round(node.x / self.grid_pitch) * self.grid_pitch
        node.y = round(node.y / self.grid_pitch) * self.grid_pitch
        
        self.nodes.add(node)
        if node not in self.adjacency:
            self.adjacency[node] = []

    def inject_gate_for_point(self, pos: QPointF, gate_type: str = "gate") -> Optional[RoutingNode]:
        """
        為指定點注入gate節點，讓它能走出包含它的障礙物節點
        
        Args:
            pos: 需要創建gate的位置（通常是起點或終點）
            gate_type: gate類型標識
            
        Returns:
            創建的gate節點，如果沒有包含該點的障礙物則返回None
        """
        # 找到包含此點的障礙物
        host_obstacle = None
        for obstacle in self.obstacles:
            if obstacle.contains(pos):
                host_obstacle = obstacle
                break
        
        if not host_obstacle:
            # 點不在任何障礙物內，直接添加為普通節點
            gate_node = RoutingNode(pos.x(), pos.y(), f"free_{gate_type}", gate_type)
            self.add_node(gate_node)
            return gate_node
        
        # 計算到各邊的距離
        distances = {
            'top': abs(pos.y() - host_obstacle.top()),
            'bottom': abs(pos.y() - host_obstacle.bottom()),
            'left': abs(pos.x() - host_obstacle.left()),
            'right': abs(pos.x() - host_obstacle.right())
        }
        
        # 找到最近的邊
        closest_side = min(distances, key=distances.get)
        
        # 在最近邊上創建gate節點
        if closest_side in ('top', 'bottom'):
            gate_y = host_obstacle.top() if closest_side == 'top' else host_obstacle.bottom()
            gate_node = RoutingNode(pos.x(), gate_y, f"gate_{closest_side}", gate_type)
        else:
            gate_x = host_obstacle.left() if closest_side == 'left' else host_obstacle.right()
            gate_node = RoutingNode(gate_x, pos.y(), f"gate_{closest_side}", gate_type)
        
        self.add_node(gate_node)
        
        # 連接原始點到gate（這樣可以進出節點）
        original_node = RoutingNode(pos.x(), pos.y(), f"orig_{gate_type}", gate_type)
        self.add_node(original_node)
        
        # 添加從原始點到gate的連線（零成本）
        self._add_edge(original_node, gate_node, 0.1)
        
        return gate_node

    def build_visibility_edges(self):
        """構建正交可見性邊"""
        self.adjacency = {node: [] for node in self.nodes}
        nodes_list = list(self.nodes)
        
        for i, node1 in enumerate(nodes_list):
            for node2 in nodes_list[i + 1:]:
                if self._is_orthogonal(node1, node2) and self._is_visible(node1, node2):
                    cost = self._calculate_cost_with_penalty(node1, node2)
                    self._add_edge(node1, node2, cost)
                    self._add_edge(node2, node1, cost)

    def _is_orthogonal(self, node1: RoutingNode, node2: RoutingNode) -> bool:
        """檢查兩節點是否在正交方向"""
        return abs(node1.x - node2.x) < 0.1 or abs(node1.y - node2.y) < 0.1

    def _is_visible(self, node1: RoutingNode, node2: RoutingNode) -> bool:
        """檢查兩節點間是否可見（無障礙物阻擋）"""
        # 創建連線的邊界矩形
        min_x, max_x = min(node1.x, node2.x), max(node1.x, node2.x)
        min_y, max_y = min(node1.y, node2.y), max(node1.y, node2.y)
        
        # 擴大成細長矩形進行碰撞檢測
        line_rect = QRectF(min_x - 1, min_y - 1, max_x - min_x + 2, max_y - min_y + 2)
        
        for obstacle in self.obstacles:
            if obstacle.intersects(line_rect):
                # 檢查線段是否真的穿越障礙物內部
                if self._line_crosses_obstacle_interior(node1, node2, obstacle):
                    return False
        
        return True

    def _line_crosses_obstacle_interior(self, node1: RoutingNode, node2: RoutingNode, obstacle: QRectF) -> bool:
        """檢查線段是否穿越障礙物內部"""
        # 採用多點採樣檢查
        steps = 5
        for i in range(1, steps):
            t = i / steps
            sample_x = node1.x + t * (node2.x - node1.x)
            sample_y = node1.y + t * (node2.y - node1.y)
            
            # 檢查採樣點是否在障礙物內部（不是邊界上）
            if (obstacle.left() < sample_x < obstacle.right() and 
                obstacle.top() < sample_y < obstacle.bottom()):
                return True
        
        return False

    def _calculate_cost_with_penalty(self, node1: RoutingNode, node2: RoutingNode) -> float:
        """計算帶轉彎懲罰的成本"""
        manhattan_distance = abs(node2.x - node1.x) + abs(node2.y - node1.y)
        
        # 轉彎懲罰：每次轉彎增加額外成本
        turn_penalty = 0
        if node1.node_type == "waypoint" and node2.node_type == "waypoint":
            turn_penalty = 5  # 中間點轉彎懲罰
        
        return manhattan_distance + turn_penalty

    def _add_edge(self, from_node: RoutingNode, to_node: RoutingNode, cost: float):
        """添加有向邊到鄰接表"""
        if from_node not in self.adjacency:
            self.adjacency[from_node] = []
        self.adjacency[from_node].append((to_node, cost))


class AStarPathfinder:
    """A* 路徑搜尋器 - 針對正交路由優化"""
    
    def __init__(self, visibility_graph: VisibilityGraph):
        self.graph = visibility_graph

    def find_path(self, start: RoutingNode, goal: RoutingNode) -> List[RoutingNode]:
        """使用 A* 搜尋最佳路徑"""
        # 優先佇列: (f_cost, g_cost, node)
        open_set = [(0, 0, start)]
        came_from: Dict[RoutingNode, RoutingNode] = {}
        g_cost: Dict[RoutingNode, float] = {start: 0}
        closed_set: Set[RoutingNode] = set()
        
        while open_set:
            current_f, current_g, current = heapq.heappop(open_set)
            
            if current in closed_set:
                continue
                
            closed_set.add(current)
            
            if current == goal:
                return self._reconstruct_path(came_from, current)
            
            # 檢查所有鄰居
            for neighbor, edge_cost in self.graph.adjacency.get(current, []):
                if neighbor in closed_set:
                    continue
                
                tentative_g = current_g + edge_cost
                
                if neighbor not in g_cost or tentative_g < g_cost[neighbor]:
                    came_from[neighbor] = current
                    g_cost[neighbor] = tentative_g
                    f_cost = tentative_g + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_cost, tentative_g, neighbor))
        
        return []  # 找不到路徑

    def _heuristic(self, node: RoutingNode, goal: RoutingNode) -> float:
        """啟發式函數 - 曼哈頓距離"""
        return abs(goal.x - node.x) + abs(goal.y - node.y)

    def _reconstruct_path(self, came_from: Dict[RoutingNode, RoutingNode], current: RoutingNode) -> List[RoutingNode]:
        """重建路徑"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return path[::-1]


class AdvancedEdgeRouter:
    """
    高級邊線路由器 - 真正的 yEd 風格正交路由實現
    """
    
    def __init__(self):
        self.visibility_graph = VisibilityGraph(grid_pitch=20)
        self.pathfinder = AStarPathfinder(self.visibility_graph)
        self.min_clearance = 8  # 最小間隙
        self.current_obstacles = []

    def route_edge(self, start_pos: QPointF, end_pos: QPointF, obstacles: List[QRectF] = None) -> List[QPointF]:
        """
        路由單條邊線 - 主要接口
        
        Args:
            start_pos: 起始位置
            end_pos: 結束位置
            obstacles: 障礙物列表
            
        Returns:
            路徑點列表，至少包含起點和終點
        """
        if obstacles is None:
            obstacles = []
        
        # ROI 優化：只處理相關區域的障礙物
        roi_obstacles = self._filter_obstacles_by_roi(start_pos, end_pos, obstacles)
        
        # 重建可見性圖
        self._rebuild_visibility_graph(roi_obstacles)
        
        # 為起終點注入gate節點
        start_gate = self.visibility_graph.inject_gate_for_point(start_pos, "start")
        end_gate = self.visibility_graph.inject_gate_for_point(end_pos, "end")
        
        if not start_gate or not end_gate:
            return [start_pos, end_pos]  # 回退到直線
        
        # 構建可見性邊
        self.visibility_graph.build_visibility_edges()
        
        # A* 搜尋路徑
        path_nodes = self.pathfinder.find_path(start_gate, end_gate)
        
        if len(path_nodes) < 2:
            return [start_pos, end_pos]  # 搜尋失敗，回退到直線
        
        # 轉換為 QPointF 列表
        path_points = []
        for node in path_nodes:
            path_points.append(QPointF(node.x, node.y))
        
        # 確保起終點精確
        if len(path_points) > 0:
            path_points[0] = start_pos
            path_points[-1] = end_pos
        
        return path_points

    def _rebuild_visibility_graph(self, obstacles: List[QRectF]):
        """重建可見性圖"""
        self.visibility_graph = VisibilityGraph(grid_pitch=20)
        
        # 添加障礙物（帶安全邊界）
        for i, obstacle in enumerate(obstacles):
            expanded = obstacle.adjusted(-self.min_clearance, -self.min_clearance, 
                                       self.min_clearance, self.min_clearance)
            self.visibility_graph.add_obstacle(expanded, f"obs_{i}")
        
        self.pathfinder = AStarPathfinder(self.visibility_graph)

    def _filter_obstacles_by_roi(self, start_pos: QPointF, end_pos: QPointF, 
                                obstacles: List[QRectF], padding: float = 200) -> List[QRectF]:
        """ROI 過濾：只保留搜尋區域內的障礙物"""
        # 計算 ROI
        min_x = min(start_pos.x(), end_pos.x()) - padding
        max_x = max(start_pos.x(), end_pos.x()) + padding
        min_y = min(start_pos.y(), end_pos.y()) - padding
        max_y = max(start_pos.y(), end_pos.y()) + padding
        
        roi_rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        
        # 過濾障礙物
        filtered = []
        for obstacle in obstacles:
            if roi_rect.intersects(obstacle):
                filtered.append(obstacle)
        
        print(f"[AdvancedRouter] ROI 過濾：{len(obstacles)} -> {len(filtered)} 障礙物")
        return filtered