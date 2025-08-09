from __future__ import annotations

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPen, QPainter
from PyQt5.QtWidgets import QGraphicsView, QRubberBand, QGraphicsScene


class CanvasView(QGraphicsView):
    """提供縮放與平移功能的畫布視圖 - 效能優化版"""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)

        # 效能優化設定
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 使用 OpenGL 加速（如果可用）
        try:
            from PyQt5.QtWidgets import QOpenGLWidget
            self.setViewport(QOpenGLWidget())
        except ImportError:
            pass

        # 設定更新模式為最小區域更新
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)

        # 設定拖拽模式
        self.setDragMode(QGraphicsView.NoDrag)

        # 平移相關
        self._panning = False
        self._panStart = QPointF()

        # 網格設定
        self.showGrid = True
        self.gridSize = 20
        self.snapToGrid = True
        self.snapDistance = 8

        # 對齊輔助線
        self.alignmentLines = []
        self.showAlignmentLines = True

        # 橡皮筋框選
        self._rubberBand = None
        self._rubberBandStart = QPointF()
        self._selecting = False

        # 緩存背景
        self._backgroundCache = None
        self._cacheValid = False

    def setGridVisible(self, visible: bool) -> None:
        """設定網格可見性"""
        self.showGrid = visible
        self._cacheValid = False
        self.viewport().update()

    def setSnapToGrid(self, snap: bool) -> None:
        """設定是否對齊網格"""
        self.snapToGrid = snap

    def snapPointToGrid(self, point: QPointF) -> QPointF:
        """將點對齊到網格"""
        if not self.snapToGrid:
            return point
        x = round(point.x() / self.gridSize) * self.gridSize
        y = round(point.y() / self.gridSize) * self.gridSize
        return QPointF(x, y)

    def drawBackground(self, painter: QPainter, rect):
        """繪製背景與網格 - 使用緩存優化"""
        # 繪製白色背景
        painter.fillRect(rect, QColor(255, 255, 255))

        if not self.showGrid:
            return

        # 簡化網格繪製 - 使用黑色網格線
        painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.SolidLine))

        left = int(rect.left()) - (int(rect.left()) % self.gridSize)
        top = int(rect.top()) - (int(rect.top()) % self.gridSize)

        lines = []

        # 收集所有線條
        x = left
        while x < rect.right():
            lines.append(QPointF(x, rect.top()))
            lines.append(QPointF(x, rect.bottom()))
            x += self.gridSize

        y = top
        while y < rect.bottom():
            lines.append(QPointF(rect.left(), y))
            lines.append(QPointF(rect.right(), y))
            y += self.gridSize

        # 批量繪製
        if lines:
            painter.drawLines(lines)

    def wheelEvent(self, event):
        """滾輪縮放"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        """滑鼠按下事件 - 支援橡皮筋框選"""
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._panStart = QPointF(event.pos())
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

        elif event.button() == Qt.LeftButton:
            # 檢查是否點擊在空白區域
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())

            # 只有點擊在真正的空白區域才開始橡皮筋框選
            # ResizeHandle 不應該被視為空白區域
            if not item:
                # 清除選取（除非按住 Ctrl/Shift）
                if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                    self.scene().clearSelection()

                # 開始框選
                self._selecting = True
                self._rubberBandStart = scene_pos

                if not self._rubberBand:
                    self._rubberBand = QRubberBand(QRubberBand.Rectangle, self)

                self._rubberBand.setGeometry(event.pos().x(), event.pos().y(), 0, 0)
                self._rubberBand.show()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """滑鼠移動事件"""
        if self._panning:
            delta = event.pos() - self._panStart
            self._panStart = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()

        elif self._selecting and self._rubberBand:
            # 更新橡皮筋框選區域
            start_view = self.mapFromScene(self._rubberBandStart)
            current = event.pos()

            # 計算矩形
            x = min(start_view.x(), current.x())
            y = min(start_view.y(), current.y())
            w = abs(current.x() - start_view.x())
            h = abs(current.y() - start_view.y())

            self._rubberBand.setGeometry(x, y, w, h)
            event.accept()

        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()

        elif event.button() == Qt.LeftButton and self._selecting:
            # 完成框選
            if self._rubberBand:
                # 計算選取區域
                end_pos = self.mapToScene(event.pos())
                selection_rect = QRectF(self._rubberBandStart, end_pos).normalized()

                # 選取框內的所有節點
                from .nodes import TaskNode
                for item in self.scene().items(selection_rect, Qt.IntersectsItemShape):
                    if isinstance(item, TaskNode):
                        item.setSelected(True)

                self._rubberBand.hide()
                self._selecting = False
            event.accept()

        else:
            super().mouseReleaseEvent(event)