#!/usr/bin/env python3
"""
yEd 風格邊線路由演算法實現
實現乾淨的線條路由，最小化交叉，支援正交和多邊形路由
"""

import math
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
import heapq
from PyQt5.QtCore import QPointF, QRectF, QLineF
from PyQt5.QtGui import QPainterPath


class RoutingStyle(Enum):
    """路由風格枚舉"""
    ORTHOGONAL = "orthogonal"    # 正交路由（僅垂直水平）
    OCTILINEAR = "octilinear"    # 八方向路由（45度倍數）
    POLYLINE = "polyline"        # 多邊形路由
    

@dataclass
class GridPoint:
    """網格點"""
    x: int
    y: int
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


@dataclass 
class PathSegment:
    """路徑段"""
    start: GridPoint
    end: GridPoint
    direction: Tuple[int, int]  # 方向向量
    
    def length(self) -> float:
        return math.sqrt((self.end.x - self.start.x)**2 + (self.end.y - self.start.y)**2)


class PenaltyFunction:
    """懲罰函數系統"""
    
    def __init__(self):
        self.crossing_penalty = 2.0           # 一般交叉懲罰
        self.adjacent_crossing_penalty = 3.0   # 相鄰邊交叉懲罰  
        self.self_crossing_penalty = 5.0      # 自我交叉懲罰
        self.bend_penalty = 0.1              # 彎曲點懲罰
        self.node_collision_penalty = 10.0    # 節點碰撞懲罰
        self.edge_spacing_penalty = 0.5       # 邊線間距懲罰
        
    def calculate_segment_cost(self, segment: PathSegment, existing_paths: List[List[GridPoint]], 
                             blocked_areas: Set[GridPoint]) -> float:
        """計算路徑段的懲罰成本"""
        cost = segment.length()  # 基本距離成本
        
        # 檢查節點碰撞
        if segment.start in blocked_areas or segment.end in blocked_areas:
            cost += self.node_collision_penalty
            
        # 檢查與現有路徑的交叉
        for path in existing_paths:
            crossings = self._count_crossings(segment, path)
            cost += crossings * self.crossing_penalty
            
        return cost
        
    def _count_crossings(self, segment: PathSegment, path: List[GridPoint]) -> int:
        """計算線段與路徑的交叉數量"""
        crossings = 0
        for i in range(len(path) - 1):
            path_segment = PathSegment(path[i], path[i + 1], (0, 0))
            if self._segments_intersect(segment, path_segment):
                crossings += 1
        return crossings
        
    def _segments_intersect(self, seg1: PathSegment, seg2: PathSegment) -> bool:
        """檢查兩個線段是否相交"""
        # 使用向量叉積判斷線段相交
        def ccw(A, B, C):
            return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)
            
        return (ccw(seg1.start, seg2.start, seg2.end) != ccw(seg1.end, seg2.start, seg2.end) and
                ccw(seg1.start, seg1.end, seg2.start) != ccw(seg1.start, seg1.end, seg2.end))


class RoutingGrid:
    """路由網格系統"""
    
    def __init__(self, bounds: QRectF, grid_spacing: float = 20.0):
        self.bounds = bounds
        self.spacing = grid_spacing
        self.blocked_points: Set[GridPoint] = set()
        self.width = int(bounds.width() / grid_spacing) + 1
        self.height = int(bounds.height() / grid_spacing) + 1
        
    def world_to_grid(self, point: QPointF) -> GridPoint:
        """世界座標轉網格座標"""
        x = int((point.x() - self.bounds.left()) / self.spacing)
        y = int((point.y() - self.bounds.top()) / self.spacing)
        return GridPoint(max(0, min(x, self.width - 1)), max(0, min(y, self.height - 1)))
        
    def grid_to_world(self, grid_point: GridPoint) -> QPointF:
        """網格座標轉世界座標"""
        x = self.bounds.left() + grid_point.x * self.spacing
        y = self.bounds.top() + grid_point.y * self.spacing
        return QPointF(x, y)
        
    def add_blocked_area(self, rect: QRectF):
        """添加阻塞區域（節點位置）"""
        top_left = self.world_to_grid(rect.topLeft())
        bottom_right = self.world_to_grid(rect.bottomRight())
        
        for x in range(top_left.x, bottom_right.x + 1):
            for y in range(top_left.y, bottom_right.y + 1):
                self.blocked_points.add(GridPoint(x, y))
                
    def get_neighbors(self, point: GridPoint, routing_style: RoutingStyle) -> List[GridPoint]:
        """獲取鄰近可達點"""
        neighbors = []
        
        if routing_style == RoutingStyle.ORTHOGONAL:
            # 僅四方向（上下左右）
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        elif routing_style == RoutingStyle.OCTILINEAR:
            # 八方向（包含45度斜線）
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0), 
                         (1, 1), (1, -1), (-1, 1), (-1, -1)]
        else:
            # 多邊形路由，允許任意角度（簡化為八方向）
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0), 
                         (1, 1), (1, -1), (-1, 1), (-1, -1)]
            
        for dx, dy in directions:
            new_x, new_y = point.x + dx, point.y + dy
            
            if (0 <= new_x < self.width and 0 <= new_y < self.height):
                new_point = GridPoint(new_x, new_y)
                if new_point not in self.blocked_points:
                    neighbors.append(new_point)
                    
        return neighbors


class AStarPathfinder:
    """A* 路徑搜尋演算法"""
    
    def __init__(self, grid: RoutingGrid, penalty_function: PenaltyFunction):
        self.grid = grid
        self.penalty_function = penalty_function
        
    def find_path(self, start: GridPoint, goal: GridPoint, 
                  routing_style: RoutingStyle,
                  existing_paths: List[List[GridPoint]] = None) -> Optional[List[GridPoint]]:
        """使用A*演算法尋找最佳路徑"""
        if existing_paths is None:
            existing_paths = []
            
        # 優先級佇列：(f_score, g_score, point)
        open_set = [(0, 0, start)]
        came_from: Dict[GridPoint, GridPoint] = {}
        g_score: Dict[GridPoint, float] = defaultdict(lambda: float('inf'))
        g_score[start] = 0
        
        visited = set()
        
        while open_set:
            current_f, current_g, current = heapq.heappop(open_set)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == goal:
                return self._reconstruct_path(came_from, current)
                
            for neighbor in self.grid.get_neighbors(current, routing_style):
                if neighbor in visited:
                    continue
                    
                # 計算移動成本（包含懲罰）
                segment = PathSegment(current, neighbor, 
                                    (neighbor.x - current.x, neighbor.y - current.y))
                move_cost = self.penalty_function.calculate_segment_cost(
                    segment, existing_paths, self.grid.blocked_points)
                
                tentative_g_score = g_score[current] + move_cost
                
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score = tentative_g_score + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, tentative_g_score, neighbor))
                    
        return None  # 找不到路徑
        
    def _heuristic(self, point: GridPoint, goal: GridPoint) -> float:
        """啟發函數（歐幾里得距離）"""
        return math.sqrt((goal.x - point.x)**2 + (goal.y - point.y)**2)
        
    def _reconstruct_path(self, came_from: Dict[GridPoint, GridPoint], 
                         current: GridPoint) -> List[GridPoint]:
        """重建路徑"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path


class MonotonicConstraint:
    """單調路徑約束"""
    
    @staticmethod
    def enforce_monotonic_path(path: List[GridPoint], source: GridPoint, 
                             target: GridPoint) -> List[GridPoint]:
        """強制執行單調路徑約束"""
        if len(path) <= 2:
            return path
            
        optimized_path = [path[0]]
        
        for i in range(1, len(path) - 1):
            current = path[i]
            prev_point = optimized_path[-1]
            next_point = path[i + 1]
            
            # 檢查是否朝向目標方向移動
            if MonotonicConstraint._is_moving_towards_target(prev_point, current, source, target):
                optimized_path.append(current)
            else:
                # 跳過非單調性的點
                continue
                
        optimized_path.append(path[-1])
        return optimized_path
        
    @staticmethod
    def _is_moving_towards_target(prev_point: GridPoint, current: GridPoint,
                                source: GridPoint, target: GridPoint) -> bool:
        """檢查是否朝目標方向移動"""
        # 計算從起點到終點的方向向量
        target_direction_x = 1 if target.x > source.x else -1 if target.x < source.x else 0
        target_direction_y = 1 if target.y > source.y else -1 if target.y < source.y else 0
        
        # 計算當前移動方向
        move_direction_x = 1 if current.x > prev_point.x else -1 if current.x < prev_point.x else 0
        move_direction_y = 1 if current.y > prev_point.y else -1 if current.y < prev_point.y else 0
        
        # 檢查移動方向是否與目標方向一致或正交
        x_consistent = (target_direction_x == 0) or (move_direction_x == 0) or (target_direction_x == move_direction_x)
        y_consistent = (target_direction_y == 0) or (move_direction_y == 0) or (target_direction_y == move_direction_y)
        
        return x_consistent and y_consistent


class YEdStyleEdgeRouter:
    """yEd 風格邊線路由器主類別"""
    
    def __init__(self, bounds: QRectF, grid_spacing: float = 20.0):
        self.grid = RoutingGrid(bounds, grid_spacing)
        self.penalty_function = PenaltyFunction()
        self.pathfinder = AStarPathfinder(self.grid, self.penalty_function)
        self.existing_paths: List[List[GridPoint]] = []
        
    def add_node_obstacle(self, node_rect: QRectF):
        """添加節點作為路由障礙"""
        self.grid.add_blocked_area(node_rect)
        
    def route_edge(self, source_rect: QRectF, target_rect: QRectF,
                  routing_style: RoutingStyle = RoutingStyle.ORTHOGONAL,
                  enforce_monotonic: bool = True) -> Optional[QPainterPath]:
        """路由單條邊線"""
        
        # 找到節點邊緣的最佳連接點
        source_point = self._find_connection_point(source_rect, target_rect.center())
        target_point = self._find_connection_point(target_rect, source_rect.center())
        
        # 轉換為網格座標
        source_grid = self.grid.world_to_grid(source_point)
        target_grid = self.grid.world_to_grid(target_point)
        
        # 尋找路徑
        path = self.pathfinder.find_path(source_grid, target_grid, routing_style, self.existing_paths)
        
        if path is None:
            return None
            
        # 應用單調性約束
        if enforce_monotonic:
            path = MonotonicConstraint.enforce_monotonic_path(path, source_grid, target_grid)
            
        # 儲存路徑供後續邊線參考
        self.existing_paths.append(path)
        
        # 轉換為QPainterPath
        return self._create_painter_path(path, source_point, target_point)
        
    def _find_connection_point(self, node_rect: QRectF, target_center: QPointF) -> QPointF:
        """找到節點邊緣的最佳連接點"""
        center = node_rect.center()
        
        # 計算從中心到目標的方向
        dx = target_center.x() - center.x()
        dy = target_center.y() - center.y()
        
        # 找到與節點邊界的交點
        if abs(dx) > abs(dy):
            # 水平方向主導
            if dx > 0:
                return QPointF(node_rect.right(), center.y())
            else:
                return QPointF(node_rect.left(), center.y())
        else:
            # 垂直方向主導
            if dy > 0:
                return QPointF(center.x(), node_rect.bottom())
            else:
                return QPointF(center.x(), node_rect.top())
                
    def _create_painter_path(self, grid_path: List[GridPoint], 
                           start_point: QPointF, end_point: QPointF) -> QPainterPath:
        """將網格路徑轉換為QPainterPath"""
        path = QPainterPath()
        
        if not grid_path:
            # 直線連接
            path.moveTo(start_point)
            path.lineTo(end_point)
            return path
            
        # 從起點開始
        path.moveTo(start_point)
        
        # 連接到第一個網格點
        first_world_point = self.grid.grid_to_world(grid_path[0])
        path.lineTo(first_world_point)
        
        # 沿著網格路徑
        for grid_point in grid_path[1:]:
            world_point = self.grid.grid_to_world(grid_point)
            path.lineTo(world_point)
            
        # 連接到終點
        path.lineTo(end_point)
        
        return path
        
    def optimize_global_layout(self):
        """全域佈局優化"""
        # 實現邊線重新排列以進一步減少交叉
        # 這是一個複雜的優化問題，可以使用遺傳演算法或模擬退火等方法
        pass
        
    def clear_existing_paths(self):
        """清除現有路徑，重新開始路由"""
        self.existing_paths.clear()