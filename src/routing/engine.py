from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPointF, QRectF, QLineF
from PyQt5.QtGui import QPainterPath


class RoutingStyle(Enum):
    STRAIGHT = "STRAIGHT"
    ORTHOGONAL = "ORTHOGONAL"
    OCTILINEAR = "OCTILINEAR"
    POLYLINE = "POLYLINE"


@dataclass
class RoutingConfig:
    grid_size: float = 20.0
    node_padding: float = 8.0
    parallel_spacing: float = 10.0
    bend_penalty: float = 1.0
    max_bends: int = 6
    avoid_obstacles: bool = True


@dataclass
class RoutingResult:
    path: QPainterPath
    bends: int
    length: float
    success: bool
    segments: List[QLineF]


class YEdStyleEdgeRouter:
    """yEd 風格路由器：目前以直線為主，提供障礙物 API 相容性。"""

    def __init__(self, scene_rect: QRectF, config: RoutingConfig):
        self.scene_rect = scene_rect
        self.config = config
        self._obstacles: List[QRectF] = []

    def add_node_obstacle(self, rect: QRectF, padding: float | None = None) -> None:
        """
        Back-compat: 某些舊呼叫點會傳 (rect, padding)。
        若 padding 為 None，使用 self.config.node_padding。
        會將 rect 以 padding 進行膨脹，並以幾何相等去重。
        """
        pad = float(self.config.node_padding if padding is None else padding)
        inflated = rect.adjusted(-pad, -pad, pad, pad)
        # 幾何去重：以 QRectF 等值判斷是否已存在
        for r in self._obstacles:
            if r == inflated:
                return
        self._obstacles.append(inflated)

    def register_node_obstacles(self, rects: List[QRectF]):
        # 重建障礙物清單（使用 add_node_obstacle 以統一膨脹與去重邏輯）
        self._obstacles = []
        for r in rects:
            self.add_node_obstacle(r)

    # -----------------------------
    # 公開 API
    # -----------------------------
    def route(self, src: QPointF, dst: QPointF, style: RoutingStyle) -> RoutingResult:
        # Step 1: 僅直線 stub；確保即使 self._obstacles 為空也能安全運作
        # 未在此步驟啟用 A* 或使用障礙物，僅確保 API 相容與安全
        return self._straight(src, dst)

    def route_many(self, edges: List[Tuple[QPointF, QPointF]]) -> List[RoutingResult]:
        return [self.route(s, d, RoutingStyle.ORTHOGONAL) for (s, d) in edges]

    # -----------------------------
    # 直線與正交路由實作
    # -----------------------------
    def _straight(self, src: QPointF, dst: QPointF) -> RoutingResult:
        path = QPainterPath(src)
        path.lineTo(dst)
        seg = QLineF(src, dst)
        return RoutingResult(path=path, bends=0, length=seg.length(), success=True, segments=[seg])

    def _route_orthogonal(self, src: QPointF, dst: QPointF) -> RoutingResult:
        grid, cols, rows, origin_x, origin_y, gs = self._build_grid()

        def to_idx(p: QPointF) -> Tuple[int, int]:
            x = max(origin_x, min(p.x(), origin_x + cols * gs - 1e-6))
            y = max(origin_y, min(p.y(), origin_y + rows * gs - 1e-6))
            ci = int((x - origin_x) // gs)
            rj = int((y - origin_y) // gs)
            return ci, rj

        def to_pt(i: int, j: int) -> QPointF:
            # 使用格點中心
            return QPointF(origin_x + (i + 0.5) * gs, origin_y + (j + 0.5) * gs)

        start = to_idx(src)
        goal = to_idx(dst)

        # 確保起訖可走
        if 0 <= start[0] < cols and 0 <= start[1] < rows:
            grid[start[1]][start[0]] = False
        if 0 <= goal[0] < cols and 0 <= goal[1] < rows:
            grid[goal[1]][goal[0]] = False

        path_indices = self._a_star(grid, cols, rows, start, goal, gs)
        if not path_indices:
            return RoutingResult(path=QPainterPath(src), bends=0, length=0.0, success=False, segments=[QLineF(src, dst)])

        # 轉為點並壓縮共線段
        pts = [to_pt(i, j) for (i, j) in path_indices]
        compressed = self._compress_collinear(pts)
        bends = max(0, len(compressed) - 2)
        if bends > self.config.max_bends:
            # 超過上限就回退直線（保守）
            straight = self._straight(src, dst)
            return RoutingResult(path=straight.path, bends=0, length=straight.length, success=False, segments=straight.segments)

        # 組 QPainterPath 與 segments
        path = QPainterPath(compressed[0])
        segments: List[QLineF] = []
        total_len = 0.0
        for k in range(1, len(compressed)):
            path.lineTo(compressed[k])
            seg = QLineF(compressed[k - 1], compressed[k])
            segments.append(seg)
            total_len += seg.length()

        return RoutingResult(path=path, bends=bends, length=total_len, success=True, segments=segments)

    # -----------------------------
    # Grid 與 A* 實作
    # -----------------------------
    def _build_grid(self) -> Tuple[List[List[bool]], int, int, float, float, float]:
        sr = self.scene_rect
        gs = max(2.0, float(self.config.grid_size))
        cols = max(2, int(sr.width() // gs) + 2)
        rows = max(2, int(sr.height() // gs) + 2)
        origin_x = sr.left()
        origin_y = sr.top()

        # grid[j][i] = True 表示被阻擋
        grid = [[False for _ in range(cols)] for _ in range(rows)]

        inflated: List[QRectF] = []
        pad = float(self.config.node_padding)
        for r in self._obstacles:
            inflated.append(r.adjusted(-pad, -pad, pad, pad))

        # 將 obstacle 中心落在格點中心者標為阻擋
        for j in range(rows):
            cy = origin_y + (j + 0.5) * gs
            for i in range(cols):
                cx = origin_x + (i + 0.5) * gs
                p = QPointF(cx, cy)
                for ob in inflated:
                    if ob.contains(p):
                        grid[j][i] = True
                        break

        return grid, cols, rows, origin_x, origin_y, gs

    def _a_star(
        self,
        grid: List[List[bool]],
        cols: int,
        rows: int,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        gs: float,
    ) -> List[Tuple[int, int]]:
        from heapq import heappush, heappop

        # 方向: (dx, dy) 與索引
        dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)]

        def in_bounds(i: int, j: int) -> bool:
            return 0 <= i < cols and 0 <= j < rows and not grid[j][i]

        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
            # 曼哈頓距離 * gs
            return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * gs

        # 狀態包含方向以計算轉彎成本
        start_state = (start[0], start[1], -1)  # dir=-1 表示起點無方向
        goal_xy = (goal[0], goal[1])

        open_heap: List[Tuple[float, Tuple[int, int, int]]] = []
        heappush(open_heap, (0.0, start_state))

        g_score: Dict[Tuple[int, int, int], float] = {start_state: 0.0}
        came: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}

        best_dir_by_cell: Dict[Tuple[int, int], float] = {(start[0], start[1]): 0.0}

        while open_heap:
            _, (ci, cj, cdir) = heappop(open_heap)
            if (ci, cj) == goal_xy:
                # 重建路徑: 取出最後一個方向狀態
                end_state = (ci, cj, cdir)
                return self._reconstruct_path(came, end_state)

            for ndir, (dx, dy) in enumerate(dirs):
                ni, nj = ci + dx, cj + dy
                if not in_bounds(ni, nj):
                    continue

                step_cost = gs
                if cdir != -1 and ndir != cdir:
                    step_cost += float(self.config.bend_penalty)
                tentative_g = g_score[(ci, cj, cdir)] + step_cost

                state_n = (ni, nj, ndir)
                if tentative_g < g_score.get(state_n, float("inf")):
                    g_score[state_n] = tentative_g
                    came[state_n] = (ci, cj, cdir)
                    f = tentative_g + heuristic((ni, nj), goal_xy)
                    heappush(open_heap, (f, state_n))

        return []  # 無路徑

    def _reconstruct_path(
        self,
        came: Dict[Tuple[int, int, int], Tuple[int, int, int]],
        end_state: Tuple[int, int, int],
    ) -> List[Tuple[int, int]]:
        path: List[Tuple[int, int]] = []
        cur = end_state
        while cur in came:
            path.append((cur[0], cur[1]))
            cur = came[cur]
        path.append((cur[0], cur[1]))
        path.reverse()
        # 移除重複連續點（若有）
        dedup: List[Tuple[int, int]] = []
        for pt in path:
            if not dedup or dedup[-1] != pt:
                dedup.append(pt)
        return dedup

    def _compress_collinear(self, pts: List[QPointF]) -> List[QPointF]:
        if len(pts) <= 2:
            return pts
        out: List[QPointF] = [pts[0]]
        def sign(x: float) -> int:
            return 0 if abs(x) < 1e-6 else (1 if x > 0 else -1)
        prev_dx = sign(pts[1].x() - pts[0].x())
        prev_dy = sign(pts[1].y() - pts[0].y())
        for k in range(1, len(pts) - 1):
            cur_dx = sign(pts[k + 1].x() - pts[k].x())
            cur_dy = sign(pts[k + 1].y() - pts[k].y())
            if cur_dx != prev_dx or cur_dy != prev_dy:
                out.append(pts[k])
            prev_dx, prev_dy = cur_dx, cur_dy
        out.append(pts[-1])
        return out
