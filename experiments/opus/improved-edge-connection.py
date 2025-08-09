"""
改進的 EdgeItem 類 - 實現精確的節點邊緣連線
"""

import math
from PyQt5.QtCore import QPointF, QLineF, QRectF
from PyQt5.QtGui import QPen, QBrush, QPainterPath, QPolygonF
from PyQt5.QtWidgets import QGraphicsPathItem
from PyQt5.QtCore import Qt


class EdgeItem(QGraphicsPathItem):
    """代表依賴關係的箭頭連線 - 精確連線版本"""

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

        # 箭頭參數
        self.arrowSize = 12  # 箭頭大小
        self.arrowAngle = math.pi / 6  # 箭頭角度 (30度)
        
        # 精確度參數
        self.connectionOffset = 0  # 連線偏移量，設為0以確保精確接觸
        self.arrowBackOffset = 1  # 箭頭後退量，避免箭頭與節點重疊

        self.updatePath()

    def setTemporary(self, temporary: bool) -> None:
        """設定是否為臨時連線"""
        self.isTemporary = temporary
        if temporary:
            self.setPen(self.tempPen)
            self.arrowHead.setBrush(QBrush(Qt.gray))
        else:
            self.setPen(self.normalPen)
            self.arrowHead.setBrush(QBrush(Qt.black))

    def updatePath(self) -> None:
        """更新路徑 - 使用精確的交點計算"""
        if not self.src or not self.dst:
            return

        # 獲取節點的場景邊界矩形
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()

        # 獲取中心點
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()

        # 建立中心連線
        centerLine = QLineF(srcCenter, dstCenter)
        
        # 計算精確的交點
        srcPoint = self.getExactIntersectionPoint(srcRect, centerLine, True)
        dstPoint = self.getExactIntersectionPoint(dstRect, centerLine, False)

        # 如果交點計算失敗，使用備用方法
        if not srcPoint:
            srcPoint = self.getFallbackConnectionPoint(srcRect, srcCenter, dstCenter)
        if not dstPoint:
            dstPoint = self.getFallbackConnectionPoint(dstRect, dstCenter, srcCenter)

        # 建立路徑
        path = QPainterPath()
        path.moveTo(srcPoint)
        
        # 計算箭頭調整後的終點
        adjustedDstPoint = self.calculateArrowAdjustedEndpoint(srcPoint, dstPoint)
        path.lineTo(adjustedDstPoint)
        
        self.setPath(path)

        # 更新箭頭
        self.updateArrowHead(srcPoint, dstPoint, adjustedDstPoint)

    def getExactIntersectionPoint(self, rect: QRectF, line: QLineF, isSource: bool) -> QPointF:
        """
        計算線段與矩形的精確交點
        使用參數方程求解線段與矩形四條邊的交點
        """
        # 獲取矩形的四條邊
        edges = [
            QLineF(rect.topLeft(), rect.topRight()),      # 上邊
            QLineF(rect.topRight(), rect.bottomRight()),   # 右邊
            QLineF(rect.bottomRight(), rect.bottomLeft()), # 下邊
            QLineF(rect.bottomLeft(), rect.topLeft())      # 左邊
        ]
        
        # 找出所有交點
        intersections = []
        for edge in edges:
            intersectType, intersectPoint = edge.intersects(line)
            if intersectType == QLineF.BoundedIntersection:
                # 檢查交點是否在邊緣上（避免浮點誤差）
                if self.isPointOnLineSegment(intersectPoint, edge):
                    intersections.append(intersectPoint)
        
        # 選擇合適的交點
        if not intersections:
            return None
        
        # 如果是源節點，選擇離目標最近的交點
        # 如果是目標節點，選擇離源最近的交點
        if isSource:
            targetPoint = line.p2()
            return min(intersections, 
                      key=lambda p: QLineF(p, targetPoint).length())
        else:
            sourcePoint = line.p1()
            return min(intersections, 
                      key=lambda p: QLineF(sourcePoint, p).length())

    def isPointOnLineSegment(self, point: QPointF, line: QLineF, 
                           tolerance: float = 0.1) -> bool:
        """
        檢查點是否在線段上（考慮浮點誤差）
        """
        # 計算點到線段的距離
        lineVector = line.p2() - line.p1()
        pointVector = point - line.p1()
        
        lineLength = line.length()
        if lineLength < 0.001:  # 線段太短
            return False
        
        # 計算投影長度
        projection = QPointF.dotProduct(pointVector, lineVector) / (lineLength * lineLength)
        
        # 檢查投影是否在線段範圍內
        if projection < -tolerance or projection > 1.0 + tolerance:
            return False
        
        # 計算點到線段的垂直距離
        projectedPoint = line.p1() + projection * lineVector
        distance = QLineF(point, projectedPoint).length()
        
        return distance < tolerance

    def getFallbackConnectionPoint(self, rect: QRectF, fromPoint: QPointF, 
                                  toPoint: QPointF) -> QPointF:
        """
        備用連線點計算方法（當精確交點計算失敗時使用）
        使用改進的算法確保連線精確接觸節點邊緣
        """
        center = rect.center()
        dx = toPoint.x() - fromPoint.x()
        dy = toPoint.y() - fromPoint.y()
        
        # 歸一化方向向量
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.001:
            return center
        
        dx /= length
        dy /= length
        
        # 計算半寬和半高
        halfWidth = rect.width() / 2
        halfHeight = rect.height() / 2
        
        # 使用更精確的交點計算
        # 計算射線與矩形邊界的參數t
        if abs(dx) > 0.001:
            t_left = (-halfWidth) / dx
            t_right = halfWidth / dx
        else:
            t_left = float('-inf')
            t_right = float('inf')
        
        if abs(dy) > 0.001:
            t_top = (-halfHeight) / dy
            t_bottom = halfHeight / dy
        else:
            t_top = float('-inf')
            t_bottom = float('inf')
        
        # 確保方向正確
        if t_left > t_right:
            t_left, t_right = t_right, t_left
        if t_top > t_bottom:
            t_top, t_bottom = t_bottom, t_top
        
        # 找出射線進入矩形的參數
        t_enter = max(t_left, t_top)
        t_exit = min(t_right, t_bottom)
        
        # 使用適當的參數計算交點
        if dx > 0:  # 向右
            t = t_exit if t_exit > 0 else t_enter
        else:  # 向左
            t = t_enter if t_enter < 0 else t_exit
        
        # 計算最終交點
        x = center.x() + t * dx
        y = center.y() + t * dy
        
        # 確保點確實在矩形邊緣上（修正浮點誤差）
        x = max(rect.left(), min(rect.right(), x))
        y = max(rect.top(), min(rect.bottom(), y))
        
        return QPointF(x, y)

    def calculateArrowAdjustedEndpoint(self, srcPoint: QPointF, 
                                      dstPoint: QPointF) -> QPointF:
        """
        計算考慮箭頭大小後的調整終點
        確保箭頭尖端精確接觸節點邊緣
        """
        # 計算方向向量
        dx = dstPoint.x() - srcPoint.x()
        dy = dstPoint.y() - srcPoint.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 0.001:
            return dstPoint
        
        # 歸一化
        dx /= length
        dy /= length
        
        # 稍微後退以避免箭頭穿透節點
        # 後退距離為箭頭的一半長度
        backOffset = self.arrowBackOffset
        adjustedX = dstPoint.x() - dx * backOffset
        adjustedY = dstPoint.y() - dy * backOffset
        
        return QPointF(adjustedX, adjustedY)

    def updateArrowHead(self, srcPos: QPointF, dstPos: QPointF, 
                       adjustedDstPos: QPointF) -> None:
        """
        更新箭頭 - 使用精確的箭頭繪製
        箭頭尖端應該精確指向目標節點邊緣
        """
        # 計算方向
        dx = dstPos.x() - srcPos.x()
        dy = dstPos.y() - srcPos.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 0.001:
            self.arrowHead.setPath(QPainterPath())
            return
        
        # 計算角度
        angle = math.atan2(dy, dx)
        
        # 箭頭尖端位於目標點
        tip = dstPos
        
        # 計算箭頭的兩個基點
        leftAngle = angle - self.arrowAngle
        rightAngle = angle + self.arrowAngle
        
        left = QPointF(
            tip.x() - self.arrowSize * math.cos(leftAngle),
            tip.y() - self.arrowSize * math.sin(leftAngle)
        )
        right = QPointF(
            tip.x() - self.arrowSize * math.cos(rightAngle),
            tip.y() - self.arrowSize * math.sin(rightAngle)
        )
        
        # 建立箭頭路徑
        arrowPath = QPainterPath()
        arrowPath.moveTo(tip)
        arrowPath.lineTo(left)
        arrowPath.lineTo(right)
        arrowPath.closeSubpath()
        
        self.arrowHead.setPath(arrowPath)

    def getConnectionPoint(self, rect: QRectF, center: QPointF, 
                          dx: float, dy: float) -> QPointF:
        """
        保留的相容性方法
        現在調用更精確的 getFallbackConnectionPoint
        """
        targetPoint = QPointF(center.x() + dx * 1000, center.y() + dy * 1000)
        return self.getFallbackConnectionPoint(rect, center, targetPoint)

    # ... 其餘方法保持不變 ...