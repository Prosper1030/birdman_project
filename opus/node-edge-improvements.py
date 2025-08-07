"""
TaskNode 類的邊緣檢測改進
"""

from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtGui import QPainterPath


class TaskNode(QGraphicsRectItem):
    """節點類的關鍵改進方法"""
    
    def getConnectionPoints(self, targetPoint: QPointF) -> list[QPointF]:
        """
        獲取節點上所有可能的連線點
        返回節點邊緣上的多個候選連線點
        """
        rect = self.rect()
        center = QPointF(rect.center())
        
        # 轉換到場景座標
        sceneRect = self.sceneBoundingRect()
        sceneCenter = sceneRect.center()
        
        # 計算8個標準連線點（類似yEd）
        points = []
        
        # 四個角點
        points.append(sceneRect.topLeft())
        points.append(sceneRect.topRight())
        points.append(sceneRect.bottomLeft())
        points.append(sceneRect.bottomRight())
        
        # 四個邊中點
        points.append(QPointF(sceneCenter.x(), sceneRect.top()))      # 上中
        points.append(QPointF(sceneCenter.x(), sceneRect.bottom()))   # 下中
        points.append(QPointF(sceneRect.left(), sceneCenter.y()))     # 左中
        points.append(QPointF(sceneRect.right(), sceneCenter.y()))    # 右中
        
        # 根據目標點方向添加額外的連線點
        dx = targetPoint.x() - sceneCenter.x()
        dy = targetPoint.y() - sceneCenter.y()
        
        if abs(dx) > abs(dy):  # 水平方向為主
            # 添加垂直邊上的額外點
            y_positions = [
                sceneRect.top() + sceneRect.height() * 0.25,
                sceneRect.top() + sceneRect.height() * 0.75
            ]
            for y in y_positions:
                if dx > 0:  # 向右
                    points.append(QPointF(sceneRect.right(), y))
                else:  # 向左
                    points.append(QPointF(sceneRect.left(), y))
        else:  # 垂直方向為主
            # 添加水平邊上的額外點
            x_positions = [
                sceneRect.left() + sceneRect.width() * 0.25,
                sceneRect.left() + sceneRect.width() * 0.75
            ]
            for x in x_positions:
                if dy > 0:  # 向下
                    points.append(QPointF(x, sceneRect.bottom()))
                else:  # 向上
                    points.append(QPointF(x, sceneRect.top()))
        
        return points
    
    def getNearestConnectionPoint(self, fromPoint: QPointF) -> QPointF:
        """
        獲取離指定點最近的連線點
        這確保連線始終從最合適的位置開始/結束
        """
        points = self.getConnectionPoints(fromPoint)
        
        if not points:
            return self.sceneBoundingRect().center()
        
        # 找出最近的點
        minDistance = float('inf')
        nearestPoint = points[0]
        
        for point in points:
            distance = QLineF(fromPoint, point).length()
            if distance < minDistance:
                minDistance = distance
                nearestPoint = point
        
        return nearestPoint
    
    def getSmartConnectionPoint(self, direction: QPointF, 
                               isSource: bool = True) -> QPointF:
        """
        智能連線點選擇
        根據連線方向和節點角色（源/目標）選擇最佳連線點
        
        Args:
            direction: 連線的方向向量
            isSource: 是否為源節點
        
        Returns:
            最佳連線點
        """
        rect = self.sceneBoundingRect()
        center = rect.center()
        
        # 歸一化方向向量
        dx = direction.x()
        dy = direction.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 0.001:
            # 如果方向不明確，返回中心點
            return center
        
        dx /= length
        dy /= length
        
        # 判斷主要方向
        if abs(dx) > abs(dy):
            # 水平方向為主
            if dx > 0:
                # 向右連線，使用右邊緣
                x = rect.right()
                # 根據dy調整y位置
                y = center.y() + dy * rect.height() * 0.3
                y = max(rect.top(), min(rect.bottom(), y))
            else:
                # 向左連線，使用左邊緣
                x = rect.left()
                y = center.y() + dy * rect.height() * 0.3
                y = max(rect.top(), min(rect.bottom(), y))
        else:
            # 垂直方向為主
            if dy > 0:
                # 向下連線，使用下邊緣
                y = rect.bottom()
                x = center.x() + dx * rect.width() * 0.3
                x = max(rect.left(), min(rect.right(), x))
            else:
                # 向上連線，使用上邊緣
                y = rect.top()
                x = center.x() + dx * rect.width() * 0.3
                x = max(rect.left(), min(rect.right(), x))
        
        return QPointF(x, y)
    
    def adjustConnectionPointForRoundedCorners(self, point: QPointF, 
                                              cornerRadius: float = 5) -> QPointF:
        """
        為圓角矩形調整連線點
        確保連線點在圓角邊緣上而不是尖角上
        """
        rect = self.sceneBoundingRect()
        center = rect.center()
        
        # 檢查點是否在角落區域
        isCorner = False
        cornerRect = QRectF()
        
        # 左上角
        if (point.x() - rect.left() < cornerRadius and 
            point.y() - rect.top() < cornerRadius):
            isCorner = True
            cornerRect = QRectF(rect.left(), rect.top(), 
                              cornerRadius * 2, cornerRadius * 2)
            cornerCenter = QPointF(rect.left() + cornerRadius, 
                                  rect.top() + cornerRadius)
        # 右上角
        elif (rect.right() - point.x() < cornerRadius and 
              point.y() - rect.top() < cornerRadius):
            isCorner = True
            cornerRect = QRectF(rect.right() - cornerRadius * 2, rect.top(), 
                              cornerRadius * 2, cornerRadius * 2)
            cornerCenter = QPointF(rect.right() - cornerRadius, 
                                  rect.top() + cornerRadius)
        # 左下角
        elif (point.x() - rect.left() < cornerRadius and 
              rect.bottom() - point.y() < cornerRadius):
            isCorner = True
            cornerRect = QRectF(rect.left(), rect.bottom() - cornerRadius * 2, 
                              cornerRadius * 2, cornerRadius * 2)
            cornerCenter = QPointF(rect.left() + cornerRadius, 
                                  rect.bottom() - cornerRadius)
        # 右下角
        elif (rect.right() - point.x() < cornerRadius and 
              rect.bottom() - point.y() < cornerRadius):
            isCorner = True
            cornerRect = QRectF(rect.right() - cornerRadius * 2, 
                              rect.bottom() - cornerRadius * 2, 
                              cornerRadius * 2, cornerRadius * 2)
            cornerCenter = QPointF(rect.right() - cornerRadius, 
                                  rect.bottom() - cornerRadius)
        
        if isCorner:
            # 計算點在圓角上的位置
            angle = math.atan2(point.y() - cornerCenter.y(), 
                              point.x() - cornerCenter.x())
            adjustedX = cornerCenter.x() + cornerRadius * math.cos(angle)
            adjustedY = cornerCenter.y() + cornerRadius * math.sin(angle)
            return QPointF(adjustedX, adjustedY)
        
        return point