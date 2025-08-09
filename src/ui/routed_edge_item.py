"""
可路由邊線繪製元件
Routed Edge Item Component

支援 polyline 路徑的邊線繪製，為未來整合 EdgeRoutingEngine 做準備。
"""

from typing import List, Optional, Tuple
from PyQt5.QtWidgets import QGraphicsPathItem
from PyQt5.QtGui import QPainterPath, QPen, QBrush, QColor, QPainter
from PyQt5.QtCore import QPointF, Qt, QRectF


class RoutedEdgeItem(QGraphicsPathItem):
    """
    支援 polyline 路徑的邊線繪製元件。
    
    可接收一系列點來繪製折線路徑，為未來整合智慧路由做準備。
    
    TODO(next): 
        - 支援平行邊偏移（多條邊之間的間距）
        - 實作選取樣式與發光效果
        - 加入 hover 提示與互動
        - 整合 EdgeRoutingEngine 自動路由
        - 支援箭頭繪製
        - 加入標籤顯示
    """
    
    def __init__(self, points: List[QPointF] = None, parent=None):
        """
        初始化路由邊線。
        
        Args:
            points: 路徑點列表，至少需要 2 個點
            parent: 父項目
        """
        super().__init__(parent)
        
        # 基本屬性
        self.setZValue(-1)  # 放在節點下方
        self.setAcceptedMouseButtons(Qt.NoButton)  # 暫時不接受滑鼠事件
        
        # 路徑點
        self._points = points or []
        
        # 樣式設定
        self._pen = QPen(Qt.gray, 1.25)
        self._pen.setCapStyle(Qt.RoundCap)
        self._pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(self._pen)
        self.setBrush(Qt.NoBrush)
        
        # 選取狀態
        self._is_selected = False
        self._is_hovered = False
        
        # 平行邊偏移
        self._parallel_offset = 0.0  # 偏移量（像素）
        
        # 箭頭設定
        self._show_arrow = False
        self._arrow_size = 10.0
        
        # 標籤
        self._label = ""
        self._label_position = 0.5  # 標籤在路徑上的位置（0-1）
        
        # 更新路徑
        self.update_path()
    
    def set_points(self, points: List[QPointF]):
        """
        設定路徑點。
        
        Args:
            points: 新的路徑點列表
        """
        self._points = points or []
        self.update_path()
    
    def get_points(self) -> List[QPointF]:
        """
        獲取當前路徑點。
        
        Returns:
            路徑點列表的副本
        """
        return self._points.copy()
    
    def set_parallel_offset(self, offset: float):
        """
        設定平行邊偏移量。
        
        用於多條平行邊之間的視覺分離。
        
        Args:
            offset: 偏移量（像素），正值向右/上偏移，負值向左/下偏移
        
        TODO(next): 實作偏移計算邏輯
        """
        self._parallel_offset = offset
        self.update_path()
    
    def set_selected(self, selected: bool):
        """
        設定選取狀態。
        
        Args:
            selected: 是否選取
        
        TODO(next): 實作選取樣式變化
        """
        self._is_selected = selected
        self._update_style()
    
    def set_hovered(self, hovered: bool):
        """
        設定懸停狀態。
        
        Args:
            hovered: 是否懸停
        
        TODO(next): 實作懸停樣式變化
        """
        self._is_hovered = hovered
        self._update_style()
    
    def set_show_arrow(self, show: bool):
        """
        設定是否顯示箭頭。
        
        Args:
            show: 是否顯示箭頭
        
        TODO(next): 實作箭頭繪製
        """
        self._show_arrow = show
        self.update_path()
    
    def set_label(self, label: str, position: float = 0.5):
        """
        設定標籤文字。
        
        Args:
            label: 標籤文字
            position: 標籤在路徑上的位置（0-1）
        
        TODO(next): 實作標籤繪製
        """
        self._label = label
        self._label_position = max(0.0, min(1.0, position))
        self.update()
    
    def update_path(self):
        """
        更新繪製路徑。
        
        根據當前的點列表和設定更新 QPainterPath。
        """
        path = QPainterPath()
        pts = self._points
        
        if not pts:
            self.setPath(path)
            return
        
        if len(pts) < 2:
            # 至少需要兩個點
            self.setPath(path)
            return
        
        # TODO(next): 實作平行偏移計算
        # if self._parallel_offset != 0:
        #     pts = self._calculate_offset_points(pts, self._parallel_offset)
        
        # 繪製主路徑
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        
        # TODO(next): 實作箭頭繪製
        # if self._show_arrow and len(pts) >= 2:
        #     arrow_path = self._create_arrow_path(pts[-2], pts[-1])
        #     path.addPath(arrow_path)
        
        self.setPath(path)
    
    def _update_style(self):
        """
        根據狀態更新繪製樣式。
        
        TODO(next): 實作不同狀態的視覺樣式
        """
        if self._is_selected:
            # 選取狀態：加粗、變色
            pen = QPen(QColor(0, 120, 215), 2.0)
        elif self._is_hovered:
            # 懸停狀態：稍微加粗
            pen = QPen(Qt.darkGray, 1.5)
        else:
            # 正常狀態
            pen = QPen(Qt.gray, 1.25)
        
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
    
    def _calculate_offset_points(self, points: List[QPointF], offset: float) -> List[QPointF]:
        """
        計算偏移後的點列表（骨架，尚未實作）。
        
        Args:
            points: 原始點列表
            offset: 偏移量
        
        Returns:
            偏移後的點列表
        
        TODO(next): 實作平行偏移演算法
        """
        # TODO: 計算每個線段的法向量
        # TODO: 根據偏移量移動點
        # TODO: 處理轉角的平滑連接
        return points
    
    def _create_arrow_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        """
        創建箭頭路徑（骨架，尚未實作）。
        
        Args:
            start: 箭頭起始點（倒數第二個點）
            end: 箭頭終點（最後一個點）
        
        Returns:
            箭頭的 QPainterPath
        
        TODO(next): 實作箭頭繪製
        """
        arrow_path = QPainterPath()
        # TODO: 計算箭頭方向
        # TODO: 計算箭頭三個頂點
        # TODO: 繪製填充的三角形
        return arrow_path
    
    def paint(self, painter: QPainter, option, widget=None):
        """
        自訂繪製方法。
        
        Args:
            painter: 繪製器
            option: 繪製選項
            widget: 繪製目標 widget
        
        TODO(next): 實作標籤繪製和發光效果
        """
        # 繪製主路徑（由父類處理）
        super().paint(painter, option, widget)
        
        # TODO(next): 繪製標籤
        # if self._label:
        #     self._draw_label(painter)
        
        # TODO(next): 繪製選取/懸停發光效果
        # if self._is_selected or self._is_hovered:
        #     self._draw_glow(painter)
    
    def _draw_label(self, painter: QPainter):
        """
        繪製標籤（骨架，尚未實作）。
        
        Args:
            painter: 繪製器
        
        TODO(next): 實作標籤繪製
        """
        # TODO: 計算標籤位置
        # TODO: 計算標籤角度
        # TODO: 繪製背景框
        # TODO: 繪製文字
        pass
    
    def _draw_glow(self, painter: QPainter):
        """
        繪製發光效果（骨架，尚未實作）。
        
        Args:
            painter: 繪製器
        
        TODO(next): 實作發光效果
        """
        # TODO: 使用較粗的半透明筆刷重繪路徑
        # TODO: 可能需要多層漸變效果
        pass
    
    def boundingRect(self) -> QRectF:
        """
        返回邊界矩形。
        
        Returns:
            包含整個邊線的邊界矩形
        """
        # 獲取路徑的邊界矩形
        rect = super().boundingRect()
        
        # 擴展以包含筆刷寬度
        pen_width = self.pen().widthF()
        margin = pen_width / 2.0 + 1.0
        
        # TODO(next): 考慮箭頭和標籤的邊界
        
        return rect.adjusted(-margin, -margin, margin, margin)
    
    def shape(self) -> QPainterPath:
        """
        返回用於碰撞檢測的形狀。
        
        Returns:
            擴展後的路徑形狀，便於選取
        
        TODO(next): 擴大選取區域以改善使用體驗
        """
        # 暫時使用預設形狀
        return super().shape()
        
        # TODO: 使用 QPainterPathStroker 擴大路徑
        # from PyQt5.QtGui import QPainterPathStroker
        # stroker = QPainterPathStroker()
        # stroker.setWidth(10.0)  # 擴大選取區域
        # return stroker.createStroke(self.path())


class RoutedEdgeManager:
    """
    路由邊線管理器（骨架）。
    
    管理多條邊線的路由和佈局。
    
    TODO(next): 實作邊線管理邏輯
    """
    
    def __init__(self):
        """初始化管理器。"""
        self.edges: List[RoutedEdgeItem] = []
        self.routing_engine = None  # 未來整合 EdgeRoutingEngine
    
    def add_edge(self, edge: RoutedEdgeItem):
        """
        添加邊線。
        
        Args:
            edge: 要添加的邊線
        """
        self.edges.append(edge)
        self._update_parallel_offsets()
    
    def remove_edge(self, edge: RoutedEdgeItem):
        """
        移除邊線。
        
        Args:
            edge: 要移除的邊線
        """
        if edge in self.edges:
            self.edges.remove(edge)
            self._update_parallel_offsets()
    
    def _update_parallel_offsets(self):
        """
        更新平行邊的偏移量。
        
        TODO(next): 實作平行邊偏移計算
        """
        # TODO: 檢測平行邊
        # TODO: 計算適當的偏移量
        # TODO: 應用偏移
        pass
    
    def route_all_edges(self):
        """
        對所有邊線進行路由。
        
        TODO(next): 整合 EdgeRoutingEngine
        """
        # TODO: 使用 routing_engine 計算路徑
        # TODO: 更新每條邊的點列表
        pass