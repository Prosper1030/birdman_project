#!/usr/bin/env python3
"""
yEd 風格路由引擎 - 核心實現
結合 ROUTING_TASK.md 需求與 opus 資料夾中的進階演算法
支援正交、多段、直線路由，具有智慧避障與平行邊分離功能
"""

import math
import heapq
import time
from typing import List, Tuple, Optional, Dict, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from PyQt5.QtCore import QPointF, QRectF, QLineF, Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QPainterPath, QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsPathItem


# ===================== 資料結構定義 =====================

class RoutingStyle(Enum):
    """路由模式枚舉 - 符合 ROUTING_TASK.md 規格"""
    STRAIGHT = "straight"           # 直線連線
    ORTHOGONAL = "orthogonal"      # 正交路由（A* 網格搜尋）
    OCTILINEAR = "octilinear"      # 45° + 90° 多邊形路由
    POLYLINE = "polyline"          # 多段折線路由


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
        return (self.x, self.y) < (other.x, other.y)


@dataclass
class RouteSegment:
    """路由段"""
    start: QPointF
    end: QPointF
    direction: Tuple[float, float]
    
    def length(self) -> float:
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
    avoid_obstacles: bool = True
    node_padding: float = 10.0
    bend_penalty: float = 0.1
    max_bends: int = 10
    parallel_spacing: float = 15.0
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
    routing_style: RoutingStyle


# ===================== 四叉樹空間索引 =====================

class QuadTree:
    """四叉樹空間索引 - 用於高效障礙物查詢"""
    
    def __init__(self, bounds: QRectF, max_depth: int = 6, max_objects: int = 10):
        self.bounds = bounds
        self.max_depth = max_depth
        self.max_objects = max_objects
        self.depth = 0
        self.objects: List[QRectF] = []
        self.children: List['QuadTree'] = []
    
    def clear(self):
        """清除所有對象和子節點"""
        self.objects.clear()
        for child in self.children:
            child.clear()
        self.children.clear()
    
    def split(self):
        """分割節點為四個子節點"""
        sub_width = self.bounds.width() / 2
        sub_height = self.bounds.height() / 2
        x = self.bounds.x()
        y = self.bounds.y()
        
        # NE, NW, SW, SE
        self.children = [
            QuadTree(QRectF(x + sub_width, y, sub_width, sub_height), 
                    self.max_depth, self.max_objects),
            QuadTree(QRectF(x, y, sub_width, sub_height), 
                    self.max_depth, self.max_objects),
            QuadTree(QRectF(x, y + sub_height, sub_width, sub_height), 
                    self.max_depth, self.max_objects),
            QuadTree(QRectF(x + sub_width, y + sub_height, sub_width, sub_height), 
                    self.max_depth, self.max_objects)
        ]
        
        for child in self.children:
            child.depth = self.depth + 1
    
    def get_index(self, rect: QRectF) -> int:
        """取得矩形所屬的子節點索引"""
        index = -1
        vertical_midpoint = self.bounds.x() + self.bounds.width() / 2
        horizontal_midpoint = self.bounds.y() + self.bounds.height() / 2
        
        top_quadrant = rect.y() < horizontal_midpoint and rect.bottom() < horizontal_midpoint
        bottom_quadrant = rect.y() > horizontal_midpoint
        
        if rect.x() < vertical_midpoint and rect.right() < vertical_midpoint:
            if top_quadrant:
                index = 1  # NW
            elif bottom_quadrant:
                index = 2  # SW
        elif rect.x() > vertical_midpoint:
            if top_quadrant:
                index = 0  # NE
            elif bottom_quadrant:
                index = 3  # SE
        
        return index
    
    def insert(self, rect: QRectF):
        """插入矩形"""
        if self.children:
            index = self.get_index(rect)
            if index != -1:
                self.children[index].insert(rect)
                return
        
        self.objects.append(rect)
        
        if len(self.objects) > self.max_objects and self.depth < self.max_depth:
            if not self.children:
                self.split()
            
            i = 0
            while i < len(self.objects):
                index = self.get_index(self.objects[i])
                if index != -1:
                    obj = self.objects.pop(i)
                    self.children[index].insert(obj)
                else:
                    i += 1
    
    def retrieve(self, rect: QRectF) -> List[QRectF]:
        """檢索可能與指定矩形相交的所有對象"""
        return_objects = list(self.objects)
        
        if self.children:
            index = self.get_index(rect)
            if index != -1:
                return_objects.extend(self.children[index].retrieve(rect))
            else:
                # 跨越多個象限，檢查所有子節點
                for child in self.children:
                    if self._intersects(rect, child.bounds):
                        return_objects.extend(child.retrieve(rect))
        
        return return_objects
    
    def _intersects(self, rect1: QRectF, rect2: QRectF) -> bool:
        """檢查兩個矩形是否相交"""
        return rect1.intersects(rect2)


# ===================== 路由網格系統 =====================

class RoutingGrid:
    """路由網格系統 - 管理空間分割和障礙物"""
    
    def __init__(self, scene_rect: QRectF, grid_size: float = 10.0):
        self.scene_rect = scene_rect
        self.grid_size = grid_size
        self.width = int(scene_rect.width() / grid_size) + 1
        self.height = int(scene_rect.height() / grid_size) + 1
        
        # 障礙物管理
        self.blocked_points: Set[GridPoint] = set()
        self.quadtree = QuadTree(scene_rect)
        self.node_obstacles: List[QRectF] = []
    
    def world_to_grid(self, point: QPointF) -> GridPoint:
        """世界座標轉網格座標"""
        x = int((point.x() - self.scene_rect.left()) / self.grid_size)
        y = int((point.y() - self.scene_rect.top()) / self.grid_size)
        return GridPoint(max(0, min(x, self.width - 1)), max(0, min(y, self.height - 1)))
    
    def grid_to_world(self, grid_point: GridPoint) -> QPointF:
        """網格座標轉世界座標"""
        x = self.scene_rect.left() + grid_point.x * self.grid_size
        y = self.scene_rect.top() + grid_point.y * self.grid_size
        return QPointF(x, y)
    
    def add_node_obstacle(self, rect: QRectF, padding: float = 10.0):
        """新增節點障礙物 - 含 padding"""
        padded_rect = rect.adjusted(-padding, -padding, padding, padding)
        self.node_obstacles.append(padded_rect)
        self.quadtree.insert(padded_rect)
        
        # 標記網格點為阻塞
        top_left = self.world_to_grid(padded_rect.topLeft())
        bottom_right = self.world_to_grid(padded_rect.bottomRight())
        
        for x in range(top_left.x, bottom_right.x + 1):
            for y in range(top_left.y, bottom_right.y + 1):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.blocked_points.add(GridPoint(x, y))
    
    def is_blocked(self, grid_point: GridPoint) -> bool:
        """檢查網格點是否被阻塞"""
        return grid_point in self.blocked_points
    
    def get_neighbors(self, point: GridPoint, routing_style: RoutingStyle) -> List[GridPoint]:
        """獲取鄰近可達點"""
        neighbors = []
        
        if routing_style == RoutingStyle.ORTHOGONAL:
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 四方向
        elif routing_style == RoutingStyle.OCTILINEAR:
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0),
                         (1, 1), (1, -1), (-1, 1), (-1, -1)]  # 八方向
        else:  # POLYLINE 和 STRAIGHT
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0),
                         (1, 1), (1, -1), (-1, 1), (-1, -1)]  # 八方向
        
        for dx, dy in directions:
            new_x, new_y = point.x + dx, point.y + dy
            
            if (0 <= new_x < self.width and 0 <= new_y < self.height):
                new_point = GridPoint(new_x, new_y)
                if not self.is_blocked(new_point):
                    neighbors.append(new_point)
        
        return neighbors
    
    def find_exit_point(self, blocked_point: GridPoint) -> Optional[GridPoint]:
        """當起訖點位於障礙內時，找到最近的可通行位置（BFS）"""
        if not self.is_blocked(blocked_point):
            return blocked_point
        
        visited = {blocked_point}
        queue = deque([blocked_point])
        
        while queue:
            current = queue.popleft()
            
            # 檢查所有八方向鄰居
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0),
                          (1, 1), (1, -1), (-1, 1), (-1, -1)]:
                neighbor = GridPoint(current.x + dx, current.y + dy)
                
                if (0 <= neighbor.x < self.width and 0 <= neighbor.y < self.height
                    and neighbor not in visited):
                    
                    visited.add(neighbor)
                    
                    if not self.is_blocked(neighbor):
                        return neighbor
                    
                    queue.append(neighbor)
        
        return None  # 找不到出口


# ===================== A* 路徑搜尋演算法 =====================

class AStarPathfinder:
    """A* 路徑搜尋演算法 - 支援彎折懲罰與最大彎折數限制"""
    
    def __init__(self, grid: RoutingGrid):
        self.grid = grid
        self.cache: Dict[Tuple, List[GridPoint]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def find_path(self, start: GridPoint, goal: GridPoint,
                  routing_style: RoutingStyle,
                  bend_penalty: float = 0.1,
                  max_bends: int = 10) -> Optional[List[GridPoint]]:
        """使用A*演算法尋找最佳路徑"""
        
        # 檢查快取
        cache_key = (start, goal, routing_style)
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        # 處理起點和終點在障礙內的情況
        if self.grid.is_blocked(start):
            start = self.grid.find_exit_point(start)
            if start is None:
                return None
        
        if self.grid.is_blocked(goal):
            goal = self.grid.find_exit_point(goal)
            if goal is None:
                return None
        
        if start == goal:
            return [start]
        
        # A* 搜尋
        # 優先級佇列：(f_score, g_score, bends, point)
        open_set = [(0, 0, 0, start)]
        came_from: Dict[GridPoint, GridPoint] = {}
        g_score: Dict[GridPoint, float] = defaultdict(lambda: float('inf'))
        g_score[start] = 0
        bend_count: Dict[GridPoint, int] = defaultdict(int)
        
        visited = set()
        
        while open_set:
            current_f, current_g, current_bends, current = heapq.heappop(open_set)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == goal:
                path = self._reconstruct_path(came_from, current)
                self.cache[cache_key] = path
                return path
            
            # 檢查彎折數限制
            if current_bends > max_bends:
                continue
            
            for neighbor in self.grid.get_neighbors(current, routing_style):
                if neighbor in visited:
                    continue
                
                # 計算移動成本
                move_cost = self._calculate_move_cost(current, neighbor, routing_style)
                
                # 計算彎折成本
                bend_cost = 0
                new_bends = current_bends
                if current in came_from:
                    prev_point = came_from[current]
                    if self._is_bend(prev_point, current, neighbor):
                        bend_cost = bend_penalty
                        new_bends += 1
                
                tentative_g_score = g_score[current] + move_cost + bend_cost
                
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    bend_count[neighbor] = new_bends
                    f_score = tentative_g_score + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, tentative_g_score, new_bends, neighbor))
        
        return None  # 找不到路徑
    
    def _calculate_move_cost(self, current: GridPoint, neighbor: GridPoint,
                           routing_style: RoutingStyle) -> float:
        """計算移動成本"""
        dx = neighbor.x - current.x
        dy = neighbor.y - current.y
        
        # 基本距離成本
        if dx == 0 or dy == 0:  # 正交移動
            return 1.0
        else:  # 對角移動
            return math.sqrt(2)
    
    def _is_bend(self, prev: GridPoint, current: GridPoint, next_point: GridPoint) -> bool:
        """檢查是否產生彎折"""
        dir1 = (current.x - prev.x, current.y - prev.y)
        dir2 = (next_point.x - current.x, next_point.y - current.y)
        return dir1 != dir2
    
    def _heuristic(self, point: GridPoint, goal: GridPoint) -> float:
        """啟發函數 - 曼哈頓距離與歐幾里得距離的混合"""
        dx = abs(goal.x - point.x)
        dy = abs(goal.y - point.y)
        # 使用歐幾里得距離作為更准確的估計
        return math.sqrt(dx * dx + dy * dy)
    
    def _reconstruct_path(self, came_from: Dict[GridPoint, GridPoint],
                         current: GridPoint) -> List[GridPoint]:
        """重建路徑"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path
    
    def clear_cache(self):
        """清除快取"""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """取得快取統計資訊"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        return {
            'cache_size': len(self.cache),
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': hit_rate
        }


# ===================== 平行邊分離器 =====================

class ParallelEdgeManager:
    """平行邊分離管理器"""
    
    def __init__(self, base_spacing: float = 15.0):
        self.base_spacing = base_spacing
        self.edge_groups: Dict[Tuple[GridPoint, GridPoint], List] = defaultdict(list)
    
    def add_edge_path(self, start: GridPoint, end: GridPoint, path: List[GridPoint]):
        """添加邊線路徑到群組"""
        # 建立正規化的鍵（確保方向一致性）
        key = (start, end) if (start.x, start.y) <= (end.x, end.y) else (end, start)
        self.edge_groups[key].append(path)
    
    def get_separated_paths(self, start: GridPoint, end: GridPoint) -> List[List[GridPoint]]:
        """取得分離後的平行路徑"""
        key = (start, end) if (start.x, start.y) <= (end.x, end.y) else (end, start)
        paths = self.edge_groups[key]
        
        if len(paths) <= 1:
            return paths
        
        # 計算分離偏移
        separated_paths = []
        center_index = len(paths) // 2
        
        for i, path in enumerate(paths):
            offset = (i - center_index) * self.base_spacing
            separated_path = self._offset_path(path, offset)
            separated_paths.append(separated_path)
        
        return separated_paths
    
    def _offset_path(self, path: List[GridPoint], offset: float) -> List[GridPoint]:
        """對路徑施加偏移"""
        if len(path) < 2 or offset == 0:
            return path
        
        # 簡化實現：僅對路徑的中間點施加垂直偏移
        offset_path = []
        
        for i, point in enumerate(path):
            if i == 0 or i == len(path) - 1:
                # 保持端點不變
                offset_path.append(point)
            else:
                # 計算垂直偏移
                if i > 0 and i < len(path) - 1:
                    prev_point = path[i - 1]
                    next_point = path[i + 1]
                    
                    # 計算路徑方向
                    dx = next_point.x - prev_point.x
                    dy = next_point.y - prev_point.y
                    
                    if dx != 0 or dy != 0:
                        length = math.sqrt(dx * dx + dy * dy)
                        # 垂直向量
                        perp_x = -dy / length
                        perp_y = dx / length
                        
                        new_x = point.x + int(perp_x * offset)
                        new_y = point.y + int(perp_y * offset)
                        
                        offset_path.append(GridPoint(new_x, new_y))
                    else:
                        offset_path.append(point)
                else:
                    offset_path.append(point)
        
        return offset_path


# ===================== 主路由引擎 =====================

class RoutingEngine(QObject):
    """主路由引擎 - 整合所有路由功能"""
    
    # 信號
    routing_started = pyqtSignal()
    routing_completed = pyqtSignal(object)  # RoutingResult
    progress_updated = pyqtSignal(int)      # 進度百分比
    
    def __init__(self, scene_rect: QRectF, grid_size: float = 10.0):
        super().__init__()
        
        self.scene_rect = scene_rect
        self.grid_size = grid_size
        
        # 核心組件
        self.grid = RoutingGrid(scene_rect, grid_size)
        self.pathfinder = AStarPathfinder(self.grid)
        self.parallel_manager = ParallelEdgeManager()
        
        # 配置參數
        self.config = {
            'default_style': RoutingStyle.ORTHOGONAL,
            'node_padding': 10.0,
            'bend_penalty': 0.1,
            'max_bends': 10,
            'parallel_spacing': 15.0,
            'corner_radius': 5.0,
            'enable_smoothing': True,
            'enable_caching': True,
            'max_computation_time': 200  # ms
        }
        
        # 統計資訊
        self.stats = {
            'total_routes': 0,
            'successful_routes': 0,
            'failed_routes': 0,
            'average_time': 0.0,
            'total_bends': 0
        }
    
    def configure(self, **kwargs):
        """配置路由引擎參數"""
        self.config.update(kwargs)
    
    def add_node_obstacle(self, rect: QRectF, padding: float = None):
        """添加節點障礙物"""
        if padding is None:
            padding = self.config['node_padding']
        self.grid.add_node_obstacle(rect, padding)
    
    def clear_obstacles(self):
        """清除所有障礙物"""
        self.grid.blocked_points.clear()
        self.grid.node_obstacles.clear()
        self.grid.quadtree.clear()
    
    def route_edge(self, request: RoutingRequest) -> RoutingResult:
        """路由單條邊線"""
        self.routing_started.emit()
        start_time = time.time()
        
        try:
            # 直線路由的特殊處理
            if request.style == RoutingStyle.STRAIGHT:
                result = self._route_straight_line(request)
            else:
                result = self._route_with_pathfinding(request)
            
            computation_time = (time.time() - start_time) * 1000  # ms
            result.computation_time = computation_time
            
            # 更新統計
            self.stats['total_routes'] += 1
            if result.success:
                self.stats['successful_routes'] += 1
                self.stats['total_bends'] += result.bends
            else:
                self.stats['failed_routes'] += 1
            
            # 更新平均時間
            total_time = self.stats['average_time'] * (self.stats['total_routes'] - 1)
            self.stats['average_time'] = (total_time + computation_time) / self.stats['total_routes']
            
            self.routing_completed.emit(result)
            return result
            
        except Exception as e:
            # 錯誤處理：返回直線路由
            result = self._route_straight_line(request)
            result.success = False
            result.computation_time = (time.time() - start_time) * 1000
            self.routing_completed.emit(result)
            return result
    
    def _route_straight_line(self, request: RoutingRequest) -> RoutingResult:
        """直線路由實現"""
        src_center = request.source_rect.center()
        dst_center = request.target_rect.center()
        
        # 計算連接點
        src_point = self._find_connection_point(request.source_rect, dst_center)
        dst_point = self._find_connection_point(request.target_rect, src_center)
        
        # 建立直線路徑
        path = QPainterPath()
        path.moveTo(src_point)
        path.lineTo(dst_point)
        
        # 建立路由段
        segment = RouteSegment(
            src_point, dst_point,
            self._calculate_direction(src_point, dst_point)
        )
        
        return RoutingResult(
            path=path,
            segments=[segment],
            bends=0,
            length=segment.length(),
            computation_time=0.0,
            success=True,
            routing_style=RoutingStyle.STRAIGHT
        )
    
    def _route_with_pathfinding(self, request: RoutingRequest) -> RoutingResult:
        """使用路徑搜尋的路由實現"""
        src_center = request.source_rect.center()
        dst_center = request.target_rect.center()
        
        # 計算連接點
        src_point = self._find_connection_point(request.source_rect, dst_center)
        dst_point = self._find_connection_point(request.target_rect, src_center)
        
        # 轉換為網格座標
        src_grid = self.grid.world_to_grid(src_point)
        dst_grid = self.grid.world_to_grid(dst_point)
        
        # 路徑搜尋
        grid_path = self.pathfinder.find_path(
            src_grid, dst_grid, request.style,
            request.bend_penalty, request.max_bends
        )
        
        if grid_path is None:
            # 路徑搜尋失敗，回退到直線
            return self._route_straight_line(request)
        
        # 轉換為世界座標路徑
        world_path = [self.grid.grid_to_world(gp) for gp in grid_path]
        
        # 建立QPainterPath
        path = QPainterPath()
        path.moveTo(src_point)
        
        if world_path:
            path.lineTo(world_path[0])
            for point in world_path[1:]:
                path.lineTo(point)
        
        path.lineTo(dst_point)
        
        # 平滑處理
        if self.config['enable_smoothing'] and self.config['corner_radius'] > 0:
            path = self._smooth_path(path, self.config['corner_radius'])
        
        # 計算路由段和彎折數
        segments, bends = self._analyze_path(path)
        total_length = sum(seg.length() for seg in segments)
        
        return RoutingResult(
            path=path,
            segments=segments,
            bends=bends,
            length=total_length,
            computation_time=0.0,  # 會在主函數中設定
            success=True,
            routing_style=request.style
        )
    
    def _find_connection_point(self, node_rect: QRectF, target_center: QPointF) -> QPointF:
        """找到節點邊緣的最佳連接點"""
        center = node_rect.center()
        
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
    
    def _calculate_direction(self, start: QPointF, end: QPointF) -> Tuple[float, float]:
        """計算方向向量"""
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length > 0:
            return (dx / length, dy / length)
        else:
            return (0.0, 0.0)
    
    def _smooth_path(self, path: QPainterPath, radius: float) -> QPainterPath:
        """路徑平滑處理 - 圓角處理"""
        # 簡化實現：保持原路徑
        # 完整實現需要複雜的貝茲曲線插值
        return path
    
    def _analyze_path(self, path: QPainterPath) -> Tuple[List[RouteSegment], int]:
        """分析路徑，計算路由段和彎折數"""
        segments = []
        bends = 0
        
        if path.elementCount() < 2:
            return segments, bends
        
        # 提取路徑點
        points = []
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            points.append(QPointF(element.x, element.y))
        
        # 建立路由段
        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1]
            direction = self._calculate_direction(start, end)
            
            segment = RouteSegment(start, end, direction)
            segments.append(segment)
        
        # 計算彎折數
        for i in range(1, len(segments)):
            prev_dir = segments[i - 1].direction
            curr_dir = segments[i].direction
            
            # 檢查方向是否改變（容忍小誤差）
            if (abs(prev_dir[0] - curr_dir[0]) > 0.1 or
                abs(prev_dir[1] - curr_dir[1]) > 0.1):
                bends += 1
        
        return segments, bends
    
    def batch_route_edges(self, requests: List[RoutingRequest]) -> List[RoutingResult]:
        """批次路由多條邊線"""
        results = []
        
        for i, request in enumerate(requests):
            result = self.route_edge(request)
            results.append(result)
            
            # 發送進度更新
            progress = int((i + 1) / len(requests) * 100)
            self.progress_updated.emit(progress)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """取得統計資訊"""
        cache_stats = self.pathfinder.get_cache_stats()
        
        stats = dict(self.stats)
        stats.update(cache_stats)
        stats['average_bends'] = (self.stats['total_bends'] / max(1, self.stats['successful_routes']))
        
        # 效能分數計算
        hit_rate = cache_stats.get('hit_rate', 0)
        success_rate = self.stats['successful_routes'] / max(1, self.stats['total_routes'])
        performance_score = (hit_rate * 40 + success_rate * 60)
        stats['performance_score'] = performance_score
        
        return stats
    
    def clear_cache(self):
        """清除路徑快取"""
        if self.config['enable_caching']:
            self.pathfinder.clear_cache()
    
    def reset_statistics(self):
        """重設統計資訊"""
        self.stats = {
            'total_routes': 0,
            'successful_routes': 0,
            'failed_routes': 0,
            'average_time': 0.0,
            'total_bends': 0
        }