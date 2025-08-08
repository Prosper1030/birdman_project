#!/usr/bin/env python3
"""
增強型邊線項目 - 支援 yEd 風格路由
整合正交路由、智慧避障、平滑曲線等功能
"""

import math
from typing import Optional, Tuple, List
from enum import Enum

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QPainterPath, QPen, QBrush, QColor, QPainter, QPolygonF
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItem, QStyle

from .engine import RoutingEngine, RoutingRequest, RoutingStyle, EdgeType


class ArrowStyle(Enum):
    """箭頭樣式"""
    TRIANGLE = "triangle"
    ARROW = "arrow"
    DIAMOND = "diamond"
    CIRCLE = "circle"


class GlowArrowHead(QGraphicsPathItem):
    """支援發光效果的箭頭"""
    
    def __init__(self, parent_edge: 'EnhancedEdgeItem'):
        super().__init__()
        self.parent_edge = parent_edge
        self.arrow_size = 15
        self.arrow_angle = math.pi / 6
        self.arrow_style = ArrowStyle.TRIANGLE
        
        # 設定基本屬性
        self.setZValue(3)  # 確保箭頭在邊線上層
        self.setPen(QPen(Qt.NoPen))
        self.setBrush(QBrush(Qt.black))
        
    def updatePosition(self, end_point: QPointF, direction: Tuple[float, float]):
        """更新箭頭位置和方向"""
        if direction == (0, 0):
            return
            
        # 計算箭頭角度
        angle = math.atan2(direction[1], direction[0])
        
        # 建立箭頭形狀
        arrow_path = QPainterPath()
        
        if self.arrow_style == ArrowStyle.TRIANGLE:
            # 三角形箭頭
            p1 = end_point
            p2 = QPointF(
                end_point.x() - self.arrow_size * math.cos(angle - self.arrow_angle),
                end_point.y() - self.arrow_size * math.sin(angle - self.arrow_angle)
            )
            p3 = QPointF(
                end_point.x() - self.arrow_size * math.cos(angle + self.arrow_angle),
                end_point.y() - self.arrow_size * math.sin(angle + self.arrow_angle)
            )
            
            arrow_path.moveTo(p1)
            arrow_path.lineTo(p2)
            arrow_path.lineTo(p3)
            arrow_path.closeSubpath()
            
        elif self.arrow_style == ArrowStyle.ARROW:
            # 標準箭頭（V型）
            p1 = end_point
            p2 = QPointF(
                end_point.x() - self.arrow_size * math.cos(angle - self.arrow_angle),
                end_point.y() - self.arrow_size * math.sin(angle - self.arrow_angle)
            )
            p3 = QPointF(
                end_point.x() - self.arrow_size * math.cos(angle + self.arrow_angle),
                end_point.y() - self.arrow_size * math.sin(angle + self.arrow_angle)
            )
            
            arrow_path.moveTo(p2)
            arrow_path.lineTo(p1)
            arrow_path.lineTo(p3)
            
        elif self.arrow_style == ArrowStyle.DIAMOND:
            # 菱形箭頭
            p1 = end_point
            p2 = QPointF(
                end_point.x() - self.arrow_size * 0.6 * math.cos(angle),
                end_point.y() - self.arrow_size * 0.6 * math.sin(angle)
            )
            p3 = QPointF(
                p2.x() - self.arrow_size * 0.4 * math.cos(angle - math.pi/2),
                p2.y() - self.arrow_size * 0.4 * math.sin(angle - math.pi/2)
            )
            p4 = QPointF(
                p2.x() - self.arrow_size * 0.4 * math.cos(angle + math.pi/2),
                p2.y() - self.arrow_size * 0.4 * math.sin(angle + math.pi/2)
            )
            p5 = QPointF(
                end_point.x() - self.arrow_size * 1.2 * math.cos(angle),
                end_point.y() - self.arrow_size * 1.2 * math.sin(angle)
            )
            
            arrow_path.moveTo(p1)
            arrow_path.lineTo(p3)
            arrow_path.lineTo(p5)
            arrow_path.lineTo(p4)
            arrow_path.closeSubpath()
            
        elif self.arrow_style == ArrowStyle.CIRCLE:
            # 圓形箭頭
            center = QPointF(
                end_point.x() - self.arrow_size * 0.5 * math.cos(angle),
                end_point.y() - self.arrow_size * 0.5 * math.sin(angle)
            )
            arrow_path.addEllipse(center, self.arrow_size * 0.3, self.arrow_size * 0.3)
        
        self.setPath(arrow_path)
    
    def paint(self, painter: QPainter, option, widget=None):
        """繪製發光箭頭"""
        # 移除預設選取框
        option.state &= ~QStyle.State_Selected
        
        if not self.path().isEmpty():
            # 判斷父邊線的狀態
            is_selected = self.parent_edge.isSelected()
            is_hovered = getattr(self.parent_edge, '_is_hovered', False)
            is_temporary = getattr(self.parent_edge, 'is_temporary', False)
            
            # 根據狀態設定顏色
            if is_temporary:
                # 臨時邊線：灰色
                painter.setBrush(QBrush(QColor(128, 128, 128)))
                painter.setPen(QPen(Qt.NoPen))
                painter.drawPath(self.path())
                
            elif is_selected:
                # 選取狀態：發光效果
                # 外層光暈
                glow_brush = QBrush(QColor(255, 165, 0, 80))
                glow_pen = QPen(QColor(255, 165, 0, 80), 4)
                painter.setBrush(glow_brush)
                painter.setPen(glow_pen)
                painter.drawPath(self.path())
                
                # 中層光暈
                mid_brush = QBrush(QColor(255, 140, 0, 120))
                mid_pen = QPen(QColor(255, 140, 0, 120), 2)
                painter.setBrush(mid_brush)
                painter.setPen(mid_pen)
                painter.drawPath(self.path())
                
                # 核心箭頭
                core_brush = QBrush(QColor(255, 100, 0))
                painter.setBrush(core_brush)
                painter.setPen(QPen(Qt.NoPen))
                painter.drawPath(self.path())
                
            elif is_hovered:
                # 懸停狀態：輕微發光
                # 外層光暈
                glow_brush = QBrush(QColor(100, 100, 255, 60))
                glow_pen = QPen(QColor(100, 100, 255, 60), 3)
                painter.setBrush(glow_brush)
                painter.setPen(glow_pen)
                painter.drawPath(self.path())
                
                # 核心箭頭
                core_brush = QBrush(QColor(50, 50, 200))
                painter.setBrush(core_brush)
                painter.setPen(QPen(Qt.NoPen))
                painter.drawPath(self.path())
                
            else:
                # 正常狀態：黑色
                painter.setBrush(QBrush(Qt.black))
                painter.setPen(QPen(Qt.NoPen))
                painter.drawPath(self.path())


class EnhancedEdgeItem(QGraphicsPathItem):
    """增強型邊線項目 - 支援 yEd 風格路由"""
    
    # 類別變數：共享路由引擎
    _router: Optional[RoutingEngine] = None
    
    @classmethod
    def initialize_router(cls, scene_rect: QRectF, grid_size: float = 10.0):
        """初始化共享路由引擎"""
        cls._router = RoutingEngine(scene_rect, grid_size)
        cls._router.configure(
            default_style=RoutingStyle.ORTHOGONAL,
            node_padding=15.0,
            bend_penalty=0.5,
            max_bends=6,
            parallel_spacing=20.0,
            corner_radius=5.0,
            enable_smoothing=True,
            enable_caching=True
        )
    
    def __init__(self, src_node, dst_node):
        super().__init__()
        
        self.src_node = src_node
        self.dst_node = dst_node
        self.is_temporary = False
        self._is_hovered = False
        
        # 路由配置
        self.routing_style = RoutingStyle.ORTHOGONAL
        self.edge_type = EdgeType.SINGLE
        
        # 樣式設定
        self.normal_pen = QPen(Qt.black, 2, Qt.SolidLine)
        self.hover_pen = QPen(QColor(50, 50, 200), 3, Qt.SolidLine)
        self.selected_pen = QPen(QColor(255, 100, 0), 3, Qt.SolidLine)
        self.temp_pen = QPen(Qt.gray, 2, Qt.DashLine)
        
        self.setPen(self.normal_pen)
        self.setZValue(1)
        
        # 設定旗標
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        # 建立箭頭
        self.arrow_head = GlowArrowHead(self)
        self.arrow_head.setParentItem(self)  # 確保設定父項目
        self.arrow_head.setZValue(3)  # 確保在最上層
        
        # 快取
        self._cached_path = None
        self._cached_src_rect = None
        self._cached_dst_rect = None
        
        # 初始更新
        self.updatePath()
    
    def setTemporary(self, temporary: bool):
        """設定是否為臨時邊線"""
        self.is_temporary = temporary
        if temporary:
            self.setPen(self.temp_pen)
            self.arrow_head.setBrush(QBrush(Qt.gray))
        else:
            self.setPen(self.normal_pen)
            self.arrow_head.setBrush(QBrush(Qt.black))
    
    def updatePath(self):
        """更新路徑 - 使用路由引擎"""
        if not self.src_node or not self.dst_node:
            return
        
        # 取得節點邊界
        src_rect = self.src_node.sceneBoundingRect()
        dst_rect = self.dst_node.sceneBoundingRect()
        
        # 檢查快取
        if (self._cached_path and 
            self._cached_src_rect == src_rect and 
            self._cached_dst_rect == dst_rect):
            return
        
        # 使用路由引擎計算路徑
        if self._router:
            request = RoutingRequest(
                source_rect=src_rect,
                target_rect=dst_rect,
                style=self.routing_style,
                edge_type=self.edge_type
            )
            
            result = self._router.route_edge(request)
            
            if result.success:
                self.setPath(result.path)
                
                # 更新箭頭位置
                if result.segments:
                    last_segment = result.segments[-1]
                    self.arrow_head.updatePosition(last_segment.end, last_segment.direction)
            else:
                # 後備方案：直線連接
                self._drawStraightLine(src_rect, dst_rect)
        else:
            # 沒有路由引擎時使用直線
            self._drawStraightLine(src_rect, dst_rect)
        
        # 更新快取
        self._cached_path = self.path()
        self._cached_src_rect = src_rect
        self._cached_dst_rect = dst_rect
    
    def _drawStraightLine(self, src_rect: QRectF, dst_rect: QRectF):
        """繪製直線連接（後備方案）"""
        src_center = src_rect.center()
        dst_center = dst_rect.center()
        
        # 計算連接點
        src_point = self.getConnectionPoint(src_rect, dst_center)
        dst_point = self.getConnectionPoint(dst_rect, src_center)
        
        # 建立路徑
        path = QPainterPath()
        path.moveTo(src_point)
        path.lineTo(dst_point)
        self.setPath(path)
        
        # 更新箭頭
        dx = dst_point.x() - src_point.x()
        dy = dst_point.y() - src_point.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            direction = (dx / length, dy / length)
            self.arrow_head.updatePosition(dst_point, direction)
    
    def getConnectionPoint(self, rect_or_point, target_or_center=None, dx=None, dy=None) -> QPointF:
        """計算矩形邊緣的連接點 - 支援兩種調用方式"""
        if isinstance(rect_or_point, QRectF) and isinstance(target_or_center, QPointF):
            # 新的調用方式：getConnectionPoint(rect, target_point)
            rect = rect_or_point
            target_point = target_or_center
            center = rect.center()
            dx = target_point.x() - center.x()
            dy = target_point.y() - center.y()
        elif dx is not None and dy is not None:
            # 舊的調用方式：getConnectionPoint(rect, center, dx, dy)
            rect = rect_or_point
            center = target_or_center
        else:
            raise ValueError("Invalid arguments for getConnectionPoint")
        
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return center
        
        # 計算與矩形邊緣的交點
        if abs(dx) > abs(dy):
            # 水平方向為主
            t = (rect.width() / 2) / abs(dx)
            x = center.x() + dx * t * (1 if dx > 0 else -1)
            y = center.y() + dy * t * (1 if dx > 0 else -1)
        else:
            # 垂直方向為主
            t = (rect.height() / 2) / abs(dy)
            x = center.x() + dx * t * (1 if dy > 0 else -1)
            y = center.y() + dy * t * (1 if dy > 0 else -1)
        
        # 確保點在矩形邊界上
        x = max(rect.left(), min(x, rect.right()))
        y = max(rect.top(), min(y, rect.bottom()))
        
        return QPointF(x, y)
    
    def setRoutingStyle(self, style: RoutingStyle):
        """設定路由風格"""
        self.routing_style = style
        self._cached_path = None  # 清除快取
        self.updatePath()
    
    def hoverEnterEvent(self, event):
        """滑鼠進入事件"""
        super().hoverEnterEvent(event)
        self._is_hovered = True
        if not self.isSelected():
            self.setPen(self.hover_pen)
        self.update()
    
    def hoverLeaveEvent(self, event):
        """滑鼠離開事件"""
        super().hoverLeaveEvent(event)
        self._is_hovered = False
        if not self.isSelected():
            self.setPen(self.normal_pen)
        self.update()
    
    def itemChange(self, change, value):
        """項目變更事件"""
        if change == QGraphicsItem.ItemSelectedChange:
            if value:
                self.setPen(self.selected_pen)
            else:
                self.setPen(self.hover_pen if self._is_hovered else self.normal_pen)
            self.update()
        
        return super().itemChange(change, value)
    
    def clearCache(self):
        """清除路徑快取"""
        self._cached_path = None
        self._cached_src_rect = None
        self._cached_dst_rect = None