"""
完整的精確連線系統實施方案
直接替換 dsm_editor.py 中的相關類別
"""

import math
from typing import Optional, List, Tuple
from PyQt5.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt5.QtGui import QPen, QBrush, QPainterPath, QColor
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsRectItem, QGraphicsItem


class PrecisionEdgeItem(QGraphicsPathItem):
    """
    精確連線實現 - 可直接替換原有的 EdgeItem 類
    """
    
    # 精確度常數
    PRECISION_TOLERANCE = 0.01  # 浮點數精度容差
    ARROW_SIZE = 12              # 箭頭大小
    ARROW_ANGLE = math.pi / 6    # 箭頭角度（30度）
    CONNECTION_OFFSET = 0        # 連線偏移（0表示精確接觸）
    ARROW_BACK_OFFSET = 1        # 箭頭後退量
    
    def __init__(self, src: 'TaskNode', dst: 'TaskNode') -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.label = ""
        self.isTemporary = False
        
        # 樣式設定
        self.normalPen = QPen(Qt.black, 2, Qt.SolidLine)
        self.hoverPen = QPen(Qt.black, 3, Qt.SolidLine)
        self.selectedPen = QPen(Qt.blue, 3, Qt.SolidLine)
        self.tempPen = QPen(Qt.gray, 2, Qt.DashLine)
        
        self.setPen(self.normalPen)
        self.setZValue(1)
        
        # 設定旗標
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        # 建立箭頭
        self.arrowHead = QGraphicsPathItem()
        self.arrowHead.setBrush(QBrush(Qt.black))
        self.arrowHead.setPen(QPen(Qt.black, 1))
        self.arrowHead.setZValue(2)
        self.arrowHead.setParentItem(self)
        
        # 效能優化：快取計算結果
        self._cached_src_point = None
        self._cached_dst_point = None
        self._cached_src_rect = None
        self._cached_dst_rect = None
        
        self.updatePath()
    
    def updatePath(self) -> None:
        """
        主要的路徑更新方法
        實現精確的節點邊緣連線
        """
        if not self.src or not self.dst:
            return
        
        # 獲取節點邊界
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()
        
        # 檢查快取
        if (self._cached_src_rect == srcRect and 
            self._cached_dst_rect == dstRect and
            self._cached_src_point and self._cached_dst_point):
            return  # 使用快取結果
        
        # 計算連線點
        srcPoint, dstPoint = self._calculateConnectionPoints(srcRect, dstRect)
        
        if not srcPoint or not dstPoint:
            return
        
        # 快取結果
        self._cached_src_rect = QRectF(srcRect)
        self._cached_dst_rect = QRectF(dstRect)
        self._cached_src_point = srcPoint
        self._cached_dst_point = dstPoint
        
        # 建立路徑
        self._buildPath(srcPoint, dstPoint)
    
    def _calculateConnectionPoints(self, srcRect: QRectF, 
                                  dstRect: QRectF) -> Tuple[QPointF, QPointF]:
        """
        計算源和目標的精確連線點
        """
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()
        
        # 方法1：使用中心線計算交點
        centerLine = QLineF(srcCenter, dstCenter)
        
        # 計算源點
        srcPoint = self._getRectLineIntersection(srcRect, centerLine, True)
        if not srcPoint:
            srcPoint = self._getAlternativeConnectionPoint(srcRect, srcCenter, dstCenter, True)
        
        # 基於源點重新計算到目標的線
        if srcPoint:
            adjustedLine = QLineF(srcPoint, dstCenter)
            dstPoint = self._getRectLineIntersection(dstRect, adjustedLine, False)
            if not dstPoint:
                dstPoint = self._getAlternativeConnectionPoint(dstRect, dstCenter, srcPoint, False)
        else:
            dstPoint = None
        
        return srcPoint, dstPoint
    
    def _getRectLineIntersection(self, rect: QRectF, line: QLineF, 
                                isSource: bool) -> Optional[QPointF]:
        """
        計算線與矩形的精確交點
        使用改進的算法確保精確度
        """
        # 定義矩形的四條邊
        edges = [
            QLineF(rect.topLeft(), rect.topRight()),      # 上
            QLineF(rect.topRight(), rect.bottomRight()),   # 右
            QLineF(rect.bottomRight(), rect.bottomLeft()), # 下
            QLineF(rect.bottomLeft(), rect.topLeft())      # 左
        ]
        
        intersections = []
        
        for edge in edges:
            intersectType, intersectPoint = edge.intersects(line)
            
            # 只接受有界交點
            if intersectType == QLineF.BoundedIntersection:
                # 驗證交點確實在邊上（處理浮點誤差）
                if self._isPointOnEdge(intersectPoint, edge):
                    intersections.append(intersectPoint)
        
        if not intersections:
            return None
        
        # 選擇最合適的交點
        if len(intersections) == 1:
            return intersections[0]
        
        # 多個交點時，選擇策略
        if isSource:
            # 源節點：選擇離目標最近的點
            targetPoint = line.p2()
            return min(intersections, 
                      key=lambda p: QLineF(p, targetPoint).length())
        else:
            # 目標節點：選擇離源最近的點
            sourcePoint = line.p1()
            return min(intersections, 
                      key=lambda p: QLineF(sourcePoint, p).length())
    
    def _isPointOnEdge(self, point: QPointF, edge: QLineF) -> bool:
        """
        檢查點是否真的在邊上（考慮浮點誤差）
        """
        # 計算點到線段的距離
        lineVec = edge.p2() - edge.p1()
        pointVec = point - edge.p1()
        lineLength = edge.length()
        
        if lineLength < self.PRECISION_TOLERANCE:
            return False
        
        # 計算投影
        t = QPointF.dotProduct(pointVec, lineVec) / (lineLength * lineLength)
        
        # 檢查t是否在[0,1]範圍內
        if t < -self.PRECISION_TOLERANCE or t > 1 + self.PRECISION_TOLERANCE:
            return False
        
        # 計算投影點
        projection = edge.p1() + t * lineVec
        
        # 計算距離
        distance = QLineF(point, projection).length()
        
        return distance < self.PRECISION_TOLERANCE
    
    def _getAlternativeConnectionPoint(self, rect: QRectF, 
                                      rectCenter: QPointF,
                                      otherPoint: QPointF,
                                      isSource: bool) -> QPointF:
        """
        備用方法：當標準方法失敗時計算連線點
        """
        # 計算方向
        dx = otherPoint.x() - rectCenter.x()
        dy = otherPoint.y() - rectCenter.y()
        
        if abs(dx) < self.PRECISION_TOLERANCE and abs(dy) < self.PRECISION_TOLERANCE:
            return rectCenter
        
        # 確定主要方向並計算交點
        halfWidth = rect.width() / 2
        halfHeight = rect.height() / 2
        
        # 使用斜率判斷
        if abs(dx) > self.PRECISION_TOLERANCE:
            slope = dy / dx
            
            # 檢查與垂直邊的交點
            if dx > 0:  # 向右
                y_at_right = rectCenter.y() + slope * halfWidth
                if abs(y_at_right) <= halfHeight:
                    return QPointF(rect.right(), rectCenter.y() + y_at_right)
            else:  # 向左
                y_at_left = rectCenter.y() - slope * halfWidth
                if abs(y_at_left) <= halfHeight:
                    return QPointF(rect.left(), rectCenter.y() + y_at_left)
        
        # 檢查與水平邊的交點
        if abs(dy) > self.PRECISION_TOLERANCE:
            inv_slope = dx / dy
            
            if dy > 0:  # 向下
                x_at_bottom = rectCenter.x() + inv_slope * halfHeight
                if abs(x_at_bottom) <= halfWidth:
                    return QPointF(rectCenter.x() + x_at_bottom, rect.bottom())
            else:  # 向上
                x_at_top = rectCenter.x() - inv_slope * halfHeight
                if abs(x_at_top) <= halfWidth:
                    return QPointF(rectCenter.x() + x_at_top, rect.top())
        
        # 最後的備用：返回最近的邊中點
        return self._getNearestEdgeMidpoint(rect, otherPoint)
    
    def _getNearestEdgeMidpoint(self, rect: QRectF, point: QPointF) -> QPointF:
        """
        獲取最近的邊中點作為連線點
        """
        midpoints = [
            QPointF(rect.center().x(), rect.top()),     # 上中
            QPointF(rect.right(), rect.center().y()),    # 右中
            QPointF(rect.center().x(), rect.bottom()),   # 下中
            QPointF(rect.left(), rect.center().y())      # 左中
        ]
        
        return min(midpoints, key=lambda p: QLineF(p, point).length())
    
    def _buildPath(self, srcPoint: QPointF, dstPoint: QPointF) -> None:
        """
        建立連線路徑並更新箭頭
        """
        # 計算調整後的終點（避免箭頭穿透）
        direction = dstPoint - srcPoint
        length = math.sqrt(direction.x()**2 + direction.y()**2)
        
        if length > self.PRECISION_TOLERANCE:
            direction /= length  # 正規化
            adjustedDst = dstPoint - direction * self.ARROW_BACK_OFFSET
        else:
            adjustedDst = dstPoint
        
        # 建立路徑
        path = QPainterPath()
        path.moveTo(srcPoint)
        path.lineTo(adjustedDst)
        self.setPath(path)
        
        # 更新箭頭
        self._updateArrowHead(srcPoint, dstPoint)
    
    def _updateArrowHead(self, srcPos: QPointF, dstPos: QPointF) -> None:
        """
        更新箭頭形狀，確保精確指向目標
        """
        # 計算方向角度
        dx = dstPos.x() - srcPos.x()
        dy = dstPos.y() - srcPos.y()
        
        if abs(dx) < self.PRECISION_TOLERANCE and abs(dy) < self.PRECISION_TOLERANCE:
            self.arrowHead.setPath(QPainterPath())
            return
        
        angle = math.atan2(dy, dx)
        
        # 計算箭頭三個頂點
        tip = dstPos  # 箭頭尖端精確在節點邊緣
        
        left = QPointF(
            tip.x() - self.ARROW_SIZE * math.cos(angle - self.ARROW_ANGLE),
            tip.y() - self.ARROW_SIZE * math.sin(angle - self.ARROW_ANGLE)
        )
        
        right = QPointF(
            tip.x() - self.ARROW_SIZE * math.cos(angle + self.ARROW_ANGLE),
            tip.y() - self.ARROW_SIZE * math.sin(angle + self.ARROW_ANGLE)
        )
        
        # 建立箭頭路徑
        arrowPath = QPainterPath()
        arrowPath.moveTo(tip)
        arrowPath.lineTo(left)
        arrowPath.lineTo(right)
        arrowPath.closeSubpath()
        
        self.arrowHead.setPath(arrowPath)
    
    def setTemporary(self, temporary: bool) -> None:
        """設定是否為臨時連線"""
        self.isTemporary = temporary
        if temporary:
            self.setPen(self.tempPen)
            self.arrowHead.setBrush(QBrush(Qt.gray))
        else:
            self.setPen(self.normalPen)
            self.arrowHead.setBrush(QBrush(Qt.black))
    
    # 保留原有的其他方法...
    def hoverEnterEvent(self, event):
        """滑鼠懸停進入"""
        if not self.isTemporary:
            self.setPen(self.hoverPen)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """滑鼠懸停離開"""
        if not self.isTemporary:
            if self.isSelected():
                self.setPen(self.selectedPen)
            else:
                self.setPen(self.normalPen)
        super().hoverLeaveEvent(event)