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
from PyQt5.QtCore import QPointF, QRectF, QObject


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
                # 拆成 HV（TB 版面）
                mid = QPointF(a.x(), b.y())
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
    
    def set_routing_mode(self, mode: RoutingMode) -> None:
        """
        設置路由模式
        
        Args:
            mode: 新的路由模式
        """
        if mode != self.current_mode:
            self.current_mode = mode
            print(f"路由模式切換為: {mode.value}")
    
    def route_single_edge(
        self, 
        edge_item, 
        start_pos: QPointF, 
        end_pos: QPointF,
        force_mode: Optional[RoutingMode] = None
    ) -> List[QPointF]:
        """
        路由單條邊線
        
        Args:
            edge_item: 邊線圖形項目
            start_pos: 起始位置
            end_pos: 結束位置
            force_mode: 強制使用指定模式
            
        Returns:
            路徑點列表
        """
        # 獲取邊線標識
        edge_key = self._get_edge_key(edge_item)
        
        # 檢查是否為用戶修改的邊線
        if edge_key in self.user_modified_edges and force_mode is None:
            # 保持用戶指定的形狀，不自動路由
            current_path = getattr(edge_item, '_user_path', None)
            if current_path:
                return current_path
        
        # 確定使用的路由模式
        mode = force_mode if force_mode else self.current_mode
        
        if mode == RoutingMode.INTERACTIVE:
            return self._route_interactive(start_pos, end_pos)
        else:
            return self._route_orthogonal(edge_item, start_pos, end_pos)
    
    def route_all_edges_for_layout(self, edges_data: List[Tuple]) -> Dict[Tuple[str, str], List[QPointF]]:
        """
        佈局時對所有邊線執行正交路由
        
        這是「套用佈局」流程的一部分：
        1. 節點佈局完成
        2. 全圖正交路由 ← 此功能
        3. 重繪
        
        Args:
            edges_data: [(edge_item, start_pos, end_pos), ...]
            
        Returns:
            {(src_id, dst_id): [path_points], ...}
        """
        print(f"開始全圖正交路由，處理 {len(edges_data)} 條邊線...")
        start_time = time.time()
        
        # 清空用戶修改記錄（新佈局重新開始）
        self.user_modified_edges.clear()
        
        # 暫時切換到佈局模式
        original_mode = self.current_mode
        self.set_routing_mode(RoutingMode.LAYOUT)
        
        try:
            result = {}
            # 不預先收集所有障礙物，改用 ROI 個別收集
            # 若啟用帶狀進階路由，改走一次性批次管線
            if getattr(self, "_band_router_enabled", False):
                try:
                    result = self._route_advanced_tb_with_bands(edges_data)
                    # 立即應用（以 edge_key 對應避免順序問題）
                    for edge_item, _, _ in edges_data:
                        edge_key = self._get_edge_key(edge_item)
                        if edge_key in result:
                            self._apply_path_to_edge_immediate(edge_item, result[edge_key])
                    elapsed = time.time() - start_time
                    self.last_routing_time = elapsed
                    self.routing_stats['layout_count'] += 1
                    print(f"全圖進階TB帶狀路由完成，耗時 {elapsed:.3f}s")
                    return result
                except Exception as e:
                    print(f"帶狀路由失敗，回退到逐邊路由：{e}")
            # 檢查超時和逐邊處理
            for i, (edge_item, start_pos, end_pos) in enumerate(edges_data):
                if time.time() - start_time > self.timeout_ms / 1000:
                    print(f"路由計算超時，已處理 {i}/{len(edges_data)} 條邊線")
                    self.routing_stats['timeout_count'] += 1
                    # 剩餘邊線使用 L 型正交路由
                    for j in range(i, len(edges_data)):
                        remaining_edge, remaining_start, remaining_end = edges_data[j]
                        edge_key = self._get_edge_key(remaining_edge)
                        # 超時回退改用 L 型折線而不是直線
                        result[edge_key] = self._route_simple_orthogonal(remaining_start, remaining_end)
                    break
                
                edge_key = self._get_edge_key(edge_item)
                # 使用個別 ROI 優化的路由
                path = self._route_orthogonal_safe(edge_item, start_pos, end_pos)
                result[edge_key] = path
                
                # 立即應用路徑到 EdgeItem，確保路徑真正繪製到畫面
                self._apply_path_to_edge_immediate(edge_item, path)
            
            elapsed = time.time() - start_time
            self.last_routing_time = elapsed
            self.routing_stats['layout_count'] += 1
            
            print(f"全圖正交路由完成，耗時 {elapsed:.3f}s")
            return result
            
        except Exception as e:
            print(f"全圖正交路由失敗: {e}")
            self.routing_stats['fallback_count'] += 1
            # 全部回退到 L 型正交路由
            return self._fallback_to_simple_orthogonal(edges_data)
        finally:
            # 恢復原模式
            self.set_routing_mode(original_mode)

    def set_band_router_enabled(self, enabled: bool) -> None:
        """啟用/停用進階 TB 帶狀路由（預設關閉）。"""
        self._band_router_enabled = bool(enabled)
        print(f"進階TB帶狀路由: {'ON' if self._band_router_enabled else 'OFF'}")

    # --- 進階 TB: 以指定 y_mid 產生 V-H-V 幾何 ---
    def _route_tb_with_y(self, edge_item, ps: QPointF, pt: QPointF, y_mid: float) -> List[QPointF]:
        """以指定的中段 y 生成 TB 的 V-H-V 路徑，保留 stub 與末段垂直規範。"""
        src = getattr(edge_item, 'src', getattr(edge_item, 'source_node', None))
        dst = getattr(edge_item, 'dst', getattr(edge_item, 'target_node', None))
        s_side = self._port_side(src, ps) if src else 'bottom'
        t_side = self._port_side(dst, pt) if dst else 'top'

        s_out = self._stub(ps, s_side, PORT_STUB)
        t_in = self._stub(pt, t_side, PORT_STUB)

        # 夾在安全帶內
        y_low = s_out.y() + CLEAR
        y_high = t_in.y() - CLEAR
        y_mid = self._snap(max(min(y_mid, y_high), y_low))

        mid1 = QPointF(s_out.x(), y_mid)
        mid2 = QPointF(t_in.x(), y_mid)
        path = [ps, s_out, mid1, mid2, t_in, pt]
        return self._ensure_manhattan(path)

    def _route_advanced_tb_with_bands(self, edges_data: List[Tuple]) -> Dict[Tuple[str, str], List[QPointF]]:
        """批次帶狀分配 + 直線預處理 的 V-H-V 管線（最小可用骨架）。"""
        from . import band_routing as br

        # 收集 (ps, pt) 及每條邊的 ROI 障礙物
        pts: List[Tuple[QPointF, QPointF]] = []
        obstacles_by_edge: List[List[QRectF]] = []
        for edge_item, ps, pt in edges_data:
            pts.append((ps, pt))
            roi = self._calculate_roi(ps, pt, padding=200)
            obstacles_by_edge.append(self._collect_obstacles(edge_item, roi))

        # Phase 1: 直線（垂直）預處理
        locked_map, remain_idx = br.preprocess_straight_edges(pts, obstacles_by_edge, tol=1.0)

        # Phase 2: 帶狀分配（帶垂直碰撞檢查）
        remain_pts = [pts[i] for i in remain_idx]
        lane_spacing = GRID

        # 先建立垂直碰撞地圖，將已鎖直線登記
        vmap = {}
        for i, path in locked_map.items():
            ps, pt = path[0], path[1]
            # 單一垂直段佔用
            br.vmap_add(vmap, ps.x(), ps.y(), pt.y(), grid=1.0)

        # 準備每條剩餘邊的 stub 上下界（用於 y_mid 計算）
        stubs_y: List[Tuple[float, float]] = []
        for j, (ps, pt) in enumerate(remain_pts):
            edge_item = edges_data[remain_idx[j]][0]
            src = getattr(edge_item, 'src', getattr(edge_item, 'source_node', None))
            dst = getattr(edge_item, 'dst', getattr(edge_item, 'target_node', None))
            s_side = self._port_side(src, ps) if src else 'bottom'
            t_side = self._port_side(dst, pt) if dst else 'top'
            s_out = self._stub(ps, s_side, PORT_STUB)
            t_in = self._stub(pt, t_side, PORT_STUB)
            stubs_y.append((s_out.y(), t_in.y()))

        # TODO: 未接上 fragments → profile；先假設空 profile（不提高低限）
        empty_profile = []
        low_lanes = br.mark_low_lane(remain_pts, empty_profile, lane_spacing)
        assign, failed = br.assign_band_with_vertical_checks(
            remain_pts, stubs_y, lane_spacing, vmap, vgrid=1.0, low_lanes=low_lanes
        )

        # 組裝結果
        result: Dict[Tuple[str, str], List[QPointF]] = {}
        # 先放已鎖定直線
        for i, path in locked_map.items():
            edge_item, ps, pt = edges_data[i]
            edge_key = self._get_edge_key(edge_item)
            result[edge_key] = path

        # 為剩餘的依 lane 產生 y_mid 幾何
        for local_i, (ps, pt) in enumerate(remain_pts):
            lane = assign.get(local_i)
            if lane is None:
                continue  # 留待後備處理
            global_index = remain_idx[local_i]
            edge_item = edges_data[global_index][0]
            # 構造 stub 後的上下界求 y_mid
            src = getattr(edge_item, 'src', getattr(edge_item, 'source_node', None))
            dst = getattr(edge_item, 'dst', getattr(edge_item, 'target_node', None))
            s_side = self._port_side(src, ps) if src else 'bottom'
            t_side = self._port_side(dst, pt) if dst else 'top'
            s_out = self._stub(ps, s_side, PORT_STUB)
            t_in = self._stub(pt, t_side, PORT_STUB)
            y_mid = br.compute_y_mid(s_out.y(), t_in.y(), lane, lane_spacing=lane_spacing, min_clear=CLEAR)
            path = self._route_tb_with_y(edge_item, ps, pt, y_mid)
            edge_key = self._get_edge_key(edge_item)
            result[edge_key] = path

        # Phase 3: 對未能放入帶狀的邊（failed）做簡單主矩形回退（先用 first-fit 不帶檢查）
        if failed:
            fallback_pts = [remain_pts[i] for i in failed]
            fb_assign = br.assign_main_rectangle(fallback_pts)
            for k, lane in fb_assign.items():
                ps, pt = fallback_pts[k]
                global_index = remain_idx[failed[k]]
                edge_item = edges_data[global_index][0]
                src = getattr(edge_item, 'src', getattr(edge_item, 'source_node', None))
                dst = getattr(edge_item, 'dst', getattr(edge_item, 'target_node', None))
                s_side = self._port_side(src, ps) if src else 'bottom'
                t_side = self._port_side(dst, pt) if dst else 'top'
                s_out = self._stub(ps, s_side, PORT_STUB)
                t_in = self._stub(pt, t_side, PORT_STUB)
                y_mid = br.compute_y_mid(s_out.y(), t_in.y(), lane, lane_spacing=lane_spacing, min_clear=CLEAR)
                path = self._route_tb_with_y(edge_item, ps, pt, y_mid)
                edge_key = self._get_edge_key(edge_item)
                result[edge_key] = path
                # 登記垂直段
                br.vmap_add(vmap, ps.x(), ps.y(), y_mid, grid=1.0)
                br.vmap_add(vmap, pt.x(), y_mid, pt.y(), grid=1.0)

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
            # 檢查是否為多邊重疊情況，計算偏移
            offset_pixels = 0
            if hasattr(edge_item, 'src') and hasattr(edge_item, 'dst'):
                # 檢查是否有相同源目標的其他邊線
                same_pair_edges = self._find_same_pair_edges(edge_item)
                if len(same_pair_edges) > 1:
                    # 為多邊線計算不同偏移量
                    edge_index = same_pair_edges.index(edge_item) if edge_item in same_pair_edges else 0
                    offset_pixels = (edge_index - len(same_pair_edges) / 2) * 4  # ±4px 偏移
            
            # 使用 EdgeItem 的增強路徑設置方法
            if hasattr(edge_item, 'set_complex_path'):
                edge_item.set_complex_path(path_points, offset_pixels)
            else:
                # 回退方案：直接設置 QPainterPath
                from PyQt5.QtGui import QPainterPath
                if path_points and len(path_points) >= 2:
                    painter_path = QPainterPath(path_points[0])
                    for point in path_points[1:]:
                        painter_path.lineTo(point)
                    edge_item.setPath(painter_path)
                    edge_item.update()
                    
        except Exception as e:
            print(f"應用路徑到邊線失敗: {e}")
    
    def _find_same_pair_edges(self, target_edge) -> list:
        """尋找相同源目標對的所有邊線"""
        same_edges = []
        if not hasattr(target_edge, 'src') or not hasattr(target_edge, 'dst'):
            return [target_edge]
            
        target_src = target_edge.src.taskId
        target_dst = target_edge.dst.taskId
        
        # 從場景中找到所有相同配對的邊線
        if hasattr(target_edge, 'scene') and target_edge.scene():
            for item in target_edge.scene().items():
                if (hasattr(item, 'src') and hasattr(item, 'dst') and
                        hasattr(item.src, 'taskId') and hasattr(item.dst, 'taskId')):
                    if (item.src.taskId == target_src and item.dst.taskId == target_dst):
                        same_edges.append(item)
        
        return same_edges
    
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

    def _infer_port_side(self, node, pos: QPointF) -> str:
        """推斷端口位於節點的哪一側，回傳 'top'|'right'|'bottom'|'left'"""
        if not node or not hasattr(node, 'sceneBoundingRect'):
            return 'right'  # 預設值
            
        r = node.sceneBoundingRect()
        d = {
            'left': abs(pos.x() - r.left()),
            'right': abs(pos.x() - r.right()),
            'top': abs(pos.y() - r.top()),
            'bottom': abs(pos.y() - r.bottom()),
        }
        return min(d, key=d.get)

    def _make_stub_point(self, pos: QPointF, side: str, length: float = None) -> QPointF:
        """從端口位置向外推出指定長度的 stub 點"""
        if length is None:
            length = self.STUB_LEN
            
        if side == 'left':
            return QPointF(pos.x() - length, pos.y())
        elif side == 'right':
            return QPointF(pos.x() + length, pos.y())
        elif side == 'top':
            return QPointF(pos.x(), pos.y() - length)
        else:  # bottom
            return QPointF(pos.x(), pos.y() + length)

    def _ensure_manhattan(self, pts: List[QPointF], prefer: str = 'TB', always_elbow: bool = True) -> List[QPointF]:
        """
        將任意點列正規化為完全正交路徑
        
        Args:
            pts: 原始點列
            prefer: 'TB' → 優先垂直再水平（HV），'LR' → 優先水平再垂直（VH）
            always_elbow: 若只有兩點，強制插入一個轉角
            
        Returns:
            完全正交的點列
        """
        if not pts:
            return []
        
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            ax, ay = a.x(), a.y()
            bx, by = b.x(), b.y()
            
            # 如果已經是正交連接（同 x 或同 y），直接加入
            if abs(ax - bx) < 0.1 or abs(ay - by) < 0.1:
                out.append(b)
            else:
                # 插入中繼點強制正交
                if prefer == 'TB':
                    mid = QPointF(ax, by)  # 先垂直再水平
                else:  # 'LR'
                    mid = QPointF(bx, ay)  # 先水平再垂直
                out.append(mid)
                out.append(b)
        
        # always_elbow：若只有兩點，強制插一個轉角
        if always_elbow and len(out) == 2:
            a, b = out[0], out[1]
            ax, ay = a.x(), a.y()
            bx, by = b.x(), b.y()
            
            # 檢查是否已經是正交的（水平或垂直線）
            if abs(ax - bx) < 0.1:  # 垂直線
                # 插入水平中點
                mid = QPointF((ax + bx) / 2 + 20, ay)  # 稍微偏移避免重疊
            elif abs(ay - by) < 0.1:  # 水平線
                # 插入垂直中點
                mid = QPointF(ax, (ay + by) / 2 + 20)  # 稍微偏移避免重疊
            else:
                # 對角線按照 prefer 策略
                if prefer == 'TB':
                    mid = QPointF(ax, by)
                else:
                    mid = QPointF(bx, ay)
            out = [a, mid, b]
        
        # 去除重複點
        dedup = [out[0]]
        for p in out[1:]:
            if abs(p.x() - dedup[-1].x()) > 0.1 or abs(p.y() - dedup[-1].y()) > 0.1:
                dedup.append(p)
        
        return dedup

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
    
    return manager