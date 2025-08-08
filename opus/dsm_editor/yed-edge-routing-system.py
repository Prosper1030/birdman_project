#!/usr/bin/env python3
"""
yEd 風格 Edge Routing 系統 - 完整實現
支援正交路由、智慧避障、多邊線分散
"""

import math
import heapq
from typing import List, Tuple, Optional, Dict, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import time

from PyQt5.QtCore import QPointF, QRectF, QLineF, Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QPainterPath, QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsRectItem


# ===================== 資料結構定義 =====================

class RoutingStyle(Enum):
    """路由風格枚舉"""
    STRAIGHT = "straight"           # 直線（後備方案）
    ORTHOGONAL = "orthogonal"      # 正交路由（主要）
    POLYLINE = "polyline"           # 多邊形路由
    CURVED = "curved"               # 曲線路由


class EdgeType(Enum):
    """邊線類型"""
    SINGLE = "single"               # 單向邊
    BIDIRECTIONAL = "bidirectional" # 雙向邊
    PARALLEL = "parallel"           # 平行邊組


@dataclass
class GridPoint:
    """網格點"""
    x: int
    y: int
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __lt__(self, other):
        """用於優先佇列排序"""
        return (self.x, self.y) < (other.x, other.y)


@dataclass
class RouteSegment:
    """路由段"""
    start: QPointF
    end: QPointF
    direction: Tuple[float, float]  # 方向向量
    
    def length(self) -> float:
        """計算段長度"""
        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        return math.sqrt(dx * dx + dy * dy)


@dataclass
class RoutingRequest:
    """路由請求"""
    source_rect: QRectF
    target_rect: QRectF
    style: RoutingStyle = RoutingStyle.ORTHOGONAL
    edge_type: EdgeType = EdgeType.SINGLE
    priority: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass 
class RoutingResult:
    """路由結果"""
    path: QPainterPath
    segments: List[RouteSegment]
    bends: int
    length: float
    computation_time: float
    success: bool


# ===================== 核心路由網格 =====================

class RoutingGrid:
    """路由網格系統 - 管理空間分割和障礙物"""
    
    def __init__(self, scene_rect: QRectF, grid_size: float = 10.0):
        """
        初始化路由網格
        
        Args:
            scene_rect: 場景邊界
            grid_size: 網格大小（像素）
        """
        self.scene_rect = scene_rect
        self.grid_size = grid_size
        
        # 計算網格維度
        self.width = int(scene_rect.width() / grid_size) + 1
        self.height = int(scene_rect.height() / grid_size) + 1
        
        # 障礙物管理
        self.obstacles: Set[GridPoint] = set()
        self.node_rects: List[QRectF] = []
        
        # 效能優化：使用位元陣列表示障礙物
        self._obstacle_bitmap = [[False] * self.width for _ in range(self.height)]
        
        # 空間索引（四叉樹）
        self.quadtree = QuadTree(scene_rect, max_depth=6)
    
    def world_to_grid(self, point: QPointF) -> GridPoint:
        """世界座標轉網格座標"""
        x = int((point.x() - self.scene_rect.left()) / self.grid_size)
        y = int((point.y() - self.scene_rect.top()) / self.grid_size)
        
        # 邊界檢查
        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))
        
        return GridPoint(x, y)
    
    def grid_to_world(self, grid_point: GridPoint) -> QPointF:
        """網格座標轉世界座標"""
        x = self.scene_rect.left() + grid_point.x * self.grid_size
        y = self.scene_rect.top() + grid_point.y * self.grid_size
        return QPointF(x, y)
    
    def add_node_obstacle(self, rect: QRectF, padding: float = 5.0):
        """添加節點障礙物"""
        # 擴展矩形以增加間距
        expanded = rect.adjusted(-padding, -padding, padding, padding)
        self.node_rects.append(expanded)
        
        # 更新四叉樹
        self.quadtree.insert(expanded)
        
        # 轉換為網格障礙物
        top_left = self.world_to_grid(expanded.topLeft())
        bottom_right = self.world_to_grid(expanded.bottomRight())
        
        for y in range(top_left.y, min(bottom_right.y + 1, self.height)):
            for x in range(top_left.x, min(bottom_right.x + 1, self.width)):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.obstacles.add(GridPoint(x, y))
                    self._obstacle_bitmap[y][x] = True
    
    def is_blocked(self, point: GridPoint) -> bool:
        """檢查網格點是否被阻擋"""
        if 0 <= point.x < self.width and 0 <= point.y < self.height:
            return self._obstacle_bitmap[point.y][point.x]
        return True
    
    def get_neighbors(self, point: GridPoint, routing_style: RoutingStyle) -> List[Tuple[GridPoint, float]]:
        """
        獲取鄰近可達點及移動成本
        
        Returns:
            List of (neighbor_point, move_cost) tuples
        """
        neighbors = []
        
        if routing_style == RoutingStyle.ORTHOGONAL:
            # 四方向移動
            directions = [(0, 1, 1.0), (0, -1, 1.0), 
                         (1, 0, 1.0), (-1, 0, 1.0)]
        else:
            # 八方向移動（包含對角線）
            directions = [
                (0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
                (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)
            ]
        
        for dx, dy, cost in directions:
            new_point = GridPoint(point.x + dx, point.y + dy)
            
            if not self.is_blocked(new_point):
                neighbors.append((new_point, cost))
        
        return neighbors
    
    def clear_obstacles(self):
        """清除所有障礙物"""
        self.obstacles.clear()
        self.node_rects.clear()
        self._obstacle_bitmap = [[False] * self.width for _ in range(self.height)]
        self.quadtree = QuadTree(self.scene_rect, max_depth=6)


# ===================== 四叉樹空間索引 =====================

class QuadTree:
    """四叉樹用於空間查詢優化"""
    
    def __init__(self, bounds: QRectF, max_depth: int = 6, max_items: int = 10):
        self.bounds = bounds
        self.max_depth = max_depth
        self.max_items = max_items
        self.depth = 0
        self.items: List[QRectF] = []
        self.children: Optional[List[QuadTree]] = None
    
    def insert(self, rect: QRectF):
        """插入矩形"""
        if not self.bounds.intersects(rect):
            return
        
        if self.children:
            # 已分割，插入到子節點
            for child in self.children:
                child.insert(rect)
        else:
            self.items.append(rect)
            
            # 檢查是否需要分割
            if len(self.items) > self.max_items and self.depth < self.max_depth:
                self._subdivide()
    
    def _subdivide(self):
        """分割節點"""
        cx = self.bounds.center().x()
        cy = self.bounds.center().y()
        w = self.bounds.width() / 2
        h = self.bounds.height() / 2
        
        self.children = [
            QuadTree(QRectF(self.bounds.left(), self.bounds.top(), w, h), 
                    self.max_depth, self.max_items),
            QuadTree(QRectF(cx, self.bounds.top(), w, h), 
                    self.max_depth, self.max_items),
            QuadTree(QRectF(self.bounds.left(), cy, w, h), 
                    self.max_depth, self.max_items),
            QuadTree(QRectF(cx, cy, w, h), 
                    self.max_depth, self.max_items)
        ]
        
        for child in self.children:
            child.depth = self.depth + 1
        
        # 重新插入項目
        for item in self.items:
            for child in self.children:
                child.insert(item)
        
        self.items.clear()
    
    def query(self, rect: QRectF) -> List[QRectF]:
        """查詢與給定矩形相交的所有項目"""
        result = []
        
        if not self.bounds.intersects(rect):
            return result
        
        if self.children:
            for child in self.children:
                result.extend(child.query(rect))
        else:
            for item in self.items:
                if item.intersects(rect):
                    result.append(item)
        
        return result


# ===================== A* 路徑搜尋器 =====================

class AStarPathfinder:
    """A* 路徑搜尋演算法 - 針對邊線路由優化"""
    
    def __init__(self, grid: RoutingGrid):
        self.grid = grid
        
        # 懲罰參數
        self.bend_penalty = 5.0        # 彎曲懲罰
        self.crossing_penalty = 10.0   # 交叉懲罰
        self.node_proximity_penalty = 3.0  # 節點接近懲罰
        
        # 快取
        self._path_cache: Dict[Tuple[GridPoint, GridPoint], List[GridPoint]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def find_path(
        self, 
        start: GridPoint, 
        goal: GridPoint,
        routing_style: RoutingStyle = RoutingStyle.ORTHOGONAL,
        existing_edges: Optional[List[List[GridPoint]]] = None
    ) -> Optional[List[GridPoint]]:
        """
        使用 A* 演算法尋找最佳路徑
        
        Args:
            start: 起始網格點
            goal: 目標網格點
            routing_style: 路由風格
            existing_edges: 現有邊線路徑（用於避免交叉）
        
        Returns:
            路徑點列表，若無法找到則返回 None
        """
        # 檢查快取
        cache_key = (start, goal)
        if cache_key in self._path_cache:
            self._cache_hits += 1
            return self._path_cache[cache_key].copy()
        
        self._cache_misses += 1
        
        # A* 演算法實現
        open_set = []
        heapq.heappush(open_set, (0, 0, start, None))  # (f_score, g_score, node, direction)
        
        came_from = {}
        g_score = defaultdict(lambda: float('inf'))
        g_score[start] = 0
        
        direction_changes = defaultdict(int)
        
        while open_set:
            current_f, current_g, current, prev_direction = heapq.heappop(open_set)
            
            if current == goal:
                # 重建路徑
                path = self._reconstruct_path(came_from, current)
                # 快取結果
                self._path_cache[cache_key] = path.copy()
                return path
            
            for neighbor, move_cost in self.grid.get_neighbors(current, routing_style):
                # 計算方向
                direction = (neighbor.x - current.x, neighbor.y - current.y)
                
                # 計算 g_score
                tentative_g = g_score[current] + move_cost
                
                # 添加彎曲懲罰
                if prev_direction and direction != prev_direction:
                    tentative_g += self.bend_penalty
                
                # 添加交叉懲罰
                if existing_edges:
                    cross_count = self._count_crossings(
                        current, neighbor, existing_edges
                    )
                    tentative_g += cross_count * self.crossing_penalty
                
                # 添加節點接近懲罰
                proximity_penalty = self._calculate_proximity_penalty(neighbor)
                tentative_g += proximity_penalty
                
                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    
                    # 計算 f_score with tie-breaking
                    h_score = self._heuristic_with_tiebreaking(
                        neighbor, goal, start
                    )
                    f_score = tentative_g + h_score
                    
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor, direction))
        
        return None  # 無法找到路徑
    
    def _heuristic_with_tiebreaking(
        self, 
        current: GridPoint, 
        goal: GridPoint, 
        start: GridPoint
    ) -> float:
        """
        改進的啟發函數，包含 tie-breaking
        """
        # Manhattan 距離（正交路由）
        dx = abs(current.x - goal.x)
        dy = abs(current.y - goal.y)
        base_distance = dx + dy
        
        # Tie-breaking：偏好直線路徑
        dx1 = current.x - goal.x
        dy1 = current.y - goal.y
        dx2 = start.x - goal.x
        dy2 = start.y - goal.y
        cross = abs(dx1 * dy2 - dx2 * dy1)
        
        return base_distance + cross * 0.001
    
    def _reconstruct_path(
        self, 
        came_from: Dict[GridPoint, GridPoint], 
        current: GridPoint
    ) -> List[GridPoint]:
        """重建路徑"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path
    
    def _count_crossings(
        self, 
        p1: GridPoint, 
        p2: GridPoint, 
        existing_edges: List[List[GridPoint]]
    ) -> int:
        """計算與現有邊線的交叉數"""
        crossings = 0
        
        for edge_path in existing_edges:
            for i in range(len(edge_path) - 1):
                if self._segments_intersect(
                    p1, p2, edge_path[i], edge_path[i + 1]
                ):
                    crossings += 1
        
        return crossings
    
    def _segments_intersect(
        self, 
        p1: GridPoint, p2: GridPoint, 
        p3: GridPoint, p4: GridPoint
    ) -> bool:
        """檢查兩線段是否相交（使用向量叉積）"""
        def ccw(A, B, C):
            return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)
        
        return (ccw(p1, p3, p4) != ccw(p2, p3, p4) and
                ccw(p1, p2, p3) != ccw(p1, p2, p4))
    
    def _calculate_proximity_penalty(self, point: GridPoint) -> float:
        """計算節點接近懲罰"""
        world_point = self.grid.grid_to_world(point)
        min_distance = float('inf')
        
        # 查詢附近的節點
        search_radius = 50.0
        search_rect = QRectF(
            world_point.x() - search_radius,
            world_point.y() - search_radius,
            search_radius * 2,
            search_radius * 2
        )
        
        nearby_nodes = self.grid.quadtree.query(search_rect)
        
        for node_rect in nearby_nodes:
            center = node_rect.center()
            distance = math.sqrt(
                (world_point.x() - center.x()) ** 2 +
                (world_point.y() - center.y()) ** 2
            )
            min_distance = min(min_distance, distance)
        
        # 指數衰減懲罰
        if min_distance < 50:
            return self.node_proximity_penalty * math.exp(-min_distance / 20)
        
        return 0
    
    def clear_cache(self):
        """清除路徑快取"""
        self._path_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_cache_stats(self) -> Dict[str, int]:
        """獲取快取統計"""
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'cache_size': len(self._path_cache)
        }


# ===================== 路徑優化器 =====================

class PathOptimizer:
    """路徑優化器 - 提升視覺品質"""
    
    @staticmethod
    def simplify_path(path: List[GridPoint]) -> List[GridPoint]:
        """
        簡化路徑，移除共線點
        使用 Douglas-Peucker 演算法
        """
        if len(path) <= 2:
            return path
        
        simplified = [path[0]]
        
        for i in range(1, len(path) - 1):
            prev = path[i - 1]
            curr = path[i]
            next = path[i + 1]
            
            # 檢查是否共線
            dx1 = curr.x - prev.x
            dy1 = curr.y - prev.y
            dx2 = next.x - curr.x
            dy2 = next.y - curr.y
            
            # 使用叉積檢查共線性
            cross = dx1 * dy2 - dy1 * dx2
            
            if abs(cross) > 0.001:  # 不共線，保留點
                simplified.append(curr)
        
        simplified.append(path[-1])
        return simplified
    
    @staticmethod
    def smooth_corners(
        path: List[QPointF], 
        corner_radius: float = 5.0
    ) -> QPainterPath:
        """
        平滑路徑轉角
        
        Args:
            path: 路徑點列表
            corner_radius: 圓角半徑
        
        Returns:
            平滑的 QPainterPath
        """
        if len(path) < 2:
            return QPainterPath()
        
        painter_path = QPainterPath()
        painter_path.moveTo(path[0])
        
        if len(path) == 2:
            painter_path.lineTo(path[1])
            return painter_path
        
        # 處理每個轉角
        for i in range(1, len(path) - 1):
            prev = path[i - 1]
            curr = path[i]
            next = path[i + 1]
            
            # 計算向量
            v1 = QPointF(curr.x() - prev.x(), curr.y() - prev.y())
            v2 = QPointF(next.x() - curr.x(), next.y() - curr.y())
            
            # 計算長度
            len1 = math.sqrt(v1.x() ** 2 + v1.y() ** 2)
            len2 = math.sqrt(v2.x() ** 2 + v2.y() ** 2)
            
            if len1 > 0 and len2 > 0:
                # 正規化向量
                v1 = QPointF(v1.x() / len1, v1.y() / len1)
                v2 = QPointF(v2.x() / len2, v2.y() / len2)
                
                # 計算圓角控制點
                radius = min(corner_radius, len1 / 2, len2 / 2)
                
                control1 = QPointF(
                    curr.x() - v1.x() * radius,
                    curr.y() - v1.y() * radius
                )
                control2 = QPointF(
                    curr.x() + v2.x() * radius,
                    curr.y() + v2.y() * radius
                )
                
                # 添加到路徑
                painter_path.lineTo(control1)
                painter_path.quadTo(curr, control2)
            else:
                painter_path.lineTo(curr)
        
        painter_path.lineTo(path[-1])
        return painter_path
    
    @staticmethod
    def enforce_monotonic(
        path: List[GridPoint], 
        start: GridPoint, 
        goal: GridPoint
    ) -> List[GridPoint]:
        """
        強制單調性約束
        確保路徑始終朝向目標前進
        """
        if len(path) <= 2:
            return path
        
        monotonic_path = [path[0]]
        
        # 目標方向
        target_dx = 1 if goal.x > start.x else -1 if goal.x < start.x else 0
        target_dy = 1 if goal.y > start.y else -1 if goal.y < start.y else 0
        
        for i in range(1, len(path)):
            curr = path[i]
            prev = monotonic_path[-1]
            
            # 移動方向
            move_dx = 1 if curr.x > prev.x else -1 if curr.x < prev.x else 0
            move_dy = 1 if curr.y > prev.y else -1 if curr.y < prev.y else 0
            
            # 檢查單調性
            x_ok = target_dx == 0 or move_dx == 0 or target_dx == move_dx
            y_ok = target_dy == 0 or move_dy == 0 or target_dy == move_dy
            
            if x_ok and y_ok:
                monotonic_path.append(curr)
        
        # 確保包含終點
        if monotonic_path[-1] != path[-1]:
            monotonic_path.append(path[-1])
        
        return monotonic_path


# ===================== 多邊線管理器 =====================

class ParallelEdgeManager:
    """管理平行邊線的分散和佈局"""
    
    def __init__(self, base_spacing: float = 6.0, max_spread: int = 3):
        """
        Args:
            base_spacing: 基礎邊線間距
            max_spread: 最大分散數量
        """
        self.base_spacing = base_spacing
        self.max_spread = max_spread
        
        # 邊線分組：key = (src_id, dst_id), value = edge_count
        self.edge_groups: Dict[Tuple[str, str], int] = defaultdict(int)
        
        # 雙向邊線追蹤
        self.bidirectional_pairs: Set[Tuple[str, str]] = set()
    
    def register_edge(self, src_id: str, dst_id: str) -> int:
        """
        註冊邊線並返回其索引
        
        Returns:
            該邊線在組中的索引（用於計算偏移）
        """
        key = tuple(sorted([src_id, dst_id]))
        index = self.edge_groups[key]
        self.edge_groups[key] += 1
        
        # 檢查是否為雙向邊
        if (dst_id, src_id) in self.edge_groups:
            self.bidirectional_pairs.add(key)
        
        return index
    
    def calculate_offset(
        self, 
        src_id: str, 
        dst_id: str, 
        edge_index: int
    ) -> float:
        """
        計算邊線偏移量
        
        Returns:
            垂直於邊線方向的偏移距離
        """
        key = tuple(sorted([src_id, dst_id]))
        total_edges = self.edge_groups[key]
        
        if total_edges == 1:
            return 0  # 單條邊線無偏移
        
        # 限制最大分散
        if total_edges > self.max_spread:
            # 超過最大分散數，使用視覺標記而非物理分離
            return 0
        
        # 計算偏移
        if key in self.bidirectional_pairs:
            # 雙向邊線：強制分離
            if (src_id, dst_id) in self.edge_groups:
                return self.base_spacing * 1.5  # 正向
            else:
                return -self.base_spacing * 1.5  # 反向
        else:
            # 多條單向邊線：均勻分散
            center = (total_edges - 1) / 2
            return (edge_index - center) * self.base_spacing
    
    def apply_offset_to_path(
        self, 
        path: List[QPointF], 
        offset: float
    ) -> List[QPointF]:
        """
        將偏移應用到路徑
        
        Args:
            path: 原始路徑點
            offset: 偏移量
        
        Returns:
            偏移後的路徑
        """
        if abs(offset) < 0.001 or len(path) < 2:
            return path
        
        offset_path = []
        
        for i in range(len(path)):
            if i == 0:
                # 起點：使用第一段的法向量
                direction = QPointF(
                    path[1].x() - path[0].x(),
                    path[1].y() - path[0].y()
                )
            elif i == len(path) - 1:
                # 終點：使用最後一段的法向量
                direction = QPointF(
                    path[-1].x() - path[-2].x(),
                    path[-1].y() - path[-2].y()
                )
            else:
                # 中間點：使用前後段的平均法向量
                dir1 = QPointF(
                    path[i].x() - path[i-1].x(),
                    path[i].y() - path[i-1].y()
                )
                dir2 = QPointF(
                    path[i+1].x() - path[i].x(),
                    path[i+1].y() - path[i].y()
                )
                direction = QPointF(
                    (dir1.x() + dir2.x()) / 2,
                    (dir1.y() + dir2.y()) / 2
                )
            
            # 計算法向量
            length = math.sqrt(direction.x() ** 2 + direction.y() ** 2)
            if length > 0:
                normal = QPointF(-direction.y() / length, direction.x() / length)
                offset_point = QPointF(
                    path[i].x() + normal.x() * offset,
                    path[i].y() + normal.y() * offset
                )
                offset_path.append(offset_point)
            else:
                offset_path.append(path[i])
        
        return offset_path
    
    def get_edge_label(self, src_id: str, dst_id: str) -> Optional[str]:
        """
        獲取邊線標籤（用於顯示多重邊數量）
        """
        key = tuple(sorted([src_id, dst_id]))
        count = self.edge_groups[key]
        
        if count > self.max_spread:
            return f"×{count}"  # 顯示數量標籤
        
        return None
    
    def clear(self):
        """清除所有邊線記錄"""
        self.edge_groups.clear()
        self.bidirectional_pairs.clear()


# ===================== 主路由器 =====================

class YEdStyleEdgeRouter(QObject):
    """
    yEd 風格邊線路由器 - 主控制類
    """
    
    # 信號
    routing_started = pyqtSignal()
    routing_completed = pyqtSignal(RoutingResult)
    progress_updated = pyqtSignal(int, int)  # current, total
    
    def __init__(self, scene_rect: QRectF, grid_size: float = 10.0):
        super().__init__()
        
        # 核心組件
        self.grid = RoutingGrid(scene_rect, grid_size)
        self.pathfinder = AStarPathfinder(self.grid)
        self.optimizer = PathOptimizer()
        self.parallel_manager = ParallelEdgeManager()
        
        # 配置參數
        self.config = {
            'default_style': RoutingStyle.ORTHOGONAL,
            'corner_radius': 5.0,
            'node_padding': 8.0,
            'max_computation_time': 500,  # ms
            'enable_caching': True,
            'enable_smoothing': True,
            'enable_monotonic': True,
            'batch_size': 10,  # 批次處理大小
        }
        
        # 統計資訊
        self.stats = {
            'total_routes': 0,
            'successful_routes': 0,
            'failed_routes': 0,
            'total_computation_time': 0,
            'average_bends': 0,
        }
        
        # 批次處理佇列
        self.routing_queue: deque[RoutingRequest] = deque()
        self.batch_timer = QTimer()
        self.batch_timer.timeout.connect(self._process_batch)
        self.batch_timer.setInterval(50)  # 50ms 批次處理間隔
    
    def configure(self, **kwargs):
        """更新配置參數"""
        self.config.update(kwargs)
    
    def add_node_obstacle(self, node_rect: QRectF):
        """添加節點障礙物"""
        self.grid.add_node_obstacle(node_rect, self.config['node_padding'])
    
    def route_edge(
        self,
        source_rect: QRectF,
        target_rect: QRectF,
        src_id: str = "",
        dst_id: str = "",
        routing_style: Optional[RoutingStyle] = None,
        immediate: bool = False
    ) -> Optional[RoutingResult]:
        """
        路由單條邊線
        
        Args:
            source_rect: 源節點矩形
            target_rect: 目標節點矩形
            src_id: 源節點 ID（用於多邊線管理）
            dst_id: 目標節點 ID
            routing_style: 路由風格（默認使用配置）
            immediate: 是否立即處理（不加入佇列）
        
        Returns:
            路由結果，若加入佇列則返回 None
        """
        if routing_style is None:
            routing_style = self.config['default_style']
        
        request = RoutingRequest(
            source_rect=source_rect,
            target_rect=target_rect,
            style=routing_style
        )
        
        if immediate:
            return self._route_single_edge(request, src_id, dst_id)
        else:
            # 加入批次處理佇列
            self.routing_queue.append((request, src_id, dst_id))
            if not self.batch_timer.isActive():
                self.batch_timer.start()
            return None
    
    def _route_single_edge(
        self,
        request: RoutingRequest,
        src_id: str,
        dst_id: str
    ) -> RoutingResult:
        """執行單條邊線路由"""
        start_time = time.time()
        
        # 計算連接點
        src_point = self._find_connection_point(
            request.source_rect, 
            request.target_rect.center()
        )
        dst_point = self._find_connection_point(
            request.target_rect,
            request.source_rect.center()
        )
        
        # 轉換為網格座標
        src_grid = self.grid.world_to_grid(src_point)
        dst_grid = self.grid.world_to_grid(dst_point)
        
        # 路徑搜尋
        grid_path = self.pathfinder.find_path(
            src_grid, dst_grid, request.style
        )
        
        if grid_path is None:
            # 失敗，使用直線作為後備
            return self._create_straight_line_result(
                src_point, dst_point, time.time() - start_time
            )
        
        # 優化路徑
        if self.config['enable_monotonic']:
            grid_path = self.optimizer.enforce_monotonic(
                grid_path, src_grid, dst_grid
            )
        
        grid_path = self.optimizer.simplify_path(grid_path)
        
        # 轉換為世界座標
        world_path = [self.grid.grid_to_world(p) for p in grid_path]
        
        # 確保端點精確
        world_path[0] = src_point
        world_path[-1] = dst_point
        
        # 處理平行邊偏移
        if src_id and dst_id:
            edge_index = self.parallel_manager.register_edge(src_id, dst_id)
            offset = self.parallel_manager.calculate_offset(
                src_id, dst_id, edge_index
            )
            world_path = self.parallel_manager.apply_offset_to_path(
                world_path, offset
            )
        
        # 創建最終路徑
        if self.config['enable_smoothing']:
            painter_path = self.optimizer.smooth_corners(
                world_path, self.config['corner_radius']
            )
        else:
            painter_path = self._create_painter_path(world_path)
        
        # 計算統計
        segments = self._create_segments(world_path)
        bends = len(world_path) - 2
        length = sum(s.length() for s in segments)
        computation_time = time.time() - start_time
        
        # 更新統計
        self._update_stats(True, bends, computation_time)
        
        return RoutingResult(
            path=painter_path,
            segments=segments,
            bends=bends,
            length=length,
            computation_time=computation_time,
            success=True
        )
    
    def _process_batch(self):
        """批次處理路由請求"""
        if not self.routing_queue:
            self.batch_timer.stop()
            return
        
        batch_size = min(self.config['batch_size'], len(self.routing_queue))
        self.routing_started.emit()
        
        for i in range(batch_size):
            request, src_id, dst_id = self.routing_queue.popleft()
            result = self._route_single_edge(request, src_id, dst_id)
            self.routing_completed.emit(result)
            self.progress_updated.emit(i + 1, batch_size)
        
        if not self.routing_queue:
            self.batch_timer.stop()
    
    def _find_connection_point(
        self, 
        node_rect: QRectF, 
        target_center: QPointF
    ) -> QPointF:
        """
        找到最佳連接點
        使用更智慧的錨點選擇策略
        """
        center = node_rect.center()
        
        # 計算方向向量
        dx = target_center.x() - center.x()
        dy = target_center.y() - center.y()
        
        # 8 個候選錨點
        anchors = [
            QPointF(center.x(), node_rect.top()),      # 上
            QPointF(node_rect.right(), center.y()),    # 右
            QPointF(center.x(), node_rect.bottom()),   # 下
            QPointF(node_rect.left(), center.y()),     # 左
            node_rect.topRight(),                      # 右上
            node_rect.bottomRight(),                   # 右下
            node_rect.bottomLeft(),                    # 左下
            node_rect.topLeft(),                       # 左上
        ]
        
        # 選擇最接近目標方向的錨點
        best_anchor = anchors[0]
        best_score = float('inf')
        
        for anchor in anchors:
            # 計算角度差異
            ax = anchor.x() - center.x()
            ay = anchor.y() - center.y()
            
            # 點積越大，方向越一致
            dot_product = ax * dx + ay * dy
            # 距離懲罰
            distance = math.sqrt(
                (anchor.x() - target_center.x()) ** 2 +
                (anchor.y() - target_center.y()) ** 2
            )
            
            score = distance - dot_product * 0.5
            
            if score < best_score:
                best_score = score
                best_anchor = anchor
        
        return best_anchor
    
    def _create_painter_path(self, points: List[QPointF]) -> QPainterPath:
        """創建基本的 QPainterPath"""
        path = QPainterPath()
        if not points:
            return path
        
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        
        return path
    
    def _create_segments(self, points: List[QPointF]) -> List[RouteSegment]:
        """創建路由段列表"""
        segments = []
        
        for i in range(len(points) - 1):
            direction = (
                points[i + 1].x() - points[i].x(),
                points[i + 1].y() - points[i].y()
            )
            segments.append(RouteSegment(
                start=points[i],
                end=points[i + 1],
                direction=direction
            ))
        
        return segments
    
    def _create_straight_line_result(
        self,
        src_point: QPointF,
        dst_point: QPointF,
        computation_time: float
    ) -> RoutingResult:
        """創建直線路由結果（後備方案）"""
        path = QPainterPath()
        path.moveTo(src_point)
        path.lineTo(dst_point)
        
        segments = [RouteSegment(
            start=src_point,
            end=dst_point,
            direction=(dst_point.x() - src_point.x(),
                      dst_point.y() - src_point.y())
        )]
        
        length = math.sqrt(
            (dst_point.x() - src_point.x()) ** 2 +
            (dst_point.y() - src_point.y()) ** 2
        )
        
        self._update_stats(False, 0, computation_time)
        
        return RoutingResult(
            path=path,
            segments=segments,
            bends=0,
            length=length,
            computation_time=computation_time,
            success=False
        )
    
    def _update_stats(self, success: bool, bends: int, time: float):
        """更新統計資訊"""
        self.stats['total_routes'] += 1
        
        if success:
            self.stats['successful_routes'] += 1
        else:
            self.stats['failed_routes'] += 1
        
        self.stats['total_computation_time'] += time
        
        # 更新平均彎曲數
        n = self.stats['successful_routes']
        if n > 0:
            prev_avg = self.stats['average_bends']
            self.stats['average_bends'] = (prev_avg * (n - 1) + bends) / n
    
    def clear_all(self):
        """清除所有資料"""
        self.grid.clear_obstacles()
        self.pathfinder.clear_cache()
        self.parallel_manager.clear()
        self.routing_queue.clear()
        self.batch_timer.stop()
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        stats = self.stats.copy()
        stats.update(self.pathfinder.get_cache_stats())
        return stats


# ===================== 整合到現有 EdgeItem =====================

class EnhancedEdgeItem(QGraphicsPathItem):
    """
    增強的 EdgeItem - 整合 yEd 風格路由
    直接替換或擴展現有的 EdgeItem 類
    """
    
    # 類別級路由器（所有邊線共享）
    _router: Optional[YEdStyleEdgeRouter] = None
    
    @classmethod
    def initialize_router(cls, scene_rect: QRectF):
        """初始化共享路由器"""
        if cls._router is None:
            cls._router = YEdStyleEdgeRouter(scene_rect)
    
    def __init__(self, src: 'TaskNode', dst: 'TaskNode'):
        super().__init__()
        
        self.src = src
        self.dst = dst
        self.label = ""
        self.isTemporary = False
        
        # 路由結果快取
        self._routing_result: Optional[RoutingResult] = None
        self._needs_reroute = True
        
        # 樣式設定（保持原有）
        self.normalPen = QPen(Qt.black, 2, Qt.SolidLine)
        self.hoverPen = QPen(Qt.black, 3, Qt.SolidLine)
        self.selectedPen = QPen(Qt.blue, 3, Qt.SolidLine)
        self.tempPen = QPen(Qt.gray, 2, Qt.DashLine)
        
        self.setPen(self.normalPen)
        self.setZValue(1)
        
        # 設定旗標
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        # 建立箭頭（保持原有）
        self.arrowHead = QGraphicsPathItem()
        self.arrowHead.setBrush(QBrush(Qt.black))
        self.arrowHead.setPen(QPen(Qt.black, 1))
        self.arrowHead.setZValue(2)
        self.arrowHead.setParentItem(self)
        
        # 標籤（用於顯示多重邊）
        self.labelItem = None
        
        # 初始路由
        self.updatePath()
    
    def updatePath(self, use_routing: bool = True):
        """
        更新路徑 - 支援智慧路由
        
        Args:
            use_routing: 是否使用路由器（False 時使用直線）
        """
        if not self.src or not self.dst:
            return
        
        if use_routing and self._router and not self.isTemporary:
            # 使用路由器
            if self._needs_reroute:
                # 添加節點障礙物
                self._router.add_node_obstacle(self.src.sceneBoundingRect())
                self._router.add_node_obstacle(self.dst.sceneBoundingRect())
                
                # 執行路由
                self._routing_result = self._router.route_edge(
                    self.src.sceneBoundingRect(),
                    self.dst.sceneBoundingRect(),
                    self.src.taskId,
                    self.dst.taskId,
                    immediate=True
                )
                
                self._needs_reroute = False
            
            if self._routing_result and self._routing_result.success:
                self.setPath(self._routing_result.path)
                
                # 更新箭頭
                if self._routing_result.segments:
                    last_segment = self._routing_result.segments[-1]
                    self._updateArrowHead(last_segment.start, last_segment.end)
                
                # 檢查是否需要標籤
                label = self._router.parallel_manager.get_edge_label(
                    self.src.taskId, self.dst.taskId
                )
                if label:
                    self._updateLabel(label)
                
                return
        
        # 後備：使用原有的直線路由
        self._updateStraightPath()
    
    def _updateStraightPath(self):
        """更新為直線路徑（原有實現）"""
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()
        
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()
        
        # 計算方向
        dx = dstCenter.x() - srcCenter.x()
        dy = dstCenter.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 1:
            return
        
        dx /= length
        dy /= length
        
        # 計算連接點（使用原有方法）
        srcPos = self.getConnectionPoint(srcRect, srcCenter, dx, dy)
        dstPos = self.getConnectionPoint(dstRect, dstCenter, -dx, -dy)
        
        # 建立路徑
        path = QPainterPath()
        path.moveTo(srcPos)
        path.lineTo(dstPos)
        self.setPath(path)
        
        # 更新箭頭
        self._updateArrowHead(srcPos, dstPos)
    
    def getConnectionPoint(self, rect, center, dx, dy):
        """計算與矩形邊界的交點（保持原有實現）"""
        halfWidth = rect.width() / 2
        halfHeight = rect.height() / 2
        
        if abs(dx) > abs(dy):
            if dx > 0:
                x = center.x() + halfWidth
                y = center.y() + dy * halfWidth / abs(dx)
            else:
                x = center.x() - halfWidth
                y = center.y() - dy * halfWidth / abs(dx)
        else:
            if dy > 0:
                y = center.y() + halfHeight
                x = center.x() + dx * halfHeight / abs(dy)
            else:
                y = center.y() - halfHeight
                x = center.x() - dx * halfHeight / abs(dy)
        
        return QPointF(x, y)
    
    def _updateArrowHead(self, srcPos: QPointF, dstPos: QPointF):
        """更新箭頭（保持原有實現）"""
        dx = dstPos.x() - srcPos.x()
        dy = dstPos.y() - srcPos.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 1:
            return
        
        dx /= length
        dy /= length
        
        arrowSize = 15
        arrowAngle = math.pi / 6
        
        tip = dstPos
        angle = math.atan2(dy, dx)
        
        left = QPointF(
            tip.x() - arrowSize * math.cos(angle - arrowAngle),
            tip.y() - arrowSize * math.sin(angle - arrowAngle)
        )
        right = QPointF(
            tip.x() - arrowSize * math.cos(angle + arrowAngle),
            tip.y() - arrowSize * math.sin(angle + arrowAngle)
        )
        
        arrowPath = QPainterPath()
        arrowPath.moveTo(tip)
        arrowPath.lineTo(left)
        arrowPath.lineTo(right)
        arrowPath.closeSubpath()
        
        self.arrowHead.setPath(arrowPath)
    
    def _updateLabel(self, text: str):
        """更新標籤顯示"""
        if not self.labelItem:
            from PyQt5.QtWidgets import QGraphicsTextItem
            self.labelItem = QGraphicsTextItem(self)
            self.labelItem.setDefaultTextColor(Qt.darkGray)
            font = self.labelItem.font()
            font.setPointSize(8)
            self.labelItem.setFont(font)
        
        self.labelItem.setPlainText(text)
        
        # 定位在路徑中點
        if self._routing_result and self._routing_result.segments:
            mid_segment = self._routing_result.segments[len(self._routing_result.segments) // 2]
            mid_point = QPointF(
                (mid_segment.start.x() + mid_segment.end.x()) / 2,
                (mid_segment.start.y() + mid_segment.end.y()) / 2
            )
            self.labelItem.setPos(mid_point)
    
    def invalidateRoute(self):
        """標記需要重新路由"""
        self._needs_reroute = True
    
    def setTemporary(self, temporary: bool):
        """設定是否為臨時連線"""
        self.isTemporary = temporary
        if temporary:
            self.setPen(self.tempPen)
            self.arrowHead.setBrush(QBrush(Qt.gray))
        else:
            self.setPen(self.normalPen)
            self.arrowHead.setBrush(QBrush(Qt.black))
