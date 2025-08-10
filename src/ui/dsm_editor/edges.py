from __future__ import annotations

import math
from typing import TYPE_CHECKING
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF
from PyQt5.QtGui import QColor, QBrush, QPen, QPainterPath, QPainterPathStroker
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItem, QMenu

if TYPE_CHECKING:
    from .nodes import TaskNode

from .commands import RemoveEdgeCommand


class GlowArrowHead(QGraphicsPathItem):
    """支援發光效果的箭頭"""

    def __init__(self, parent_edge):
        super().__init__()
        self.parent_edge = parent_edge

    def paint(self, painter, option, widget=None):
        """繪製發光箭頭 - 支援所有狀態"""
        try:
            # 移除預設選取框
            from PyQt5.QtWidgets import QStyle
            option.state &= ~QStyle.State_Selected

            if not self.path().isEmpty():
                # 判斷父邊線的狀態
                is_selected = getattr(self.parent_edge, '_is_selected', False)
                is_shift_highlighted = getattr(self.parent_edge, '_is_shift_highlighted', False)
                is_hovered = getattr(self.parent_edge, '_is_hovered', False)

                # 繪製發光效果（與父邊線同步）
                if is_shift_highlighted:
                    # Shift + 懸停：最亮的發光效果
                    glow_brush = QBrush(QColor(255, 220, 50, 150))
                    glow_pen = QPen(QColor(255, 220, 50, 150), 4)
                    painter.setBrush(glow_brush)
                    painter.setPen(glow_pen)
                    painter.drawPath(self.path())

                    mid_brush = QBrush(QColor(255, 200, 50, 200))
                    mid_pen = QPen(QColor(255, 200, 50, 200), 2)
                    painter.setBrush(mid_brush)
                    painter.setPen(mid_pen)
                    painter.drawPath(self.path())

                elif is_selected:
                    # 選取狀態：橘色發光效果
                    glow_brush = QBrush(QColor(255, 165, 0, 120))
                    glow_pen = QPen(QColor(255, 165, 0, 120), 3)
                    painter.setBrush(glow_brush)
                    painter.setPen(glow_pen)
                    painter.drawPath(self.path())

                    mid_brush = QBrush(QColor(255, 165, 0, 180))
                    mid_pen = QPen(QColor(255, 165, 0, 180), 1)
                    painter.setBrush(mid_brush)
                    painter.setPen(mid_pen)
                    painter.drawPath(self.path())

                elif is_hovered:
                    # 普通懸停：淡淡的發光
                    glow_brush = QBrush(QColor(255, 165, 0, 80))
                    glow_pen = QPen(QColor(255, 165, 0, 80), 2)
                    painter.setBrush(glow_brush)
                    painter.setPen(glow_pen)
                    painter.drawPath(self.path())

                # 永遠繪製主要黑色箭頭
                painter.setBrush(QBrush(Qt.black))
                painter.setPen(QPen(Qt.black, 1))
                painter.drawPath(self.path())

        except Exception as e:
            print(f"GlowArrowHead paint error: {e}")
            super().paint(painter, option, widget)


class EdgeItem(QGraphicsPathItem):
    """代表依賴關係的箭頭連線 - 精確連線版本"""

    # 精確度常數（從 opus 改進方案）
    PRECISION_TOLERANCE = 0.01
    ARROW_SIZE = 15
    ARROW_ANGLE = math.pi / 6
    ARROW_BACK_OFFSET = 1

    def __init__(self, src: TaskNode, dst: TaskNode) -> None:
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
        self.setZValue(5)  # 提高邊線的 Z 值，確保在節點下方但高於背景

        # 設定旗標
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 建立箭頭 - 使用自定義類別支援發光效果
        self.arrowHead = GlowArrowHead(self)
        self.arrowHead.setZValue(15)  # 確保箭頭在所有節點之上
        self.arrowHead.setParentItem(self)

        # 精確連線系統：效能優化快取
        self._cached_src_point = None
        self._cached_dst_point = None
        self._cached_src_rect = None
        self._cached_dst_rect = None

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

    def updatePath(self, custom_ports=None) -> None:
        """
        更新路徑 - 支援 yEd 式精確端口

        Args:
            custom_ports: Optional[(src_x, src_y), (dst_x, dst_y)] 來自佈局引擎的精確端口座標
        """
        if not self.src or not self.dst:
            return

        # 優先使用佈局引擎提供的精確端口
        if custom_ports and len(custom_ports) == 2:
            srcPoint = QPointF(custom_ports[0][0], custom_ports[0][1])
            dstPoint = QPointF(custom_ports[1][0], custom_ports[1][1])

            # 建立路徑（跳過快取檢查）
            self._buildPath(srcPoint, dstPoint)
            print(f"使用精確端口 - 源: {custom_ports[0]}, 目標: {custom_ports[1]}")
            return

        # 獲取節點邊界
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()

        # 檢查快取
        if (self._cached_src_rect == srcRect and
            self._cached_dst_rect == dstRect and
            self._cached_src_point and self._cached_dst_point):
            return  # 使用快取結果

        # 計算連線點（備用方法）
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

    def _calculateConnectionPoints(self, srcRect: QRectF, dstRect: QRectF):
        """計算源和目標的精確連線點（opus 改進）"""
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()

        # 使用中心線計算交點
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

    def _getRectLineIntersection(self, rect: QRectF, line: QLineF, isSource: bool):
        """計算線與矩形的精確交點（opus 改進）"""
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
        """檢查點是否真的在邊上（考慮浮點誤差）"""
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

    def _getAlternativeConnectionPoint(self, rect: QRectF, rectCenter: QPointF,
                                     otherPoint: QPointF, isSource: bool) -> QPointF:
        """備用方法：當標準方法失敗時計算連線點（opus 改進）"""
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
                if abs(y_at_right - rectCenter.y()) <= halfHeight:
                    return QPointF(rect.right(), y_at_right)
            else:  # 向左
                y_at_left = rectCenter.y() - slope * halfWidth
                if abs(y_at_left - rectCenter.y()) <= halfHeight:
                    return QPointF(rect.left(), y_at_left)

        # 檢查與水平邊的交點
        if abs(dy) > self.PRECISION_TOLERANCE:
            inv_slope = dx / dy

            if dy > 0:  # 向下
                x_at_bottom = rectCenter.x() + inv_slope * halfHeight
                if abs(x_at_bottom - rectCenter.x()) <= halfWidth:
                    return QPointF(x_at_bottom, rect.bottom())
            else:  # 向上
                x_at_top = rectCenter.x() - inv_slope * halfHeight
                if abs(x_at_top - rectCenter.x()) <= halfWidth:
                    return QPointF(x_at_top, rect.top())

        # 最後的備用：返回最近的邊中點
        return self._getNearestEdgeMidpoint(rect, otherPoint)

    def _getNearestEdgeMidpoint(self, rect: QRectF, point: QPointF) -> QPointF:
        """獲取最近的邊中點作為連線點（opus 改進）"""
        midpoints = [
            QPointF(rect.center().x(), rect.top()),     # 上中
            QPointF(rect.right(), rect.center().y()),    # 右中
            QPointF(rect.center().x(), rect.bottom()),   # 下中
            QPointF(rect.left(), rect.center().y())      # 左中
        ]

        return min(midpoints, key=lambda p: QLineF(p, point).length())

    def set_complex_path(self, path_points: list):
        """
        根據一個點列表（例如來自路由器的結果）設定複雜路徑。
        這個方法會處理 QPainterPath 的轉換並更新箭頭。
        """
        if not path_points or len(path_points) < 2:
            self.setPath(QPainterPath())
            if hasattr(self, 'arrowHead'):
                self.arrowHead.setPath(QPainterPath())
            return

        # 1. 將點列表 (list) 轉換為 QPainterPath
        painter_path = QPainterPath(path_points[0])
        for point in path_points[1:]:
            painter_path.lineTo(point)

        # 2. 設定邊線的路徑
        self.setPath(painter_path)

        # 3. 根據路徑的最後一段來更新箭頭的位置
        if hasattr(self, '_updateArrowHead'):
            self._updateArrowHead(path_points[-2], path_points[-1])

    def set_path_from_ports(self, src_port: QPointF, dst_port: QPointF):
        """
        根據佈局引擎計算好的 Port 座標來設定路徑，
        這會繞過預設的動態交點計算。
        """
        # 清除快取，強制使用新的 Port 座標
        self._cached_src_point = None
        self._cached_dst_point = None
        self._cached_src_rect = None
        self._cached_dst_rect = None
        
        # 直接使用 Port 座標建立路徑
        self._buildPath(src_port, dst_port)
        print(f"[DEBUG] 使用 Port 座標建立路徑: {src_port} -> {dst_port}")

    def _buildPath(self, srcPoint: QPointF, dstPoint: QPointF) -> None:
        """建立連線路徑並更新箭頭（opus 改進）- 支援雙向邊線分離"""
        # 檢查是否有相反方向的邊線
        reverse_edge_exists = False
        if hasattr(self.src, 'editor') and self.src.editor:
            reverse_key = (self.dst.taskId, self.src.taskId)
            if reverse_key in self.src.editor.edges:
                reverse_edge_exists = True

        # 計算調整後的終點（避免箭頭穿透）
        direction = dstPoint - srcPoint
        length = math.sqrt(direction.x()**2 + direction.y()**2)

        if length > self.PRECISION_TOLERANCE:
            direction /= length  # 正規化
            adjustedDst = dstPoint - direction * self.ARROW_BACK_OFFSET

            # 如果有相反方向邊線，調整路徑避免重疊
            if reverse_edge_exists:
                # 計算垂直於連線方向的偏移向量
                perpendicular = QPointF(-direction.y(), direction.x())
                offset_distance = 8  # 偏移 8 像素

                # 偏移起點和終點
                srcPoint = srcPoint + perpendicular * offset_distance
                adjustedDst = adjustedDst + perpendicular * offset_distance
                dstPoint = dstPoint + perpendicular * offset_distance
        else:
            adjustedDst = dstPoint

        # 建立路徑
        path = QPainterPath()
        path.moveTo(srcPoint)
        path.lineTo(adjustedDst)
        self.setPath(path)

        # 更新箭頭
        self._updateArrowHead(srcPoint, dstPoint)

    def getConnectionPoint(self, rect, center, dx, dy):
        """保留的相容性方法 - 現在調用更精確的方法"""
        targetPoint = QPointF(center.x() + dx * 1000, center.y() + dy * 1000)
        return self._getAlternativeConnectionPoint(rect, center, targetPoint, True)

    def _updateArrowHead(self, srcPos: QPointF, dstPos: QPointF) -> None:
        """
        更新箭頭形狀，確保精確指向目標（opus 改進）
        修正：確保箭頭在節點邊界上而不是端口內部
        """
        # 計算方向角度
        dx = dstPos.x() - srcPos.x()
        dy = dstPos.y() - srcPos.y()

        if abs(dx) < self.PRECISION_TOLERANCE and abs(dy) < self.PRECISION_TOLERANCE:
            self.arrowHead.setPath(QPainterPath())
            return

        angle = math.atan2(dy, dx)

        # 確保箭頭 tip 在目標節點的實際邊界上
        # 如果使用了精確端口，需要調整箭頭位置避免被節點遮擋
        if hasattr(self, 'dst') and self.dst:
            dst_rect = self.dst.sceneBoundingRect()
            dst_center = dst_rect.center()

            # 計算從目標節點中心到端口的方向
            to_port_dx = dstPos.x() - dst_center.x()
            to_port_dy = dstPos.y() - dst_center.y()

            # 如果端口在節點內部（距中心很近），將箭頭移到邊界上
            distance_to_center = math.sqrt(to_port_dx**2 + to_port_dy**2)
            node_radius = min(dst_rect.width(), dst_rect.height()) / 2

            if distance_to_center < node_radius * 0.8:  # 端口在節點內部
                # 將箭頭 tip 移動到節點邊界
                direction = QPointF(dx, dy)
                length = math.sqrt(dx**2 + dy**2)
                if length > 0:
                    direction /= length
                    # 箭頭 tip 位於節點邊界上
                    tip = dst_center + direction * (node_radius - 2)
                else:
                    tip = dstPos
            else:
                tip = dstPos  # 使用端口位置
        else:
            tip = dstPos  # 備用：使用目標位置

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

    def updateArrowHead(self, srcPos, dstPos, adjustedDstPos=None):
        """保留的相容性方法 - 調用新的精確實作"""
        self._updateArrowHead(srcPos, dstPos)

    def hoverEnterEvent(self, event):
        """滑鼠懸停進入 - 支援 Shift 鍵發亮"""
        if not self.isTemporary:
            # 檢查 Shift 鍵是否被按下
            from PyQt5.QtWidgets import QApplication
            modifiers = QApplication.keyboardModifiers()
            shift_pressed = modifiers & Qt.ShiftModifier

            if shift_pressed:
                # Shift + 懸停：設定發亮狀態
                self._is_shift_highlighted = True
            else:
                # 普通懸停
                self._is_hovered = True

            # 觸發重繪
            self.update()
            if hasattr(self, 'arrowHead') and self.arrowHead:
                self.arrowHead.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """滑鼠懸停離開"""
        if not self.isTemporary:
            # 清除懸停狀態
            self._is_hovered = False
            self._is_shift_highlighted = False

            # 觸發重繪
            self.update()
            if hasattr(self, 'arrowHead') and self.arrowHead:
                self.arrowHead.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """滑鼠按下事件 - 處理邊線選取與多選"""
        if event.button() == Qt.LeftButton and not self.isTemporary:
            # 檢查 Shift 鍵是否按下 - 多選模式
            from PyQt5.QtWidgets import QApplication
            modifiers = QApplication.keyboardModifiers()
            shift_pressed = modifiers & Qt.ShiftModifier

            current_selected = getattr(self, '_is_selected', False)

            if shift_pressed:
                # Shift 多選模式：切換當前邊線狀態，保持其他選取
                self._is_selected = not current_selected

                # 觸發重繪（先更新視覺）
                self.update()
                if hasattr(self, 'arrowHead') and self.arrowHead:
                    self.arrowHead.update()

                # 確保其他已選中的邊線保持選中狀態和視覺效果
                scene = self.scene()
                selected_count = 0
                selected_edges = []
                if scene:
                    for item in scene.items():
                        if isinstance(item, EdgeItem) and getattr(item, '_is_selected', False):
                            selected_count += 1
                            selected_edges.append(f"{item.src.taskId}->{item.dst.taskId}")
                            # 確保每個選中的邊線都重新繪製
                            item.update()
                            if hasattr(item, 'arrowHead') and item.arrowHead:
                                item.arrowHead.update()

                print(f"[Shift多選] 邊線 {self.src.taskId} -> {self.dst.taskId} {'選取' if self._is_selected else '取消選取'}")
                print(f"    當前選取的邊線: {selected_edges} (總共: {selected_count})")
            else:
                # 單選模式：清除其他選取，選中當前邊線
                scene = self.scene()
                if scene:
                    for item in scene.items():
                        if isinstance(item, EdgeItem) and item != self:
                            if getattr(item, '_is_selected', False):
                                item._is_selected = False
                                item.update()
                                if hasattr(item, 'arrowHead') and item.arrowHead:
                                    item.arrowHead.update()

                # 單選模式：直接選中當前邊線（不切換）
                if not current_selected:
                    self._is_selected = True
                    print(f"[單選] 邊線 {self.src.taskId} -> {self.dst.taskId} 選取")
                else:
                    # 如果已選中，則取消選取
                    self._is_selected = False
                    print(f"[單選] 邊線 {self.src.taskId} -> {self.dst.taskId} 取消選取")

            # 清除懸停狀態（避免視覺衝突）
            self._is_hovered = False
            self._is_shift_highlighted = False

            # 如果不是 Shift 模式，需要重繪（Shift 模式已經重繪過了）
            if not shift_pressed:
                self.update()
                if hasattr(self, 'arrowHead') and self.arrowHead:
                    self.arrowHead.update()

            event.accept()
        else:
            super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """右鍵選單"""
        if self.isTemporary:
            return

        menu = QMenu()

        deleteAction = menu.addAction("刪除依賴")
        deleteAction.triggered.connect(self.deleteEdge)

        menu.exec_(event.screenPos())

    def deleteEdge(self):
        """刪除邊"""
        if not self.isTemporary and self.src and self.dst:
            editor = None
            for view in self.scene().views():
                parent = view.parent()
                while parent:
                    # 動態導入以避免循環導入
                    from .main_editor import DsmEditor
                    if isinstance(parent, DsmEditor):
                        editor = parent
                        break
                    parent = parent.parent()
                if editor:
                    break

            if editor:
                command = RemoveEdgeCommand(editor, self)
                editor.executeCommand(command)

    def itemChange(self, change, value):
        """處理邊線狀態變化 - 真正 yEd 風格：黑線 + 橘色發光"""
        if change == QGraphicsItem.ItemSelectedChange:
            self._is_selected = value
            # 更新重繪，讓 paint() 方法處理視覺效果
            self.update()

        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        """自訂繪製方法 - 實現 yEd 風格發光效果"""
        try:
            # 移除 Qt 預設選取框
            from PyQt5.QtWidgets import QStyle
            option.state &= ~QStyle.State_Selected

            # 判斷當前狀態
            is_selected = getattr(self, '_is_selected', False)
            is_shift_highlighted = getattr(self, '_is_shift_highlighted', False)
            is_hovered = getattr(self, '_is_hovered', False)

            # 繪製發光效果
            if is_shift_highlighted:
                # Shift + 懸停：最亮的發光效果
                glow_pen = QPen(QColor(255, 220, 50, 150), 10, Qt.SolidLine)  # 亮橘黃色
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
                # 選取狀態：橘色發光效果
                glow_pen = QPen(QColor(255, 165, 0, 120), 8, Qt.SolidLine)  # 半透明橘色
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
                # 普通懸停：淡淡的發光
                glow_pen = QPen(QColor(255, 165, 0, 80), 4, Qt.SolidLine)  # 很淡的橘色
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
            print(f"EdgeItem paint error: {e}")
            # 回退到預設繪製
            super().paint(painter, option, widget)

    def shape(self):
        """定義擴大的選取區域 - 包含箭頭和粗線條"""
        try:
            path = QPainterPath()

            if not self.path().isEmpty():
                # 創建擴大的線條選取區域
                stroker = QPainterPathStroker()
                stroker.setWidth(max(12, self.pen().width() * 2))  # 至少12像素寬的選取區域
                stroker.setCapStyle(Qt.RoundCap)
                stroker.setJoinStyle(Qt.RoundJoin)

                # 為主線條創建粗選取路徑
                thick_path = stroker.createStroke(self.path())
                path.addPath(thick_path)

                # 添加箭頭的選取區域
                if hasattr(self, 'arrowHead') and self.arrowHead and not self.arrowHead.path().isEmpty():
                    arrow_path = self.arrowHead.path()

                    # 為箭頭創建擴大的選取區域
                    arrow_stroker = QPainterPathStroker()
                    arrow_stroker.setWidth(10)  # 箭頭周圍10像素選取區域
                    arrow_stroker.setCapStyle(Qt.RoundCap)
                    arrow_stroker.setJoinStyle(Qt.RoundJoin)

                    expanded_arrow = arrow_stroker.createStroke(arrow_path)
                    path.addPath(expanded_arrow)

                    # 也包含箭頭本身的填充區域
                    path.addPath(arrow_path)

            return path if not path.isEmpty() else super().shape()

        except Exception as e:
            print(f"Edge shape calculation error: {e}")
            # 安全回退到預設行為
            return super().shape()

    def boundingRect(self):
        """返回包含擴大選取區域的邊界矩形"""
        try:
            # 使用 shape() 的邊界
            shape_rect = self.shape().boundingRect()

            if not shape_rect.isEmpty():
                # 再稍微擴大邊界以確保完全包含
                margin = 5
                return shape_rect.adjusted(-margin, -margin, margin, margin)
            else:
                # 回退到預設行為
                return super().boundingRect()

        except Exception as e:
            print(f"Edge boundingRect calculation error: {e}")
            return super().boundingRect()
