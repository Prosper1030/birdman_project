"""
Advanced Edge Routing Engine for DSM Editor - yEd Style Implementation
實現真正的正交路由和避障功能

第一階段升級重點：
1. Gate 機制讓起終點能走出節點
2. 可見性圖構建與正交連線
3. 方向感知的 A* 路徑搜尋與轉彎代價
4. ROI 優化與全域擁塞感知的 sequential routing
5. 為後續 rip-up / lane ordering 預留批次入口
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import QPointF, QRectF


CardinalDirection = Optional[str]
SegmentEndpoint = Tuple[int, int]
SegmentKey = Tuple[SegmentEndpoint, SegmentEndpoint]


@dataclass
class RoutingNode:
    """路由圖中的節點。"""

    x: float
    y: float
    node_id: str = ""
    node_type: str = "waypoint"  # "source", "target", "waypoint", "gate", "corner"

    def __hash__(self):
        return hash((round(self.x, 2), round(self.y, 2), self.node_id))

    def __eq__(self, other):
        return abs(self.x - other.x) < 0.1 and abs(self.y - other.y) < 0.1


@dataclass
class EdgeRouteRequest:
    """批次路由時的單條邊需求。"""

    edgeKey: Any
    startPos: QPointF
    endPos: QPointF
    obstacles: List[QRectF]
    previousPath: Optional[List[QPointF]] = None


class VisibilityGraph:
    """正交可見性圖 - 支援 gate 機制。"""

    def __init__(self, grid_pitch: float = 20):
        self.nodes: Set[RoutingNode] = set()
        self.adjacency: Dict[RoutingNode, List[Tuple[RoutingNode, float]]] = {}
        self.obstacles: List[QRectF] = []
        self.grid_pitch = grid_pitch  # 格點對齊

    def add_obstacle(self, rect: QRectF, obstacle_id: str = ""):
        """添加障礙物並創建角點和中點。"""
        self.obstacles.append(rect)

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
        """添加節點到圖中。"""
        node.x = round(node.x / self.grid_pitch) * self.grid_pitch
        node.y = round(node.y / self.grid_pitch) * self.grid_pitch

        self.nodes.add(node)
        if node not in self.adjacency:
            self.adjacency[node] = []

    def inject_gate_for_point(
        self, pos: QPointF, gate_type: str = "gate"
    ) -> Optional[RoutingNode]:
        """
        為指定點注入 gate 節點，讓它能走出包含它的障礙物節點。
        """
        host_obstacle = None
        for obstacle in self.obstacles:
            if obstacle.contains(pos):
                host_obstacle = obstacle
                break

        if not host_obstacle:
            gate_node = RoutingNode(pos.x(), pos.y(), f"free_{gate_type}", gate_type)
            self.add_node(gate_node)
            return gate_node

        distances = {
            "top": abs(pos.y() - host_obstacle.top()),
            "bottom": abs(pos.y() - host_obstacle.bottom()),
            "left": abs(pos.x() - host_obstacle.left()),
            "right": abs(pos.x() - host_obstacle.right()),
        }
        closest_side = min(distances, key=distances.get)

        if closest_side in ("top", "bottom"):
            gate_y = (
                host_obstacle.top()
                if closest_side == "top"
                else host_obstacle.bottom()
            )
            gate_node = RoutingNode(pos.x(), gate_y, f"gate_{closest_side}", gate_type)
        else:
            gate_x = (
                host_obstacle.left()
                if closest_side == "left"
                else host_obstacle.right()
            )
            gate_node = RoutingNode(gate_x, pos.y(), f"gate_{closest_side}", gate_type)

        self.add_node(gate_node)
        return gate_node

    def build_visibility_edges(self):
        """構建正交可見性邊。"""
        self.adjacency = {node: [] for node in self.nodes}
        nodes_list = sorted(
            self.nodes,
            key=lambda node: (node.x, node.y, node.node_type, node.node_id),
        )

        for index, node1 in enumerate(nodes_list):
            for node2 in nodes_list[index + 1 :]:
                if self._is_orthogonal(node1, node2) and self._is_visible(node1, node2):
                    cost = self._calculate_edge_cost(node1, node2)
                    self._add_edge(node1, node2, cost)
                    self._add_edge(node2, node1, cost)

    def _is_orthogonal(self, node1: RoutingNode, node2: RoutingNode) -> bool:
        """檢查兩節點是否在正交方向。"""
        return abs(node1.x - node2.x) < 0.1 or abs(node1.y - node2.y) < 0.1

    def _is_visible(self, node1: RoutingNode, node2: RoutingNode) -> bool:
        """檢查兩節點間是否可見（無障礙物阻擋）。"""
        min_x, max_x = min(node1.x, node2.x), max(node1.x, node2.x)
        min_y, max_y = min(node1.y, node2.y), max(node1.y, node2.y)

        line_rect = QRectF(min_x - 1, min_y - 1, max_x - min_x + 2, max_y - min_y + 2)

        for obstacle in self.obstacles:
            if obstacle.intersects(line_rect) and self._line_crosses_obstacle_interior(
                node1, node2, obstacle
            ):
                return False

        return True

    def _line_crosses_obstacle_interior(
        self, node1: RoutingNode, node2: RoutingNode, obstacle: QRectF
    ) -> bool:
        """檢查線段是否穿越障礙物內部。"""
        steps = 5
        for index in range(1, steps):
            ratio = index / steps
            sample_x = node1.x + ratio * (node2.x - node1.x)
            sample_y = node1.y + ratio * (node2.y - node1.y)

            if (
                obstacle.left() < sample_x < obstacle.right()
                and obstacle.top() < sample_y < obstacle.bottom()
            ):
                return True

        return False

    def _calculate_edge_cost(self, node1: RoutingNode, node2: RoutingNode) -> float:
        """計算基礎邊成本，轉彎代價改由 stateful A* 統一處理。"""
        return abs(node2.x - node1.x) + abs(node2.y - node1.y)

    def _add_edge(self, from_node: RoutingNode, to_node: RoutingNode, cost: float):
        """添加有向邊到鄰接表。"""
        if from_node not in self.adjacency:
            self.adjacency[from_node] = []
        self.adjacency[from_node].append((to_node, cost))

    @staticmethod
    def get_direction(
        from_node: RoutingNode, to_node: RoutingNode
    ) -> CardinalDirection:
        """回傳正交線段方向。"""
        if abs(from_node.x - to_node.x) < 0.1:
            return "S" if to_node.y > from_node.y else "N"
        if abs(from_node.y - to_node.y) < 0.1:
            return "E" if to_node.x > from_node.x else "W"
        return None

    @staticmethod
    def _point_key(x: float, y: float) -> SegmentEndpoint:
        """將浮點座標壓成穩定的 segment key。"""
        return (int(round(x * 10)), int(round(y * 10)))

    def make_segment_key(self, node1: RoutingNode, node2: RoutingNode) -> SegmentKey:
        """產生與方向無關的 segment key，供擁塞統計使用。"""
        endpoint1 = self._point_key(node1.x, node1.y)
        endpoint2 = self._point_key(node2.x, node2.y)
        return tuple(sorted((endpoint1, endpoint2)))  # type: ignore[return-value]


class AStarPathfinder:
    """方向感知的 A* 路徑搜尋器。"""

    def __init__(self, visibility_graph: VisibilityGraph):
        self.graph = visibility_graph

    def find_path(
        self,
        start: RoutingNode,
        goal: RoutingNode,
        occupancy: Optional[Dict[SegmentKey, int]] = None,
        previous_segments: Optional[Set[SegmentKey]] = None,
        bend_penalty: float = 12.0,
        congestion_weight: float = 18.0,
        stability_weight: float = 4.0,
    ) -> List[RoutingNode]:
        """使用 stateful A* 搜尋最佳路徑。"""
        start_state = (start, None)
        counter = 0
        open_set: List[Tuple[float, float, int, RoutingNode, CardinalDirection]] = [
            (self._heuristic(start, goal), 0.0, counter, start, None)
        ]
        came_from: Dict[
            Tuple[RoutingNode, CardinalDirection],
            Tuple[RoutingNode, CardinalDirection],
        ] = {}
        g_cost: Dict[Tuple[RoutingNode, CardinalDirection], float] = {
            start_state: 0.0
        }

        while open_set:
            _, current_g, _, current_node, incoming_dir = heapq.heappop(open_set)
            current_state = (current_node, incoming_dir)

            if current_g > g_cost.get(current_state, float("inf")) + 1e-9:
                continue

            if current_node == goal:
                return self._reconstruct_path(came_from, current_state)

            for neighbor, base_cost in self.graph.adjacency.get(current_node, []):
                direction = self.graph.get_direction(current_node, neighbor)
                if direction is None:
                    continue

                segment_key = self.graph.make_segment_key(current_node, neighbor)
                bend_cost = (
                    bend_penalty
                    if incoming_dir is not None and incoming_dir != direction
                    else 0.0
                )
                congestion_cost = self._compute_congestion_cost(
                    segment_key, occupancy, congestion_weight
                )
                stability_cost = (
                    stability_weight
                    if previous_segments is not None
                    and segment_key not in previous_segments
                    else 0.0
                )
                tentative_g = (
                    current_g + base_cost + bend_cost + congestion_cost + stability_cost
                )

                neighbor_state = (neighbor, direction)
                if tentative_g + 1e-9 >= g_cost.get(neighbor_state, float("inf")):
                    continue

                came_from[neighbor_state] = current_state
                g_cost[neighbor_state] = tentative_g
                counter += 1
                heuristic = self._heuristic(neighbor, goal)
                heapq.heappush(
                    open_set,
                    (tentative_g + heuristic, tentative_g, counter, neighbor, direction),
                )

        return []

    def _heuristic(self, node: RoutingNode, goal: RoutingNode) -> float:
        """啟發式函數 - 曼哈頓距離。"""
        return abs(goal.x - node.x) + abs(goal.y - node.y)

    def _reconstruct_path(
        self,
        came_from: Dict[
            Tuple[RoutingNode, CardinalDirection],
            Tuple[RoutingNode, CardinalDirection],
        ],
        current_state: Tuple[RoutingNode, CardinalDirection],
    ) -> List[RoutingNode]:
        """從 state graph 重建節點路徑。"""
        path = [current_state[0]]
        while current_state in came_from:
            current_state = came_from[current_state]
            path.append(current_state[0])
        return path[::-1]

    def _compute_congestion_cost(
        self,
        segment_key: SegmentKey,
        occupancy: Optional[Dict[SegmentKey, int]],
        congestion_weight: float,
    ) -> float:
        """使用增量擁塞成本，讓後續邊傾向分散到較空的走廊。"""
        if occupancy is None:
            return 0.0
        load = occupancy.get(segment_key, 0)
        return congestion_weight * float(2 * load + 1)


class AdvancedEdgeRouter:
    """高級邊線路由器 - 第一階段導入批次與擁塞感知。"""

    def __init__(self):
        self.visibility_graph = VisibilityGraph(grid_pitch=20)
        self.pathfinder = AStarPathfinder(self.visibility_graph)
        self.min_clearance = 8
        self.current_obstacles: List[QRectF] = []
        self.bendPenalty = 12.0
        self.congestionWeight = 18.0
        self.stabilityWeight = 4.0
        self.lastOccupancy: Dict[SegmentKey, int] = {}

    def route_edge(
        self,
        start_pos: QPointF,
        end_pos: QPointF,
        obstacles: Optional[List[QRectF]] = None,
        occupancy: Optional[Dict[SegmentKey, int]] = None,
        previous_path: Optional[List[QPointF]] = None,
    ) -> List[QPointF]:
        """
        路由單條邊線 - 主要接口。
        """
        if obstacles is None:
            obstacles = []

        roi_obstacles = self._filter_obstacles_by_roi(start_pos, end_pos, obstacles)
        self._rebuild_visibility_graph(roi_obstacles)

        start_gate = self.visibility_graph.inject_gate_for_point(start_pos, "start")
        end_gate = self.visibility_graph.inject_gate_for_point(end_pos, "end")

        if not start_gate or not end_gate:
            return [start_pos, end_pos]

        self.visibility_graph.build_visibility_edges()
        previous_segments = self._path_points_to_segment_keys(previous_path)
        path_nodes = self.pathfinder.find_path(
            start_gate,
            end_gate,
            occupancy=occupancy,
            previous_segments=previous_segments,
            bend_penalty=self.bendPenalty,
            congestion_weight=self.congestionWeight,
            stability_weight=self.stabilityWeight,
        )

        if len(path_nodes) < 2:
            return [start_pos, end_pos]

        path_points = [QPointF(node.x, node.y) for node in path_nodes]
        path_points[0] = start_pos
        path_points[-1] = end_pos
        return self._simplify_path(path_points)

    def route_edges(self, requests: List[EdgeRouteRequest]) -> Dict[Any, List[QPointF]]:
        """
        以 sequential routing 依序處理多條邊，並把既有路徑 load 納入成本。
        """
        if not requests:
            return {}

        occupancy: Dict[SegmentKey, int] = {}
        results: Dict[Any, List[QPointF]] = {}
        ordered_requests = sorted(
            requests,
            key=self._estimate_route_difficulty,
            reverse=True,
        )

        for request in ordered_requests:
            path_points = self.route_edge(
                request.startPos,
                request.endPos,
                obstacles=request.obstacles,
                occupancy=occupancy,
                previous_path=request.previousPath,
            )
            results[request.edgeKey] = path_points
            self._commit_path_to_occupancy(path_points, occupancy)

        self.lastOccupancy = occupancy.copy()
        return results

    def _estimate_route_difficulty(self, request: EdgeRouteRequest) -> float:
        """簡單的難度估計，先排長距離且障礙多的邊。"""
        manhattan = abs(request.endPos.x() - request.startPos.x()) + abs(
            request.endPos.y() - request.startPos.y()
        )
        return manhattan + len(request.obstacles) * 40.0

    def _commit_path_to_occupancy(
        self, path_points: List[QPointF], occupancy: Dict[SegmentKey, int]
    ) -> None:
        """把已提交路徑寫入 occupancy，供後續邊計算擁塞成本。"""
        for index in range(len(path_points) - 1):
            point1 = path_points[index]
            point2 = path_points[index + 1]
            segment_key = self._make_segment_key_from_points(point1, point2)
            occupancy[segment_key] = occupancy.get(segment_key, 0) + 1

    def _make_segment_key_from_points(
        self, point1: QPointF, point2: QPointF
    ) -> SegmentKey:
        """將 QPointF 路徑段轉成與方向無關的 key。"""
        endpoint1 = self.visibility_graph._point_key(point1.x(), point1.y())
        endpoint2 = self.visibility_graph._point_key(point2.x(), point2.y())
        return tuple(sorted((endpoint1, endpoint2)))  # type: ignore[return-value]

    def _path_points_to_segment_keys(
        self, path_points: Optional[List[QPointF]]
    ) -> Optional[Set[SegmentKey]]:
        """將既有 polyline 轉成 segment key 集合，供穩定性成本使用。"""
        if not path_points or len(path_points) < 2:
            return None

        segments: Set[SegmentKey] = set()
        for index in range(len(path_points) - 1):
            segments.add(
                self._make_segment_key_from_points(
                    path_points[index], path_points[index + 1]
                )
            )
        return segments

    def _simplify_path(self, path_points: List[QPointF]) -> List[QPointF]:
        """移除重複點與共線中繼點，避免回傳過度破碎的 polyline。"""
        if not path_points:
            return []

        deduped = [path_points[0]]
        for point in path_points[1:]:
            last_point = deduped[-1]
            if abs(point.x() - last_point.x()) > 0.1 or abs(point.y() - last_point.y()) > 0.1:
                deduped.append(point)

        index = 1
        while index + 1 < len(deduped):
            point_a = deduped[index - 1]
            point_b = deduped[index]
            point_c = deduped[index + 1]
            same_x = abs(point_a.x() - point_b.x()) < 0.1 and abs(point_b.x() - point_c.x()) < 0.1
            same_y = abs(point_a.y() - point_b.y()) < 0.1 and abs(point_b.y() - point_c.y()) < 0.1
            if same_x or same_y:
                deduped.pop(index)
                continue
            index += 1
        return deduped

    def _rebuild_visibility_graph(self, obstacles: List[QRectF]):
        """重建可見性圖。"""
        self.visibility_graph = VisibilityGraph(grid_pitch=20)

        for index, obstacle in enumerate(obstacles):
            expanded = obstacle.adjusted(
                -self.min_clearance,
                -self.min_clearance,
                self.min_clearance,
                self.min_clearance,
            )
            self.visibility_graph.add_obstacle(expanded, f"obs_{index}")

        self.pathfinder = AStarPathfinder(self.visibility_graph)

    def _filter_obstacles_by_roi(
        self,
        start_pos: QPointF,
        end_pos: QPointF,
        obstacles: List[QRectF],
        padding: float = 200,
    ) -> List[QRectF]:
        """ROI 過濾：只保留搜尋區域內的障礙物。"""
        min_x = min(start_pos.x(), end_pos.x()) - padding
        max_x = max(start_pos.x(), end_pos.x()) + padding
        min_y = min(start_pos.y(), end_pos.y()) - padding
        max_y = max(start_pos.y(), end_pos.y()) + padding

        roi_rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        filtered = [obstacle for obstacle in obstacles if roi_rect.intersects(obstacle)]
        print(f"[AdvancedRouter] ROI 過濾：{len(obstacles)} -> {len(filtered)} 障礙物")
        return filtered
