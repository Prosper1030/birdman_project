"""
Routed Edge Item - 整合 yEd 風格路由的邊線項目

整合 EdgeRoutingEngine 與現有的 EdgeItem，
提供智慧路由功能同時保持所有現有的視覺效果和互動功能。
"""

from PyQt5.QtCore import QPointF, QRectF, Qt, QLineF
from PyQt5.QtGui import QPainterPath, QPen, QColor, QBrush
from PyQt5.QtWidgets import QGraphicsPathItem, QStyle

from .edge_routing import EdgeRoutingEngine
import math


class RoutedEdgeItem(QGraphicsPathItem):
    """
    支援智慧路由的邊線項目
    
    繼承所有現有 EdgeItem 的功能，添加：
    1. yEd 風格正交路由
    2. 智慧避障
    3. 多邊線分散
    4. 動態路由更新
    """
    
    # 路由模式
    ROUTING_DIRECT = "direct"           # 直線連接 (原有方式)
    ROUTING_ORTHOGONAL = "orthogonal"   # 正交路由 (yEd 風格)
    ROUTING_SMART = "smart"             # 智慧選擇
    
    # 注意：QGraphicsPathItem 不是 QObject，不能使用 pyqtSignal
    # 如需信號，可以通過父場景或其他機制處理
    
    def __init__(self, src: 'TaskNode', dst: 'TaskNode', routing_engine: EdgeRoutingEngine = None):
        super().__init__()
        
        self.src = src
        self.dst = dst
        self.label = ""
        self.isTemporary = False
        
        # 路由相關
        self.routing_engine = routing_engine
        self.routing_mode = self.ROUTING_SMART
        self.enable_routing = True
        self.route_cache = None  # 路由路徑快取
        
        # 多邊線處理
        self.edge_offset = 0  # 多邊線偏移
        self.parallel_edges_count = 1
        
        # 視覺樣式 (保持與原 EdgeItem 一致)
        self.normalPen = QPen(Qt.black, 2, Qt.SolidLine)
        self.hoverPen = QPen(Qt.black, 3, Qt.SolidLine)
        self.selectedPen = QPen(Qt.blue, 3, Qt.SolidLine)
        self.tempPen = QPen(Qt.gray, 2, Qt.DashLine)
        
        # 狀態變數 (支援 yEd 風格選取)
        self._is_selected = False
        self._is_hovered = False
        self._is_shift_highlighted = False
        
        # 設定
        self.setPen(self.normalPen)
        self.setZValue(1)
        self.setFlag(self.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        # 初始化路徑
        self.updateRoutedPath()
    
    def setRoutingEngine(self, engine: EdgeRoutingEngine):
        """設定路由引擎"""
        self.routing_engine = engine
        self.route_cache = None
        self.updateRoutedPath()
    
    def setRoutingMode(self, mode: str):
        """設定路由模式"""
        if mode in [self.ROUTING_DIRECT, self.ROUTING_ORTHOGONAL, self.ROUTING_SMART]:
            self.routing_mode = mode
            self.route_cache = None
            self.updateRoutedPath()
    
    def setEnableRouting(self, enabled: bool):
        """啟用/禁用智慧路由"""
        self.enable_routing = enabled
        self.route_cache = None
        self.updateRoutedPath()
    
    def setEdgeOffset(self, offset: float):
        """設定邊線偏移 (用於多邊線分散)"""
        self.edge_offset = offset
        self.route_cache = None
        self.updateRoutedPath()
    
    def updateRoutedPath(self):
        """更新路由路徑 - 主要路由邏輯"""
        if not self.src or not self.dst:
            return
        
        # 計算連接點
        src_point, dst_point = self._calculateConnectionPoints()
        
        if not src_point or not dst_point:
            return
        
        # 應用多邊線偏移
        if self.edge_offset != 0:
            src_point, dst_point = self._applyParallelOffset(src_point, dst_point)
        
        # 選擇路由方法
        if self.enable_routing and self.routing_engine and self.routing_mode != self.ROUTING_DIRECT:
            routed_path = self._computeRoutedPath(src_point, dst_point)
        else:
            routed_path = self._computeDirectPath(src_point, dst_point)
        
        self.setPath(routed_path)
        # 路由變更完成 - 可以在這裡添加其他處理邏輯
    
    def _calculateConnectionPoints(self) -> tuple:
        """計算節點連接點 - 使用原有的精確計算方法"""
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()
        
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()
        centerLine = QLineF(srcCenter, dstCenter)
        
        # 使用原有的精確連接點計算
        srcPoint = self._getRectLineIntersection(srcRect, centerLine, True)
        dstPoint = self._getRectLineIntersection(dstRect, centerLine, False)
        
        return srcPoint, dstPoint
    
    def _getRectLineIntersection(self, rect: QRectF, line: QLineF, isSource: bool):
        """計算線與矩形的交點 - 保持原有邏輯"""
        edges = [
            QLineF(rect.topLeft(), rect.topRight()),
            QLineF(rect.topRight(), rect.bottomRight()),
            QLineF(rect.bottomRight(), rect.bottomLeft()),
            QLineF(rect.bottomLeft(), rect.topLeft())
        ]
        
        intersections = []
        for edge in edges:
            intersectType, intersectPoint = edge.intersects(line)
            if intersectType == QLineF.BoundedIntersection:
                intersections.append(intersectPoint)
        
        if not intersections:
            return line.p1() if isSource else line.p2()
        
        if len(intersections) == 1:
            return intersections[0]
        
        # 選擇最合適的交點
        targetPoint = line.p2() if isSource else line.p1()
        return min(intersections, key=lambda p: QLineF(p, targetPoint).length())
    
    def _applyParallelOffset(self, src_point: QPointF, dst_point: QPointF) -> tuple:
        """應用平行邊線偏移"""
        # 計算垂直方向
        direction = dst_point - src_point
        length = math.sqrt(direction.x()**2 + direction.y()**2)
        
        if length > 0:
            direction /= length
            perpendicular = QPointF(-direction.y(), direction.x())
            
            offset_src = src_point + perpendicular * self.edge_offset
            offset_dst = dst_point + perpendicular * self.edge_offset
            
            return offset_src, offset_dst
        
        return src_point, dst_point
    
    def _computeRoutedPath(self, src_point: QPointF, dst_point: QPointF) -> QPainterPath:
        """計算路由路徑 - 使用路由引擎"""
        try:
            # 檢查快取
            cache_key = (src_point.x(), src_point.y(), dst_point.x(), dst_point.y(), self.routing_mode)
            if self.route_cache and self.route_cache[0] == cache_key:
                return self.route_cache[1]
            
            # 路由計算
            if self.routing_mode == self.ROUTING_ORTHOGONAL:
                routed_path = self.routing_engine.route_edge(src_point, dst_point)
            elif self.routing_mode == self.ROUTING_SMART:
                # 智慧選擇：短距離使用直線，長距離使用路由
                distance = math.sqrt((dst_point.x() - src_point.x())**2 + 
                                   (dst_point.y() - src_point.y())**2)
                if distance < 150:  # 150 像素內使用直線
                    routed_path = self._computeDirectPath(src_point, dst_point)
                else:
                    routed_path = self.routing_engine.route_edge(src_point, dst_point)
            else:
                routed_path = self._computeDirectPath(src_point, dst_point)
            
            # 快取結果
            self.route_cache = (cache_key, routed_path)
            return routed_path
            
        except Exception as e:
            print(f"路由計算失敗: {e}")
            return self._computeDirectPath(src_point, dst_point)
    
    def _computeDirectPath(self, src_point: QPointF, dst_point: QPointF) -> QPainterPath:
        """計算直線路徑 - 原有方法"""
        path = QPainterPath()
        path.moveTo(src_point)
        path.lineTo(dst_point)
        return path
    
    # ============ 保持所有原有的視覺和互動功能 ============
    
    def paint(self, painter, option, widget=None):
        """繪製 - 保持 yEd 風格發光效果"""
        try:
            from PyQt5.QtWidgets import QStyle
            option.state &= ~QStyle.State_Selected
            
            is_selected = getattr(self, '_is_selected', False)
            is_shift_highlighted = getattr(self, '_is_shift_highlighted', False)
            is_hovered = getattr(self, '_is_hovered', False)
            
            # 繪製發光效果
            if is_shift_highlighted:
                glow_pen = QPen(QColor(255, 220, 50, 150), 10, Qt.SolidLine)
                glow_pen.setCapStyle(Qt.RoundCap)
                glow_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(glow_pen)
                painter.drawPath(self.path())
                
                mid_glow_pen = QPen(QColor(255, 200, 50, 200), 6, Qt.SolidLine)
                mid_glow_pen.setCapStyle(Qt.RoundCap)
                mid_glow_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(mid_glow_pen)
                painter.drawPath(self.path())
                
            elif is_selected:
                glow_pen = QPen(QColor(255, 165, 0, 120), 8, Qt.SolidLine)
                glow_pen.setCapStyle(Qt.RoundCap)
                glow_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(glow_pen)
                painter.drawPath(self.path())
                
                mid_glow_pen = QPen(QColor(255, 165, 0, 180), 5, Qt.SolidLine)
                mid_glow_pen.setCapStyle(Qt.RoundCap)
                mid_glow_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(mid_glow_pen)
                painter.drawPath(self.path())
                
            elif is_hovered:
                glow_pen = QPen(QColor(255, 165, 0, 80), 4, Qt.SolidLine)
                glow_pen.setCapStyle(Qt.RoundCap)
                glow_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(glow_pen)
                painter.drawPath(self.path())
            
            # 永遠繪製主要黑色邊線
            main_pen = QPen(Qt.black, 2, Qt.SolidLine)
            main_pen.setCapStyle(Qt.RoundCap)
            main_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(main_pen)
            painter.drawPath(self.path())
            
        except Exception as e:
            print(f"RoutedEdgeItem paint error: {e}")
            super().paint(painter, option, widget)
    
    def hoverEnterEvent(self, event):
        """滑鼠懸停進入"""
        if not self.isTemporary:
            from PyQt5.QtWidgets import QApplication
            modifiers = QApplication.keyboardModifiers()
            shift_pressed = modifiers & Qt.ShiftModifier
            
            if shift_pressed:
                self._is_shift_highlighted = True
            else:
                self._is_hovered = True
            
            self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """滑鼠懸停離開"""
        if not self.isTemporary:
            self._is_hovered = False
            self._is_shift_highlighted = False
            self.update()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """滑鼠按下事件 - 保持多選功能"""
        if event.button() == Qt.LeftButton and not self.isTemporary:
            from PyQt5.QtWidgets import QApplication
            modifiers = QApplication.keyboardModifiers()
            shift_pressed = modifiers & Qt.ShiftModifier
            
            current_selected = getattr(self, '_is_selected', False)
            
            if shift_pressed:
                # Shift 多選模式
                self._is_selected = not current_selected
                self.update()
                
                # 計算選取邊線總數
                scene = self.scene()
                selected_count = 0
                selected_edges = []
                if scene:
                    for item in scene.items():
                        if isinstance(item, (RoutedEdgeItem, EdgeItem)) and getattr(item, '_is_selected', False):
                            selected_count += 1
                            selected_edges.append(f"{item.src.taskId}->{item.dst.taskId}")
                            item.update()
                
                print(f"[Shift多選] 路由邊線 {self.src.taskId} -> {self.dst.taskId} {'選取' if self._is_selected else '取消選取'}")
                print(f"    當前選取的邊線: {selected_edges} (總共: {selected_count})")
            else:
                # 單選模式
                scene = self.scene()
                if scene:
                    for item in scene.items():
                        if isinstance(item, (RoutedEdgeItem, EdgeItem)) and item != self:
                            if getattr(item, '_is_selected', False):
                                item._is_selected = False
                                item.update()
                
                if not current_selected:
                    self._is_selected = True
                    print(f"[單選] 路由邊線 {self.src.taskId} -> {self.dst.taskId} 選取")
                else:
                    self._is_selected = False
                    print(f"[單選] 路由邊線 {self.src.taskId} -> {self.dst.taskId} 取消選取")
                
                self.update()
            
            self._is_hovered = False
            self._is_shift_highlighted = False
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def invalidateRouteCache(self):
        """使路由快取失效 - 在節點移動時調用"""
        self.route_cache = None
        
    def getRoutingInfo(self) -> dict:
        """獲取路由資訊 - 調試用"""
        path_length = self.path().length() if not self.path().isEmpty() else 0
        return {
            "routing_mode": self.routing_mode,
            "enable_routing": self.enable_routing,
            "path_length": path_length,
            "edge_offset": self.edge_offset,
            "has_cache": self.route_cache is not None
        }


# 為了相容性，保持原 EdgeItem 導入
try:
    from .dsm_editor import EdgeItem
except ImportError:
    EdgeItem = type("EdgeItem", (), {})  # 占位類別