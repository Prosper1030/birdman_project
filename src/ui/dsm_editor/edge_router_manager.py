"""
yEd 風格邊線路由管理器
Edge Router Manager for yEd-style Routing

管理兩種路由模式：
- 日常互動：直線或簡單折線
- 佈局觸發：正交 90° 路由

實現用戶需求：
- 平時拖拽：只做直線更新
- 點擊佈局：節點佈局 + 全圖正交路由
- 手動調整邊線：保持用戶指定形狀直到下次佈局
- 計算失敗：安全回退到直線
"""

import time
from typing import List, Dict, Tuple, Set, Optional
from enum import Enum
try:
    from PyQt5.QtCore import QPointF, QRectF, QObject  # type: ignore
except Exception:
    # 提供最小替身，僅供靜態分析/無 PyQt5 環境下使用
    class QObject:  # type: ignore
        pass
    class QPointF:  # type: ignore
        def __init__(self, x=0.0, y=0.0):
            self._x = float(x)
            self._y = float(y)
        def x(self) -> float:
            return self._x
        def y(self) -> float:
            return self._y
    class QRectF:  # type: ignore
        def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0):
            self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)
        def left(self) -> float:
            return self._x
        def right(self) -> float:
            return self._x + self._w
        def top(self) -> float:
            return self._y
        def bottom(self) -> float:
            return self._y + self._h
        def intersects(self, other: 'QRectF') -> bool:
            return not (
                self.right() < other.left() or other.right() < self.left() or
                self.bottom() < other.top() or other.bottom() < self.top()
            )
        def adjusted(self, dx1: float, dy1: float, dx2: float, dy2: float) -> 'QRectF':
            return QRectF(
                self._x + dx1,
                self._y + dy1,
                self._w + (dx2 - dx1),
                self._h + (dy2 - dy1),
            )


class RoutingMode(Enum):
    """路由模式枚舉"""
    INTERACTIVE = "interactive"  # 日常互動：直線模式
    LAYOUT = "layout"            # 佈局觸發：正交路由模式


# TB 版面規範常數
GRID = 16
PORT_STUB = 16
CLEAR = 12


class EdgeRouterManager(QObject):
    """
    TB 版面規範的邊線路由管理器
    
    核心功能：
    1. 嚴格 Manhattan 路由（僅水平/垂直）
    2. 同軸例外（同 x 允許直線）
    3. Port stub 避免轉角貼邊
    4. 末段必為垂直（TB 版面）
    5. 高級路由僅處理中段，保留首尾框架
    """
    
    def __init__(self, scene=None, timeout_ms: int = 2000):
        """
        初始化路由管理器
        
        Args:
            scene: DSM 場景對象
            timeout_ms: 路由計算超時時間（毫秒）
        """
        super().__init__()
        self.scene = scene
        self.timeout_ms = timeout_ms
        
        # 路由狀態
        self.current_mode = RoutingMode.INTERACTIVE
        
        # 手動調整的邊線（用戶希望保持的形狀）
        self.user_modified_edges: Set[Tuple[str, str]] = set()
        
        # 路由器組件
        self._simple_router = None
        self._orthogonal_router = None
        
        # 性能監控
        self.last_routing_time = 0
        self.routing_stats = {
            'interactive_count': 0,
            'layout_count': 0,
            'timeout_count': 0,
            'fallback_count': 0
        }
        # 進階 TB 帶狀路由開關（預設關閉以維持舊行為）
        self._band_router_enabled = False
    
    def _snap(self, v: float, g: int = GRID) -> float:
        """將數值對齊到格點"""
        return round(v / g) * g
    
    def _port_side(self, node, pos: QPointF) -> str:
        """回傳 'top'|'right'|'bottom'|'left'；以距離邊界最近為準。"""
        if not node or not hasattr(node, 'sceneBoundingRect'):
            return 'bottom'
        
        r = node.sceneBoundingRect()
        d = {
            'left': abs(pos.x() - r.left()),
            'right': abs(pos.x() - r.right()),
            'top': abs(pos.y() - r.top()),
            'bottom': abs(pos.y() - r.bottom())
        }
        return min(d, key=d.get)
    
    def _stub(self, p: QPointF, side: str, d: float = PORT_STUB) -> QPointF:
        """產生 port stub 點"""
        if side == 'top':
            return QPointF(p.x(), p.y() - d)
        if side == 'bottom':
            return QPointF(p.x(), p.y() + d)
        if side == 'left':
            return QPointF(p.x() - d, p.y())
        return QPointF(p.x() + d, p.y())
    
    def _dedupe_keep_elbow(self, pts):
        """去掉連續重複點，但保留至少一個轉角（避免被簡成兩點）。"""
        if not pts:
            return []
        
        out = [pts[0]]
        for q in pts[1:]:
            if abs(q.x() - out[-1].x()) > 0.1 or abs(q.y() - out[-1].y()) > 0.1:
                out.append(q)
        
        if len(out) == 2:
            a, b = out
            out = [a, QPointF(a.x(), b.y()), b]  # 保底 L 型
        
        return out
    
    # 兼容舊測試 API
    def _infer_port_side(self, node, pos: QPointF) -> str:
        return self._port_side(node, pos)

    def _make_stub_point(self, pos: QPointF, side: str, length: float = None) -> QPointF:
        return self._stub(pos, side, PORT_STUB if length is None else length)
    
    def _ensure_manhattan(self, pts):
        """將任意點列強制轉為正交：若一段既非同 x 也非同 y，插入中繼點。"""
        if not pts:
            return []
        out = [pts[0]]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if abs(a.x() - b.x()) < 0.1 or abs(a.y() - b.y()) < 0.1:
                out.append(b)
            else:
                mid = QPointF(a.x(), b.y())  # HV（TB 方向）
                out.extend([mid, b])
        return self._dedupe_keep_elbow(out)

    def _route_tb_canonical(self, edge_item, ps: QPointF, pt: QPointF):
        """
        TB 版面規範化路徑：
        - 若 x 相同：允許單段垂直直線（同軸例外）
        - 否則：ps→(stub)→水平層(y_mid)→(x_t, y_mid)→(stub)→pt，末段必垂直
        """
        # 同軸例外（允許直線）
        if abs(ps.x() - pt.x()) < 0.1:
            return [ps, pt]

        # 端點與邊向
        src = getattr(edge_item, 'src', getattr(edge_item, 'source_node', None))
        dst = getattr(edge_item, 'dst', getattr(edge_item, 'target_node', None))
        s_side = self._port_side(src, ps) if src else 'bottom'
        t_side = self._port_side(dst, pt) if dst else 'top'

        # stub：避免轉角貼邊
        s_out = self._stub(ps, s_side, PORT_STUB)
        t_in = self._stub(pt, t_side, PORT_STUB)

        # 轉彎高度（中段）
        y_low = s_out.y() + CLEAR
        y_high = t_in.y() - CLEAR
        y_mid = self._snap(max(min((s_out.y() + t_in.y()) * 0.5, y_high), y_low))

        mid1 = QPointF(s_out.x(), y_mid)     # 垂直到層架
        mid2 = QPointF(t_in.x(), y_mid)      # 水平到目標 x（應為 stub 入口點）
        path = [ps, s_out, mid1, mid2, t_in, pt]

        return self._ensure_manhattan(path)

    def _compute_nodes_overlap_x(self, node_a, node_b) -> Tuple[float, float]:
        """計算兩個節點在場景座標中的水平重疊 [L,R]；
        若任一節點不存在或無法取得邊界，回傳 (0, 0)。
        """
        def _scene_rect(n) -> Optional['QRectF']:
            if not n:
                return None
            try:
                if hasattr(n, 'sceneBoundingRect'):
                    return n.sceneBoundingRect()
                if hasattr(n, 'boundingRect') and hasattr(n, 'mapRectToScene'):
                    return n.mapRectToScene(n.boundingRect())
            except Exception:
                return None
            return None

        ra = _scene_rect(node_a)
        rb = _scene_rect(node_b)
        if not ra or not rb:
            return (0.0, 0.0)
        L = max(ra.left(), rb.left())
        R = min(ra.right(), rb.right())
        if R < L:
            return (0.0, 0.0)
        return (float(L), float(R))
    
    def _tb_port_sides(self, ps: QPointF, pt: QPointF) -> Tuple[str, str]:
        """依 TB 規則選擇來源/目標 port 側邊（N+1 規則）：
        - 從上到下：src 用 bottom，dst 用 top
        - 從下到上：src 用 top，dst 用 bottom
        """
        if ps.y() <= pt.y():
            return 'bottom', 'top'
        else:
            return 'top', 'bottom'

    def _route_tb_with_y(self, edge_item, ps: QPointF, pt: QPointF, y_mid: float) -> List[QPointF]:
        """在指定 y_mid 的 TB 路徑（保留首尾垂直結構）。"""
        s_side, t_side = self._tb_port_sides(ps, pt)
        s_out = self._stub(ps, s_side, PORT_STUB)
        t_in = self._stub(pt, t_side, PORT_STUB)
        y_mid = self._snap(y_mid)
        path = [
            ps,
            s_out,
            QPointF(s_out.x(), y_mid),
            QPointF(t_in.x(), y_mid),
            t_in,
            pt,
        ]
        return self._ensure_manhattan(path)

    def _route_advanced_tb_with_bands(self, edges_data: List[Tuple]) -> Dict[Tuple[str, str], List[QPointF]]:
        """
        進階 TB 路由（簡化版）：
        - 單邊策略：若以 port x 判斷為垂直（start.x == end.x，容差約 0.5px），直接畫純直線 [ps, pt]
        - 否則使用標準 V-H-V（或後續可插入高級核心）
        - 不再以『雙向/同節點對』作任何特例或強制分欄
        """
        # 先處理『垂直候選』的直線欄位分配（yEd 風格）：
        # - 僅針對原本就垂直（以 port x 檢查）的邊
        # - 分組鍵採用『同一對節點（忽略方向）』，確保雙向也能被當成多條線分欄
        from .band_routing import assign_vertical_columns_by_pairs, near

        n = len(edges_data)
        edges_xy: List[Tuple[QPointF, QPointF]] = []
        pair_keys: List[Tuple[str, str]] = []
        x_windows: List[Tuple[float, float]] = []
        for (edge_item, ps, pt) in edges_data:
            edges_xy.append((ps, pt))
            # 節點對（忽略方向）
            a = str(getattr(getattr(edge_item, 'src', None), 'taskId', ''))
            b = str(getattr(getattr(edge_item, 'dst', None), 'taskId', ''))
            pair_keys.append(tuple(sorted((a, b))))
            # 可用直線 [L,R] 視窗：採兩節點水平重疊
            L, R = self._compute_nodes_overlap_x(getattr(edge_item, 'src', None), getattr(edge_item, 'dst', None))
            x_windows.append((L, R) if R > L else (0.0, 0.0))

        xcol_assign: Dict[int, float] = assign_vertical_columns_by_pairs(
            edges_xy,
            x_windows=x_windows,
            pair_keys=pair_keys,
            tol_x=1.0,
            default_halfspan=12.0,
        )

        result: Dict[Tuple[str, str], List[QPointF]] = {}
        for idx, (edge_item, ps, pt) in enumerate(edges_data):
            edge_key = self._get_edge_key(edge_item)
            if abs(ps.x() - pt.x()) < 1.0 and idx in xcol_assign:
                # 多條垂直線：使用分配到的 x 欄位，保留原始 y 值
                xcol = xcol_assign[idx]
                # snap 0.5 px，避免 14.999999 之類的浮點殘值
                try:
                    from .band_routing import snap_x
                    xcol = snap_x(xcol, grid=0.5)
                except Exception:
                    pass
                p1 = QPointF(xcol, ps.y())
                p2 = QPointF(xcol, pt.y())
                result[edge_key] = [p1, p2]
            elif abs(ps.x() - pt.x()) < 0.5:
                # 單條垂直線：直接兩點
                result[edge_key] = [ps, pt]
            else:
                # 非垂直：標準 TB V-H-V
                result[edge_key] = self._route_tb_canonical(edge_item, ps, pt)

        return result
    
    def mark_edge_as_user_modified(self, edge_item, path: List[QPointF]) -> None:
        """
        標記邊線為用戶手動修改
        
        當用戶手動調整邊線（拖動控制點、改成直線等）時呼叫
        
        Args:
            edge_item: 邊線圖形項目
            path: 用戶指定的路徑
        """
        edge_key = self._get_edge_key(edge_item)
        self.user_modified_edges.add(edge_key)
        
        # 保存用戶路徑
        edge_item._user_path = path.copy()
        
        print(f"邊線 {edge_key} 已標記為用戶修改")
    
    def _route_interactive(self, start_pos: QPointF, end_pos: QPointF) -> List[QPointF]:
        """
        日常互動模式：直線或簡單折線
        
        Args:
            start_pos: 起始位置
            end_pos: 結束位置
            
        Returns:
            路徑點列表
        """
        self.routing_stats['interactive_count'] += 1
        
        # 對於日常互動，使用最簡單的直線
        return [start_pos, end_pos]
    
    def _route_orthogonal_safe(
        self, 
        edge_item, 
        start_pos: QPointF, 
        end_pos: QPointF,
        obstacles: List[QRectF] = None
    ) -> List[QPointF]:
        """
        TB 版面規範安全正交路由：
        1) TB 規範化（無障礙時的標準路徑）
        2) 有障礙才用高級路由覆蓋「中段」
        
        Args:
            edge_item: 邊線項目
            start_pos: 起始位置
            end_pos: 結束位置
            obstacles: 預先計算的障礙物列表（可選）
            
        Returns:
            TB 版面規範路徑點列表
        """
        # 1) TB 規範化（無障礙時的標準路徑）
        base = self._route_tb_canonical(edge_item, start_pos, end_pos)

        # 2) 有障礙才用高級路由覆蓋「中段」
        if obstacles and len(obstacles) > 0 and self._orthogonal_router:
            try:
                if len(base) >= 4:  # 確保有足夠的點進行中段替換
                    s_out, t_in = base[1], base[-2]   # 保留 stub 與末段垂直
                    core = self._orthogonal_router.route_edge(s_out, t_in, obstacles)
                    if core and len(core) >= 2:
                        core = self._ensure_manhattan(core)
                        # 組合：首段 + 高級路由中段 + 末段
                        return self._dedupe_keep_elbow([base[0], base[1]] + core[1:-1] + [base[-2], base[-1]])
            except Exception as e:
                print(f"高級路由失敗：{e}")

        return base
    
    def route_all_edges_for_layout(self, edges_data: List[Tuple]) -> Dict[Tuple[str, str], List[QPointF]]:
        """佈局後全圖正交路由：輸入 (edge_item, ps, pt) 清單，回傳並套用路徑字典。
        - 所有處理皆以 DrawEdge（獨立 stroke）為單位，禁止任何合併。
        - 若啟用 band router，使用 _route_advanced_tb_with_bands（逐邊規則）；
        - 否則逐條使用 _route_tb_canonical。
        - 路徑會即時套用到 EdgeItem（若提供 set_complex_path）。
        """
        t0 = time.time()
        results: Dict[Tuple[str, str], List[QPointF]] = {}
        if not edges_data:
            return results
        try:
            # 展開為 DrawEdge（目前 UI 已單向，這步主要生成穩定 draw_id）
            from .draw_edges import expand_to_draw_edges
            draw_edges = expand_to_draw_edges(edges_data)

            if self._band_router_enabled:
                # 轉回與既有邏輯相容的輸入（仍逐邊，無合併）
                ed = [(de.item, de.ps, de.pt) for de in draw_edges]
                batch = self._route_advanced_tb_with_bands(ed)
            else:
                batch = {}
                for edge_item, ps, pt in ((de.item, de.ps, de.pt) for de in draw_edges):
                    edge_key = self._get_edge_key(edge_item)
                    batch[edge_key] = self._route_tb_canonical(edge_item, ps, pt)

            # 套用到 GUI
            for de in draw_edges:
                edge_item, ps, pt = de.item, de.ps, de.pt
                edge_key = self._get_edge_key(edge_item)
                path = batch.get(edge_key, [ps, pt])
                self._apply_path_to_edge_immediate(edge_item, path)
                results[edge_key] = path
        finally:
            self.last_routing_time = int((time.time() - t0) * 1000)
            self.routing_stats['layout_count'] += 1
        return results
    
    def _route_orthogonal(
        self, 
        edge_item, 
        start_pos: QPointF, 
        end_pos: QPointF,
        obstacles: List[QRectF] = None
    ) -> List[QPointF]:
        """
        正交路由實現（90度折線） - 整合真正的避障路由
        
        Args:
            edge_item: 邊線項目
            start_pos: 起始位置
            end_pos: 結束位置
            obstacles: 障礙物列表
            
        Returns:
            路徑點列表
        """
        # 如果有高級路由器，使用它進行真正的避障路由
        if self._orthogonal_router:
            try:
                path_points = self._orthogonal_router.route_edge(start_pos, end_pos, obstacles)
                
                # 驗證路由結果
                if path_points and len(path_points) >= 2:
                    edge_id = f"{edge_item.src.taskId}->{edge_item.dst.taskId}" if hasattr(edge_item, 'src') else "unknown"
                    print(f"[高級路由] {edge_id}: {len(path_points)} 點")
                    return path_points
                else:
                    print("[高級路由] 結果無效，回退到簡單路由")
                    
            except Exception as e:
                print(f"高級路由器執行失敗: {e}")
        
        # 回退到簡單正交路由
        return self._route_simple_orthogonal(start_pos, end_pos)
    
    def _apply_path_to_edge_immediate(self, edge_item, path_points: List[QPointF]) -> None:
        """
        立即應用路徑到邊線項目，確保路徑真正繪製到畫面
        
        Args:
            edge_item: 邊線圖形項目
            path_points: 路徑點列表
        """
        try:
            # Band routing 模式下，直接使用計算好的路徑，不再做額外偏移
            adjusted = path_points
            offset_pixels = 0  # Band routing 已經處理了位置分配，不需要額外偏移

            # 使用 EdgeItem 的增強路徑設置方法
            if hasattr(edge_item, 'set_complex_path'):
                edge_item.set_complex_path(adjusted, offset_pixels)
            else:
                # 回退方案：若無 set_complex_path 且無法建立 QPainterPath，則略過
                # 實際環境具備 PyQt5 時，應提供 set_complex_path，否則忽略回退繪製
                pass
                    
        except Exception as e:
            print(f"應用路徑到邊線失敗: {e}")
    
    # 移除成對邊搜尋：禁止基於同節點對的合併或特別處理。
    
    def _route_simple_orthogonal(self, start_pos: QPointF, end_pos: QPointF) -> List[QPointF]:
        """
        yEd 風格簡單正交路由：永遠返回3點，強制至少1個轉角
        
        Args:
            start_pos: 起始位置
            end_pos: 結束位置
            
        Returns:
            固定3點路徑列表（包含1個轉角）
        """
        # 固定策略：以 TB 方向為預設（先垂直再水平）
        prefer = 'TB'
        
        if prefer == 'TB':
            mid_point = QPointF(start_pos.x(), end_pos.y())
        else:  # 'LR'
            mid_point = QPointF(end_pos.x(), start_pos.y())
        
        return [start_pos, mid_point, end_pos]
    
    def _calculate_roi(self, start_pos: QPointF, end_pos: QPointF, padding: float = 200) -> QRectF:
        """
        計算路由搜尋的 ROI (Region of Interest) 區域
        
        Args:
            start_pos: 起始位置
            end_pos: 結束位置
            padding: 擴展邊界（像素）
        
        Returns:
            ROI 矩形區域
        """
        # 計算起終點的包圍盒
        min_x = min(start_pos.x(), end_pos.x())
        max_x = max(start_pos.x(), end_pos.x())
        min_y = min(start_pos.y(), end_pos.y())
        max_y = max(start_pos.y(), end_pos.y())
        
        # 外擴 padding
        roi_rect = QRectF(
            min_x - padding,
            min_y - padding,
            (max_x - min_x) + 2 * padding,
            (max_y - min_y) + 2 * padding
        )
        
        return roi_rect
    
    def _collect_obstacles(self, edge_item=None, roi_rect: QRectF = None) -> List[QRectF]:
        """
        收集場景中的障礙物（節點邊界框）
        
        Args:
            edge_item: 當前路由的邊線項目，將排除其起終點節點
            roi_rect: ROI 區域，只收集此區域內的障礙物
        
        Returns:
            障礙物矩形列表
        """
        obstacles = []
        
        if not self.scene:
            return obstacles
        
        # 獲取要排除的節點（起終點）
        excluded_nodes = set()
        if edge_item:
            # 獲取邊線的起終點節點
            src_node = getattr(edge_item, 'src', None) or getattr(edge_item, 'source_node', None)
            dst_node = getattr(edge_item, 'dst', None) or getattr(edge_item, 'target_node', None)
            if src_node:
                excluded_nodes.add(src_node)
            if dst_node:
                excluded_nodes.add(dst_node)
        
        # 收集所有節點作為障礙物
        for item in self.scene.items():
            # 支援 taskId 和 task_id 兩種命名
            has_task_id = hasattr(item, 'taskId') or hasattr(item, 'task_id')
            if hasattr(item, 'boundingRect') and has_task_id:
                # 排除起終點節點
                if item in excluded_nodes:
                    continue
                
                # 這是一個任務節點
                rect = item.boundingRect()
                scene_rect = item.mapRectToScene(rect)
                
                # ROI 過濾：只保留 ROI 區域內的障礙物
                if roi_rect and not roi_rect.intersects(scene_rect):
                    continue
                
                # 加入 12px 安全邊界避免邊線貼得太近
                expanded_rect = scene_rect.adjusted(-12, -12, 12, 12)
                obstacles.append(expanded_rect)
        
        excluded_count = len(excluded_nodes)
        roi_info = "，ROI 過濾" if roi_rect else ""
        print(f"收集到 {len(obstacles)} 個障礙物節點（排除 {excluded_count} 個起終點{roi_info}）")
        return obstacles
    
    def _fallback_to_simple_orthogonal(self, edges_data: List[Tuple]) -> Dict[Tuple[str, str], List[QPointF]]:
        """
        回退到簡單正交連接（L型折線）
        
        Args:
            edges_data: [(edge_item, start_pos, end_pos), ...]
            
        Returns:
            {edge_key: [L型路徑點列表], ...}
        """
        result = {}
        for edge_item, start_pos, end_pos in edges_data:
            edge_key = self._get_edge_key(edge_item)
            # 使用 L 型正交路由而不是直線
            result[edge_key] = self._route_simple_orthogonal(start_pos, end_pos)
        return result
    
    def _get_edge_key(self, edge_item) -> Tuple[str, str]:
        """
        獲取邊線的唯一標識
        
        Args:
            edge_item: 邊線圖形項目
            
        Returns:
            (源節點ID, 目標節點ID)
        """
        # 支援 src/dst 和 source_node/target_node 兩種欄位
        src_node = None
        dst_node = None
        
        if hasattr(edge_item, 'src') and hasattr(edge_item, 'dst'):
            src_node = edge_item.src
            dst_node = edge_item.dst
        elif hasattr(edge_item, 'source_node') and hasattr(edge_item, 'target_node'):
            src_node = edge_item.source_node
            dst_node = edge_item.target_node
        
        if src_node and dst_node:
            # 支援 taskId 和 task_id 兩種節點屬性
            src_id = getattr(src_node, 'taskId', None) or getattr(src_node, 'task_id', 'unknown')
            dst_id = getattr(dst_node, 'taskId', None) or getattr(dst_node, 'task_id', 'unknown')
            return (src_id, dst_id)
        
        # 回退方案
        return (str(id(edge_item)), 'target')
    
    def set_orthogonal_router(self, router) -> None:
        """
        設置高級正交路由器
        
        Args:
            router: 實現了 route_edge 方法的路由器對象
        """
        self._orthogonal_router = router
        print("已設置高級正交路由器")
    
    def get_routing_stats(self) -> Dict:
        """
        獲取路由統計信息
        
        Returns:
            統計信息字典
        """
        return {
            **self.routing_stats,
            'last_routing_time': self.last_routing_time,
            'current_mode': self.current_mode.value,
            'user_modified_count': len(self.user_modified_edges)
        }

    def set_band_router_enabled(self, enabled: bool) -> None:
        """啟用/停用帶狀進階 TB 路由（預設 False）。"""
        self._band_router_enabled = bool(enabled)
        print(f"Band router enabled = {self._band_router_enabled}")

    

    def reset_user_modifications(self) -> None:
        """重置所有用戶修改記錄"""
        self.user_modified_edges.clear()
        print("已重置用戶邊線修改記錄")


# 便利函數
def create_yed_router_manager(scene, timeout_ms: int = 5000) -> EdgeRouterManager:
    """
    創建 yEd 風格的路由管理器
    
    Args:
        scene: DSM 場景
        timeout_ms: 超時時間
        
    Returns:
        路由管理器實例
    """
    manager = EdgeRouterManager(scene, timeout_ms)
    
    # 嘗試載入高級路由器（多種載入方式）
    try:
        from .advanced_routing import AdvancedEdgeRouter
        advanced_router = AdvancedEdgeRouter()
        manager.set_orthogonal_router(advanced_router)
        print("成功載入高級正交路由器")
    except ImportError as e:
        print(f"高級路由器導入失敗: {e}")
        try:
            # 備用載入方式
            from advanced_routing import AdvancedEdgeRouter
            advanced_router = AdvancedEdgeRouter()
            manager.set_orthogonal_router(advanced_router)
            print("成功載入高級正交路由器（備用方式）")
        except ImportError:
            print("高級路由器不可用，使用智能簡單正交路由")
    except Exception as e:
        print(f"高級路由器初始化失敗: {e}")
        print("回退到智能簡單正交路由")
    
    # 啟用帶狀進階 TB 路由（預設開啟以使用通用直線欄位分配；可用 BIRDMAN_BAND_ROUTER=0 關閉）
    try:
        import os
        flag = os.environ.get("BIRDMAN_BAND_ROUTER", "1")
        manager.set_band_router_enabled(flag != "0")
    except Exception:
        manager.set_band_router_enabled(True)

    return manager