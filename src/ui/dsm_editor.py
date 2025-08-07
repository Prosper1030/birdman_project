"""
yEd 風格視覺化 DSM 編輯器 - 完整修正版
解決所有核心互動問題，達到商業級用戶體驗
"""

from __future__ import annotations

import math
import time
from typing import Dict, Set, Optional, List
from enum import Enum

import pandas as pd
import networkx as nx
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsPathItem,
    QGraphicsItem,
    QMenu,
    QAction,
    QMenuBar,
    QGroupBox,
    QRubberBand,
)


class EditorState(Enum):
    """編輯器狀態枚舉"""
    IDLE = "idle"
    CREATING_EDGE = "creating_edge"
    EDITING_TEXT = "editing_text"
    SELECTING = "selecting"
    RESIZING = "resizing"
    MOVING = "moving"


class LayoutAlgorithm(Enum):
    """佈局演算法枚舉"""
    HIERARCHICAL = "hierarchical"
    ORTHOGONAL = "orthogonal"
    FORCE_DIRECTED = "force_directed"


class Command:
    """命令模式基類，用於撤銷/重做功能"""
    def execute(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError


class AddNodeCommand(Command):
    """新增節點命令"""
    def __init__(self, editor: 'DsmEditor', node: 'TaskNode'):
        self.editor = editor
        self.node = node

    def execute(self) -> None:
        # 檢查項目是否已在場景中，避免重複添加
        if self.node.scene() != self.editor.scene:
            self.editor.scene.addItem(self.node)
        self.editor.nodes[self.node.taskId] = self.node

    def undo(self) -> None:
        self.editor.scene.removeItem(self.node)
        del self.editor.nodes[self.node.taskId]


class AddEdgeCommand(Command):
    """新增邊命令"""
    def __init__(self, editor: 'DsmEditor', src: 'TaskNode', dst: 'TaskNode'):
        self.editor = editor
        self.src = src
        self.dst = dst
        self.edge: Optional['EdgeItem'] = None

    def execute(self) -> None:
        if (self.src.taskId, self.dst.taskId) not in self.editor.edges:
            self.edge = EdgeItem(self.src, self.dst)
            # 檢查邊線是否已在場景中
            if self.edge.scene() != self.editor.scene:
                self.editor.scene.addItem(self.edge)
            # 檢查箭頭是否已在場景中
            if hasattr(self.edge, 'arrowHead') and self.edge.arrowHead.scene() != self.editor.scene:
                self.editor.scene.addItem(self.edge.arrowHead)
            self.src.edges.append(self.edge)
            self.dst.edges.append(self.edge)
            self.editor.edges.add((self.src.taskId, self.dst.taskId))

    def undo(self) -> None:
        if self.edge:
            self.editor.scene.removeItem(self.edge)
            if hasattr(self.edge, 'arrowHead') and self.edge.arrowHead.scene():
                self.editor.scene.removeItem(self.edge.arrowHead)
            self.src.edges.remove(self.edge)
            self.dst.edges.remove(self.edge)
            self.editor.edges.discard((self.src.taskId, self.dst.taskId))


class RemoveEdgeCommand(Command):
    """移除邊的命令"""
    def __init__(self, editor: DsmEditor, edge: EdgeItem):
        self.editor = editor
        self.edge = edge
        self.src = edge.src
        self.dst = edge.dst

    def execute(self) -> None:
        if self.edge and self.edge.scene():
            self.editor.scene.removeItem(self.edge)
            if hasattr(self.edge, 'arrowHead') and self.edge.arrowHead.scene():
                self.editor.scene.removeItem(self.edge.arrowHead)
            self.src.edges.remove(self.edge)
            self.dst.edges.remove(self.edge)
            self.editor.edges.discard((self.src.taskId, self.dst.taskId))

    def undo(self) -> None:
        if self.edge:
            # 檢查邊線是否已在場景中
            if self.edge.scene() != self.editor.scene:
                self.editor.scene.addItem(self.edge)
            # 檢查箭頭是否已在場景中  
            if hasattr(self.edge, 'arrowHead') and self.edge.arrowHead.scene() != self.editor.scene:
                self.editor.scene.addItem(self.edge.arrowHead)
            self.src.edges.append(self.edge)
            self.dst.edges.append(self.edge)
            self.editor.edges.add((self.src.taskId, self.dst.taskId))


class MoveNodeCommand(Command):
    """移動節點命令"""
    def __init__(self, node: 'TaskNode', old_pos: QPointF, new_pos: QPointF):
        self.node = node
        self.old_pos = old_pos
        self.new_pos = new_pos

    def execute(self) -> None:
        self.node.setPos(self.new_pos)
        # 更新所有相關連線
        for edge in self.node.edges:
            edge.updatePath()

    def undo(self) -> None:
        self.node.setPos(self.old_pos)
        # 更新所有相關連線
        for edge in self.node.edges:
            edge.updatePath()


class ResizeNodeCommand(Command):
    """調整節點大小命令"""
    def __init__(self, node: 'TaskNode', old_rect: QRectF, new_rect: QRectF):
        self.node = node
        self.old_rect = old_rect
        self.new_rect = new_rect

    def execute(self) -> None:
        self.node.setRect(self.new_rect)
        self.node._updateHandlesPosition()
        # 更新所有相關連線
        for edge in self.node.edges:
            edge.updatePath()

    def undo(self) -> None:
        self.node.setRect(self.old_rect)
        self.node._updateHandlesPosition()
        # 更新所有相關連線
        for edge in self.node.edges:
            edge.updatePath()


class ResizeHandle(QGraphicsRectItem):
    """yEd 風格的調整大小把手 - 正確實現版"""

    HANDLE_SIZE = 6  # 把手視覺大小 - 符合 yEd 風格
    HANDLE_DISTANCE = 5  # 把手距離節點邊緣的固定距離
    HOVER_DETECTION_RANGE = 8  # 懸停檢測範圍（比把手稍大）
    MIN_NODE_SIZE = 50  # 最小節點尺寸

    def __init__(self, parent_node: 'TaskNode', handle_index: int):
        # 使用懸停檢測範圍初始化（用於事件檢測）
        half_detection = self.HOVER_DETECTION_RANGE / 2
        super().__init__(-half_detection, -half_detection,
                         self.HOVER_DETECTION_RANGE, self.HOVER_DETECTION_RANGE, parent_node)

        self.parent_node = parent_node
        self.handle_index = handle_index
        self.resizing = False
        self.resize_start_pos = QPointF()
        self.initial_rect = QRectF()
        self.initial_pos = QPointF()
        self._is_hovered = False

        # 設定視覺樣式 - yEd 風格黑色小方塊
        self.setBrush(QBrush(Qt.black))
        self.setPen(QPen(Qt.black, 1))

        # 設定游標樣式
        cursor_map = {
            0: Qt.SizeFDiagCursor,  # 左上
            1: Qt.SizeVerCursor,    # 上中
            2: Qt.SizeBDiagCursor,  # 右上
            3: Qt.SizeHorCursor,    # 右中
            4: Qt.SizeFDiagCursor,  # 右下
            5: Qt.SizeVerCursor,    # 下中
            6: Qt.SizeBDiagCursor,  # 左下
            7: Qt.SizeHorCursor,    # 左中
        }
        self.setCursor(cursor_map.get(handle_index, Qt.SizeAllCursor))

        # 設定 Z 值確保在最上層（比父節點更高）
        self.setZValue(2000)  # 提高 Z 值

        # 啟用事件處理
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)
        self.setFlag(QGraphicsItem.ItemStacksBehindParent, False)  # 確保不在父節點後面
        self.setAcceptHoverEvents(True)

        # 確保把手能接收滑鼠事件
        self.setEnabled(True)

    def updatePosition(self):
        """更新把手位置 - yEd 風格：把手位於節點外圍固定距離"""
        rect = self.parent_node.rect()
        distance = self.HANDLE_DISTANCE
        half_detection = self.HOVER_DETECTION_RANGE / 2

        # 計算把手中心位置（距離節點邊緣固定距離）
        positions = [
            # 左上角：向左上偏移
            (rect.left() - distance - half_detection, rect.top() - distance - half_detection),
            # 上中：向上偏移
            (rect.center().x() - half_detection, rect.top() - distance - half_detection),
            # 右上角：向右上偏移
            (rect.right() + distance - half_detection, rect.top() - distance - half_detection),
            # 右中：向右偏移
            (rect.right() + distance - half_detection, rect.center().y() - half_detection),
            # 右下角：向右下偏移
            (rect.right() + distance - half_detection, rect.bottom() + distance - half_detection),
            # 下中：向下偏移
            (rect.center().x() - half_detection, rect.bottom() + distance - half_detection),
            # 左下角：向左下偏移
            (rect.left() - distance - half_detection, rect.bottom() + distance - half_detection),
            # 左中：向左偏移
            (rect.left() - distance - half_detection, rect.center().y() - half_detection),
        ]

        if self.handle_index < len(positions):
            x, y = positions[self.handle_index]
            self.setPos(x, y)

    def paint(self, painter, option, widget=None):
        """自訂繪製 - 繪製 yEd 風格的黑色小方塊把手"""
        # 計算實際把手在檢測範圍中央的位置
        detection_center = self.HOVER_DETECTION_RANGE / 2
        handle_half = self.HANDLE_SIZE / 2

        # 繪製黑色小方塊把手
        handle_rect = QRectF(
            detection_center - handle_half,
            detection_center - handle_half,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE
        )

        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(handle_rect)

    def hoverEnterEvent(self, event):
        """滑鼠懸停進入事件"""
        self._is_hovered = True
        print(f"🖱️ 把手 {self.handle_index} 懸停進入")  # 調試輸出
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """滑鼠懸停離開事件"""
        # 只有在不調整大小時才設定為非懸停狀態
        if not self.resizing:
            self._is_hovered = False
            print(f"🖱️ 把手 {self.handle_index} 懸停離開")  # 調試輸出
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """滑鼠按下事件 - 只有在懸停狀態下才響應"""
        print(f"🖱️ 把手 {self.handle_index} 按下事件, 懸停狀態: {self._is_hovered}, 按鈕: {event.button()}")  # 調試輸出

        if event.button() == Qt.LeftButton:
            if self._is_hovered:
                print(f"🔧 開始調整大小 - 把手 {self.handle_index}")  # 調試輸出
                self.resizing = True
                self.resize_start_pos = event.scenePos()
                self.initial_rect = self.parent_node.rect()
                self.initial_pos = self.parent_node.pos()

                # 通知編輯器進入調整大小狀態
                if hasattr(self.parent_node.editor, 'state'):
                    self.parent_node.editor.state = EditorState.RESIZING

                event.accept()  # 確保事件被接受
                return
            else:
                print(f"❌ 把手 {self.handle_index} 未在懸停狀態，忽略點擊")

        # 如果不是我們處理的事件，傳遞給父類
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """滑鼠移動事件"""
        if self.resizing:
            current_pos = event.scenePos()
            delta = current_pos - self.resize_start_pos

            # 減少調試輸出頻率以提升性能
            if not hasattr(self, '_debug_counter'):
                self._debug_counter = 0
            self._debug_counter += 1
            if self._debug_counter % 5 == 0:  # 每5次移動才輸出一次
                print(f"📏 調整大小中 - 把手 {self.handle_index}, delta: ({delta.x():.1f}, {delta.y():.1f})")

            # 在場景坐標中處理
            self._resizeParentNode(delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        if event.button() == Qt.LeftButton and self.resizing:
            # 記錄調整大小的命令
            current_rect = self.parent_node.rect()
            if (current_rect != self.initial_rect):
                resize_command = ResizeNodeCommand(self.parent_node, self.initial_rect, current_rect)
                self.parent_node.editor.executeCommand(resize_command)

            self.resizing = False
            self._is_hovered = False  # 重設懸停狀態

            # 恢復編輯器狀態
            if hasattr(self.parent_node.editor, 'state'):
                self.parent_node.editor.state = EditorState.IDLE

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _resizeParentNode(self, delta):
        """調整父節點大小 - yEd 風格：保持中心點固定，平滑調整"""
        rect = self.initial_rect
        node_pos = self.initial_pos

        # 計算原始中心點（在場景座標中）
        original_center = QPointF(
            node_pos.x() + rect.center().x(),
            node_pos.y() + rect.center().y()
        )

        # 計算新的寬度和高度變化
        width_delta = 0
        height_delta = 0

        # 根據把手位置計算尺寸變化
        if self.handle_index == 0:  # 左上
            width_delta = -delta.x() * 2  # 左邊拉動，影響總寬度
            height_delta = -delta.y() * 2  # 上邊拉動，影響總高度
        elif self.handle_index == 1:  # 上中
            height_delta = -delta.y() * 2  # 上邊拉動，影響總高度
        elif self.handle_index == 2:  # 右上
            width_delta = delta.x() * 2   # 右邊拉動，影響總寬度
            height_delta = -delta.y() * 2  # 上邊拉動，影響總高度
        elif self.handle_index == 3:  # 右中
            width_delta = delta.x() * 2   # 右邊拉動，影響總寬度
        elif self.handle_index == 4:  # 右下
            width_delta = delta.x() * 2   # 右邊拉動，影響總寬度
            height_delta = delta.y() * 2  # 下邊拉動，影響總高度
        elif self.handle_index == 5:  # 下中
            height_delta = delta.y() * 2  # 下邊拉動，影響總高度
        elif self.handle_index == 6:  # 左下
            width_delta = -delta.x() * 2  # 左邊拉動，影響總寬度
            height_delta = delta.y() * 2  # 下邊拉動，影響總高度
        elif self.handle_index == 7:  # 左中
            width_delta = -delta.x() * 2  # 左邊拉動，影響總寬度

        # 計算新尺寸
        new_width = max(rect.width() + width_delta, self.MIN_NODE_SIZE)
        new_height = max(rect.height() + height_delta, self.MIN_NODE_SIZE)

        # 創建以(0,0)為左上角的新矩形
        new_rect = QRectF(0, 0, new_width, new_height)

        # 計算新的位置，確保中心點保持不變
        new_pos = QPointF(
            original_center.x() - new_rect.center().x(),
            original_center.y() - new_rect.center().y()
        )

        # 批量更新：僅在真正需要時呼叫 prepareGeometryChange
        current_rect = self.parent_node.rect()
        current_pos = self.parent_node.pos()

        # 檢查是否有實際變化（避免不必要的重繪）
        if (abs(current_rect.width() - new_width) > 1 or
                abs(current_rect.height() - new_height) > 1 or
                abs(current_pos.x() - new_pos.x()) > 1 or
                abs(current_pos.y() - new_pos.y()) > 1):

            # 使用 setFlag 暫時停用 ItemSendsGeometryChanges 來避免多次重繪
            old_flags = self.parent_node.flags()
            self.parent_node.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)

            # 更新幾何形狀
            self.parent_node.prepareGeometryChange()
            self.parent_node.setRect(new_rect)
            self.parent_node.setPos(new_pos)

            # 恢復旗標
            self.parent_node.setFlags(old_flags)

            # 批量更新把手位置（不觸發個別重繪）
            self.parent_node._updateHandlesPositionQuiet()

        # 即時更新與節點相連的邊，確保縮放過程中連線緊貼節點
        for edge in self.parent_node.edges:
            edge.updatePath()


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
                for item in self.scene().items(selection_rect, Qt.IntersectsItemShape):
                    if isinstance(item, TaskNode):
                        item.setSelected(True)

                self._rubberBand.hide()
                self._selecting = False
            event.accept()

        else:
            super().mouseReleaseEvent(event)


class TaskNode(QGraphicsRectItem):
    """代表任務節點的圖形物件 - 完整修正版"""

    DEFAULT_WIDTH = 120
    DEFAULT_HEIGHT = 60

    def __init__(self, taskId: str, text: str, color: QColor, editor: 'DsmEditor') -> None:
        super().__init__(-self.DEFAULT_WIDTH / 2, -self.DEFAULT_HEIGHT / 2,
                         self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self.taskId = taskId
        self.text = text
        self.editor = editor
        self.edges: List[EdgeItem] = []

        # 狀態管理
        self.isEditing = False
        self.isHovered = False
        self.isDragging = False
        self.isConnecting = False
        self.moveMode = False  # yEd 風格節點跟隨滑鼠模式
        self._is_highlighted = False
        self._canMove = False  # 只有選中的節點才能移動

        # 連線檢測參數
        self.dragStartPos = QPointF()
        self.dragStartTime = 0
        self.connectionThreshold = 8  # 降低閾值，更容易觸發連線

        # 選取把手
        self._selection_handles = []
        self._handles_visible = False

        # yEd 風格顏色 - 高彩度亮黃色與選取時的溫和米黃色
        self.yedYellow = QColor(255, 255, 0)  # 高彩度亮黃色
        self.selectedYellow = QColor(255, 245, 160)  # 選取時的溫和米黃色（比原來亮一些）

        self.normalBrush = QBrush(self.yedYellow)  # 未選取：高彩度亮黃色
        self.selectedBrush = QBrush(self.selectedYellow)  # 選取：溫和米黃色
        self.hoverBrush = QBrush(self.yedYellow.lighter(110))
        self.highlightBrush = QBrush(QColor(46, 204, 113))

        self.normalPen = QPen(Qt.black, 1)
        self.selectedPen = QPen(Qt.black, 2)
        self.hoverPen = QPen(Qt.black, 1)
        self.highlightPen = QPen(QColor(46, 204, 113), 2, Qt.DashLine)

        # 設定初始樣式
        self.setBrush(self.normalBrush)
        self.setPen(self.normalPen)

        # 設定 Z 值
        self.setZValue(10)

        # 設定互動旗標 - 初始不可移動
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 初始化選取把手
        self._createSelectionHandles()

        # 自訂屬性
        self.customData = {
            "assignee": "",
            "status": "",
            "duration": 0,
            "priority": "Medium"
        }

    def _createSelectionHandles(self) -> None:
        """建立 8 個選取把手"""
        for i in range(8):
            handle = ResizeHandle(self, i)
            handle.setVisible(False)
            self._selection_handles.append(handle)

    def _updateHandlesPosition(self) -> None:
        """更新把手位置"""
        for handle in self._selection_handles:
            handle.updatePosition()

    def _updateHandlesPositionQuiet(self) -> None:
        """靜默更新把手位置（不觸發重繪事件）"""
        for handle in self._selection_handles:
            # 暫時停用幾何變化通知來避免頻繁重繪
            old_flags = handle.flags()
            handle.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
            handle.updatePosition()
            handle.setFlags(old_flags)

    def _updateHandlesVisibility(self, visible: bool) -> None:
        """更新選取把手的可見性"""
        self._handles_visible = visible
        for handle in self._selection_handles:
            handle.setVisible(visible)

        # 根據選取狀態設定是否可移動
        self._canMove = visible
        self.setFlag(QGraphicsItem.ItemIsMovable, visible)

    def itemChange(self, change, value):
        """處理項目變化"""
        if change == QGraphicsItem.ItemSelectedChange:
            # 選取狀態變化 - 同步處理所有視覺效果
            self._updateSelectionState(value)
            # 立即強制重繪確保效果同步
            self.update()
            if self.scene():
                self.scene().update(self.sceneBoundingRect())

        elif change == QGraphicsItem.ItemPositionChange:
            # 位置變化 - 對齊網格
            if hasattr(self.editor, 'view') and self.editor.view.snapToGrid:
                value = self.editor.view.snapPointToGrid(value)

        elif change == QGraphicsItem.ItemPositionHasChanged:
            # 位置已變化 - 更新連線和把手
            self._updateHandlesPosition()
            for edge in self.edges:
                edge.updatePath()

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """滑鼠按下事件 - yEd 標準邏輯"""
        if event.button() == Qt.LeftButton:
            # 記錄按下位置和時間，準備判斷後續行為
            self.dragStartPos = event.scenePos()
            self.initialPos = self.pos()  # 記錄初始位置用於撤銷
            self.dragStartTime = time.time()
            self.pressedInNode = True  # 標記按下時在節點內
            self.leftNodeBounds = False  # 標記是否已離開節點邊界
            self.mouseReleased = False  # 追蹤是否已經放開滑鼠

            # 檢查是否點擊在調整把手上
            clicked_item = self.scene().itemAt(event.scenePos(), self.scene().views()[0].transform())
            if isinstance(clicked_item, ResizeHandle):
                # 點擊把手，讓把手處理
                super().mousePressEvent(event)
                return

            # 重置狀態
            self.isDragging = False
            self.isConnecting = False

            # yEd 邏輯：不管選取狀態如何，都準備等待後續行為
            # 不立即改變選取狀態，等到 mouseReleaseEvent 再決定
            print(f"節點 '{self.taskId}' 按下，等待判斷行為（選取或連線）")

            # 阻止預設的選取行為 - 不調用 super()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """滑鼠移動事件 - yEd 標準邏輯"""
        if event.buttons() & Qt.LeftButton and hasattr(self, 'pressedInNode'):
            current_pos = event.scenePos()

            # 檢查是否正在調整把手
            if any(handle.resizing for handle in self._selection_handles if hasattr(handle, 'resizing')):
                super().mouseMoveEvent(event)
                return  # 把手調整中，讓把手處理

            # yEd 關鍵邏輯：選取狀態下優先處理拖動，絕不觸發連線
            if self.isSelected():
                # 已選取的節點：只能拖動移動，絕對不能開始連線
                distance = (current_pos - self.dragStartPos).manhattanLength()
                if distance > 8:  # 拖動閾值
                    if not self.isDragging:
                        self.isDragging = True
                        print(f"節點 '{self.taskId}' 開始拖動")
                    
                    # 允許標準拖動行為
                    super().mouseMoveEvent(event)
                    return
                else:
                    # 在閾值內，不移動但也不觸發其他行為
                    event.accept()
                    return

            # 只有未選取的節點才處理連線邏輯
            node_rect = self.sceneBoundingRect()
            shrink_amount = 5  # 縮小5像素
            detection_rect = node_rect.adjusted(shrink_amount, shrink_amount, -shrink_amount, -shrink_amount)

            if not self.leftNodeBounds and not detection_rect.contains(current_pos):
                # 第一次離開節點有效區域，且節點未被選取
                self.leftNodeBounds = True
                
                # 只有未選取的節點才能觸發連線模式
                if not self.isConnecting:
                    self.startConnectionMode()
                    print(f"開始連線模式：從節點 '{self.taskId}' 拖拽")
                
                event.accept()
                return

            # 如果在連線模式，更新預覽
            if self.isConnecting:
                if hasattr(self.editor.scene, 'updateTempConnection'):
                    self.editor.scene.updateTempConnection(current_pos)
                event.accept()
                return

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件 - yEd 標準邏輯：關鍵判斷點"""
        if event.button() == Qt.LeftButton and hasattr(self, 'pressedInNode'):
            current_pos = event.scenePos()
            self.mouseReleased = True

            if self.isConnecting:
                # 在連線模式中放開 - 完成連線或建立固定點
                item = self.scene().itemAt(current_pos, self.scene().views()[0].transform())
                if isinstance(item, TaskNode) and item != self:
                    # 完成連線
                    if hasattr(self.editor.scene, 'finishConnection'):
                        self.editor.scene.finishConnection(item)
                else:
                    # 在空白處放開 - 轉為兩階段連線模式
                    if hasattr(self.editor.scene, 'enterSecondPhaseConnection'):
                        self.editor.scene.enterSecondPhaseConnection(current_pos)
                    else:
                        # 如果沒有兩階段模式，就取消連線
                        if hasattr(self.editor.scene, 'cancelConnectionMode'):
                            self.editor.scene.cancelConnectionMode()
                        self.stopConnectionMode()

            elif not self.leftNodeBounds and not self.isDragging:
                # yEd 關鍵邏輯：在節點上按下並在節點上放開，且沒有拖動 = 選取操作
                node_rect = self.sceneBoundingRect()
                if node_rect.contains(current_pos):
                    # 清除其他選取，選中當前節點
                    self.scene().clearSelection()
                    self.setSelected(True)
                    self.updateVisualState()  # 顯示把手
                    print(f"節點 '{self.taskId}' 被選取")
                    event.accept()

            # 檢查是否有移動並記錄撤銷命令
            if hasattr(self, 'initialPos') and self.isDragging:
                final_pos = self.pos()
                if (final_pos - self.initialPos).manhattanLength() > 2:  # 只有移動距離超過2像素才記錄
                    move_command = MoveNodeCommand(self, self.initialPos, final_pos)
                    self.editor.executeCommand(move_command)
                    print(f"節點 '{self.taskId}' 拖動完成")

            # 重置狀態
            self.isDragging = False
            if not hasattr(self.editor.scene, 'enterSecondPhaseConnection') or not self.isConnecting:
                self.isConnecting = False
            delattr(self, 'pressedInNode')
            if hasattr(self, 'leftNodeBounds'):
                delattr(self, 'leftNodeBounds')
            if hasattr(self, 'mouseReleased'):
                delattr(self, 'mouseReleased')

        super().mouseReleaseEvent(event)

    def startConnectionMode(self) -> None:
        """開始連線模式 - 增強視覺回饋"""
        # yEd 關鍵規則：選取狀態下絕對不能開始連線模式
        if self.isSelected():
            print(f"節點 '{self.taskId}' 處於選取狀態，無法開始連線模式")
            return
            
        self.isConnecting = True
        self.setCursor(Qt.CrossCursor)

        # 設定節點為不可移動（連線期間）
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

        # 增強視覺回饋 - 邊框高亮
        self.setPen(QPen(QColor(255, 100, 100), 3, Qt.SolidLine))  # 紅色高亮邊框

        # 隱藏調整把手，避免干擾連線操作
        for handle in self._selection_handles:
            handle.setVisible(False)

        # 添加連線提示效果（可選）
        self.setOpacity(0.8)  # 半透明效果表示連線模式

        # 通知場景開始連線
        if hasattr(self.editor, 'scene'):
            self.editor.scene.startConnectionMode(self)

        # 在狀態欄或控制台顯示提示
        print(f"連線模式：從節點 '{self.text}' 拖拽到目標節點")

    def stopConnectionMode(self) -> None:
        """結束連線模式 - 恢復正常狀態"""
        self.isConnecting = False
        self.setCursor(Qt.ArrowCursor)

        # 恢復節點可移動
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

        # 恢復正常視覺狀態
        self.setOpacity(1.0)  # 恢復不透明

        # 如果仍然選中，顯示調整把手
        if self.isSelected():
            for handle in self._selection_handles:
                handle.setVisible(True)
            # 恢復選中狀態的邊框
            self.setPen(self.selectedPen)
        else:
            # 恢復正常邊框
            self.setPen(self.normalPen)

        print("連線模式已結束")

    def hoverEnterEvent(self, event):
        """滑鼠懸停進入 - yEd 標準行為"""
        self.isHovered = True
        self.updateVisualState()
        # yEd 邏輯：只有選取狀態下才顯示移動游標，否則保持箭頭
        if self.isSelected():
            self.setCursor(Qt.SizeAllCursor)  # 選取狀態：顯示移動游標
        # 未選取狀態：不改變游標，保持預設箭頭
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """滑鼠懸停離開 - yEd 標準行為"""
        self.isHovered = False
        self.updateVisualState()
        # 離開時恢復預設游標
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def set_highlight(self, highlighted: bool) -> None:
        """設定高亮狀態"""
        self._is_highlighted = highlighted
        self.updateVisualState()

    def _updateSelectionState(self, is_selected: bool) -> None:
        """同步更新選取狀態的所有視覺效果 - yEd 風格"""
        if is_selected:
            # 被選中：立即顯示把手並更新顏色
            self._updateHandlesVisibility(True)
            self._updateHandlesPosition()
            # 立即切換到選取顏色
            self.setBrush(self.selectedBrush)
            self.setPen(self.selectedPen)
            # 更新鼠標樣式為移動模式
            if self.isHovered:
                self.setCursor(Qt.SizeAllCursor)
            print(f"節點 '{self.taskId}' 已選中，可拖動移動")
        else:
            # 取消選中：立即隱藏把手並恢復原色
            self._updateHandlesVisibility(False)
            # 立即切換到正常顏色
            if self.isHovered:
                self.setBrush(self.hoverBrush)
                self.setPen(self.hoverPen)
                # 恢復一般鼠標
                self.setCursor(Qt.ArrowCursor)
            else:
                self.setBrush(self.normalBrush)
                self.setPen(self.normalPen)
            print(f"節點 '{self.taskId}' 取消選中")

    def updateVisualState(self) -> None:
        """更新視覺狀態 - 立即反應選取狀態變化"""
        if self._is_highlighted:
            self.setBrush(self.highlightBrush)
            self.setPen(self.highlightPen)
        elif self.isSelected():
            self.setBrush(self.selectedBrush)
            self.setPen(self.selectedPen)
        elif self.isHovered:
            self.setBrush(self.hoverBrush)
            self.setPen(self.hoverPen)
        else:
            self.setBrush(self.normalBrush)
            self.setPen(self.normalPen)

        # 立即強制重繪以確保快速反應
        self.update()
        # 強制場景也立即更新
        if self.scene():
            self.scene().update(self.sceneBoundingRect())

    def paint(self, painter, option, widget=None):
        """繪製節點"""
        # 避免預設的選取框
        from PyQt5.QtWidgets import QStyleOptionGraphicsItem, QStyle
        opt = QStyleOptionGraphicsItem(option)
        if opt.state & QStyle.State_Selected:
            opt.state &= ~QStyle.State_Selected

        # 繪製節點
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(self.rect())

        # 繪製文字
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(Qt.black))
        painter.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, self.text)

    def contextMenuEvent(self, event):
        """右鍵選單"""
        menu = QMenu()

        editAction = menu.addAction("編輯標籤")
        editAction.triggered.connect(self.startTextEdit)

        menu.addSeparator()

        deleteAction = menu.addAction("刪除節點")
        deleteAction.triggered.connect(self.deleteNode)

        menu.exec_(event.screenPos())

    def startTextEdit(self):
        """開始編輯文字"""
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(None, "編輯標籤", "輸入任務名稱:", text=self.text)
        if ok:
            self.text = text
            self.update()

    def deleteNode(self):
        """刪除節點"""
        edges_to_remove = self.edges.copy()
        for edge in edges_to_remove:
            self.editor.removeEdge(edge)

        self.scene().removeItem(self)
        del self.editor.nodes[self.taskId]


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

    def updatePath(self) -> None:
        """更新路徑 - 精確連線版本（從 opus 改進）"""
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
    
    def _buildPath(self, srcPoint: QPointF, dstPoint: QPointF) -> None:
        """建立連線路徑並更新箭頭（opus 改進）"""
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
    
    def getConnectionPoint(self, rect, center, dx, dy):
        """保留的相容性方法 - 現在調用更精確的方法"""
        targetPoint = QPointF(center.x() + dx * 1000, center.y() + dy * 1000)
        return self._getAlternativeConnectionPoint(rect, center, targetPoint, True)

    def _updateArrowHead(self, srcPos: QPointF, dstPos: QPointF) -> None:
        """更新箭頭形狀，確保精確指向目標（opus 改進）"""
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
    
    def updateArrowHead(self, srcPos, dstPos, adjustedDstPos=None):
        """保留的相容性方法 - 調用新的精確實作"""
        self._updateArrowHead(srcPos, dstPos)

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
                    if isinstance(parent, DsmEditor):
                        editor = parent
                        break
                    parent = parent.parent()
                if editor:
                    break

            if editor:
                command = RemoveEdgeCommand(editor, self)
                editor.executeCommand(command)


class DsmScene(QGraphicsScene):
    """支援連線操作的場景 - 優化版"""

    def __init__(self, editor: 'DsmEditor') -> None:
        super().__init__()
        self.editor = editor

        # 狀態管理
        self.connectionMode = False
        self.sourceNode = None
        self.tempEdge = None
        self.last_hovered_target = None

        # 多固定點連線模式
        self.fixedPoints = []  # 存儲多個固定點的列表

    def startConnectionMode(self, sourceNode: TaskNode) -> None:
        """開始連線模式"""
        self.connectionMode = True
        self.sourceNode = sourceNode

        # 建立臨時邊
        self.tempEdge = EdgeItem(sourceNode, sourceNode)
        self.tempEdge.setTemporary(True)
        
        # 檢查臨時邊線是否已在場景中，避免重複添加
        if self.tempEdge.scene() != self:
            self.addItem(self.tempEdge)

        # 設定游標
        for view in self.views():
            view.setCursor(Qt.CrossCursor)

        # 視覺回饋
        sourceNode.updateVisualState()

    def updateTempConnection(self, mousePos: QPointF) -> None:
        """更新臨時連線 - 支援多個固定點折線"""
        if not self.tempEdge or not self.sourceNode:
            return

        # 建立完整路徑：源節點 → 所有固定點 → 滑鼠位置
        path = QPainterPath()
        
        # 起始點：源節點邊緣
        srcRect = self.sourceNode.sceneBoundingRect()
        srcCenter = srcRect.center()
        
        # 計算到第一個目標的方向（固定點或滑鼠位置）
        first_target = self.fixedPoints[0] if self.fixedPoints else mousePos
        dx = first_target.x() - srcCenter.x()
        dy = first_target.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length > 1:
            dx /= length
            dy /= length
            srcPos = self.tempEdge.getConnectionPoint(srcRect, srcCenter, dx, dy)
        else:
            srcPos = srcCenter
        
        # 從源節點開始
        path.moveTo(srcPos)
        
        # 連接所有固定點
        for fixed_point in self.fixedPoints:
            path.lineTo(fixed_point)
        
        # 最後連接到滑鼠位置
        path.lineTo(mousePos)
        
        self.tempEdge.setPath(path)
        
        # 更新箭頭（從最後一個點到滑鼠位置）
        last_point = self.fixedPoints[-1] if self.fixedPoints else srcPos
        if hasattr(self.tempEdge, 'updateArrowHead'):
            self.tempEdge.updateArrowHead(last_point, mousePos)

        # 高亮目標節點並調整箭頭位置
        targetItem = self.itemAt(mousePos, self.views()[0].transform())

        if self.last_hovered_target and self.last_hovered_target != targetItem:
            self.last_hovered_target.set_highlight(False)
            self.last_hovered_target = None

        if isinstance(targetItem, TaskNode) and targetItem != self.sourceNode:
            targetItem.set_highlight(True)
            self.last_hovered_target = targetItem

            # 當鼠標在目標節點上時，調整最後一段線到節點邊緣
            targetRect = targetItem.sceneBoundingRect()
            targetCenter = targetRect.center()
            
            # 計算從最後一個點到目標節點的方向
            last_point = self.fixedPoints[-1] if self.fixedPoints else srcPos
            dx = targetCenter.x() - last_point.x()
            dy = targetCenter.y() - last_point.y()
            length = math.sqrt(dx * dx + dy * dy)
            
            if length > 1:
                dx /= length
                dy /= length
                targetPos = self.tempEdge.getConnectionPoint(targetRect, targetCenter, -dx, -dy)
                
                # 重新建立完整路徑
                path = QPainterPath()
                path.moveTo(srcPos)
                for fixed_point in self.fixedPoints:
                    path.lineTo(fixed_point)
                path.lineTo(targetPos)
                self.tempEdge.setPath(path)
                
                if hasattr(self.tempEdge, 'updateArrowHead'):
                    self.tempEdge.updateArrowHead(last_point, targetPos)

    def finishConnection(self, targetNode: TaskNode) -> None:
        """完成連線"""
        if not self.connectionMode or not self.sourceNode or targetNode == self.sourceNode:
            self.cancelConnectionMode()
            return

        # 檢查是否已存在連線
        if (self.sourceNode.taskId, targetNode.taskId) not in self.editor.edges:
            self.editor.addDependency(self.sourceNode, targetNode)

        self.cancelConnectionMode()

    def cancelConnectionMode(self) -> None:
        """取消連線模式"""
        # 清理高亮
        if self.last_hovered_target:
            self.last_hovered_target.set_highlight(False)
            self.last_hovered_target = None

        # 移除臨時邊
        if self.tempEdge:
            self.removeItem(self.tempEdge)
            self.tempEdge = None

        # 重設狀態
        self.connectionMode = False
        self.fixedPoints = []  # 清空固定點列表

        # 恢復源節點狀態
        if self.sourceNode:
            self.sourceNode.stopConnectionMode()
            self.sourceNode = None

        # 恢復游標
        for view in self.views():
            view.setCursor(Qt.ArrowCursor)

    def enterSecondPhaseConnection(self, fixedPoint):
        """進入兩階段連線模式 - yEd 標準行為"""
        if not self.connectionMode or not self.tempEdge:
            return

        # 記錄固定點
        self.fixedPoint = fixedPoint
        self.secondPhase = True

        # 更新臨時邊，從源節點到固定點
        srcRect = self.sourceNode.sceneBoundingRect()
        srcCenter = srcRect.center()

        dx = fixedPoint.x() - srcCenter.x()
        dy = fixedPoint.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)

        if length > 1:
            dx /= length
            dy /= length
            srcPos = self.tempEdge.getConnectionPoint(srcRect, srcCenter, dx, dy)

            path = QPainterPath()
            path.moveTo(srcPos)
            path.lineTo(fixedPoint)
            self.tempEdge.setPath(path)

            if hasattr(self.tempEdge, 'updateArrowHead'):
                self.tempEdge.updateArrowHead(srcPos, fixedPoint)

        print(f"進入兩階段連線模式，固定點：({fixedPoint.x():.1f}, {fixedPoint.y():.1f})")

    def addFixedPoint(self, point: QPointF) -> None:
        """添加固定點到連線路徑"""
        if not self.connectionMode:
            return
            
        # 添加固定點到列表
        self.fixedPoints.append(point)
        
        # 更新臨時連線以顯示新的路徑
        if self.tempEdge:
            self.updateTempConnection(point)
        
        print(f"添加固定點：({point.x():.1f}, {point.y():.1f})，總計 {len(self.fixedPoints)} 個固定點")

    def endConnectionMode(self) -> None:
        """結束連線模式並清理狀態"""
        if self.connectionMode:
            self.cancelConnectionMode()
            print("連線模式已結束")

    def mouseMoveEvent(self, event):
        """場景滑鼠移動事件 - 標準拖放行為"""
        if self.connectionMode and self.tempEdge:
            self.updateTempConnection(event.scenePos())
            event.accept()
        else:
            # 標準行為：讓節點自己處理拖動，場景不主動移動節點
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """場景滑鼠釋放事件 - yEd 風格行為"""
        if self.connectionMode:
            target = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(target, TaskNode) and target != self.sourceNode:
                # 連線到節點
                self.finishConnection(target)
            else:
                # 在畫布上放開 - 建立固定點
                self.addFixedPoint(event.scenePos())
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class DsmEditor(QDialog):
    """視覺化 DSM 編輯器 - 主視窗"""

    def __init__(self, wbsDf: pd.DataFrame, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("依賴關係編輯器")
        self.resize(1200, 800)

        # 設定視窗標誌
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowTitleHint |
            Qt.WindowSystemMenuHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        # 初始化狀態
        self.state = EditorState.IDLE
        self.commandHistory: List[Command] = []
        self.commandIndex = -1

        self.nodes: Dict[str, TaskNode] = {}
        self.edges: Set[tuple[str, str]] = set()

        self.setupUI()
        self.loadWbs(wbsDf)

    def setupUI(self) -> None:
        """設定使用者介面"""
        layout = QVBoxLayout(self)

        # 選單列
        menuBar = QMenuBar(self)
        layout.setMenuBar(menuBar)

        # 檔案選單
        fileMenu = menuBar.addMenu("檔案(&F)")

        exportAction = QAction("匯出 DSM(&E)...", self)
        exportAction.setShortcut(QKeySequence.SaveAs)
        exportAction.triggered.connect(self.exportDsm)
        fileMenu.addAction(exportAction)

        # 編輯選單
        editMenu = menuBar.addMenu("編輯(&E)")

        self.undoAction = QAction("撤銷(&U)", self)
        self.undoAction.setShortcut(QKeySequence.Undo)
        self.undoAction.triggered.connect(self.undo)
        self.undoAction.setEnabled(False)
        editMenu.addAction(self.undoAction)

        self.redoAction = QAction("重做(&R)", self)
        self.redoAction.setShortcut(QKeySequence.Redo)
        self.redoAction.triggered.connect(self.redo)
        self.redoAction.setEnabled(False)
        editMenu.addAction(self.redoAction)

        # 佈局選單
        layoutMenu = menuBar.addMenu("佈局(&L)")

        hierarchicalAction = QAction("階層式佈局(&H)", self)
        hierarchicalAction.triggered.connect(lambda: self.applyLayout(LayoutAlgorithm.HIERARCHICAL))
        layoutMenu.addAction(hierarchicalAction)

        orthogonalAction = QAction("正交式佈局(&O)", self)
        orthogonalAction.triggered.connect(lambda: self.applyLayout(LayoutAlgorithm.ORTHOGONAL))
        layoutMenu.addAction(orthogonalAction)

        forceAction = QAction("力導向佈局(&F)", self)
        forceAction.triggered.connect(lambda: self.applyLayout(LayoutAlgorithm.FORCE_DIRECTED))
        layoutMenu.addAction(forceAction)

        # 檢視選單
        viewMenu = menuBar.addMenu("檢視(&V)")

        self.gridAction = QAction("顯示網格(&G)", self)
        self.gridAction.setCheckable(True)
        self.gridAction.setChecked(True)
        self.gridAction.triggered.connect(self.toggleGrid)
        viewMenu.addAction(self.gridAction)

        self.snapAction = QAction("對齊網格(&S)", self)
        self.snapAction.setCheckable(True)
        self.snapAction.setChecked(True)
        self.snapAction.triggered.connect(self.toggleSnapToGrid)
        viewMenu.addAction(self.snapAction)

        # 建立場景和視圖
        self.scene = DsmScene(self)
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        # 設定場景背景為白色
        self.scene.setBackgroundBrush(QBrush(QColor(255, 255, 255)))
        self.view = CanvasView(self.scene)
        layout.addWidget(self.view)

        # 工具列
        toolLayout = QHBoxLayout()

        # 佈局按鈕群組
        layoutGroup = QGroupBox("自動佈局")
        layoutGroupLayout = QHBoxLayout(layoutGroup)

        hierarchicalBtn = QPushButton("階層式")
        hierarchicalBtn.clicked.connect(lambda: self.applyLayout(LayoutAlgorithm.HIERARCHICAL))
        layoutGroupLayout.addWidget(hierarchicalBtn)

        orthogonalBtn = QPushButton("正交式")
        orthogonalBtn.clicked.connect(lambda: self.applyLayout(LayoutAlgorithm.ORTHOGONAL))
        layoutGroupLayout.addWidget(orthogonalBtn)

        forceBtn = QPushButton("力導向")
        forceBtn.clicked.connect(lambda: self.applyLayout(LayoutAlgorithm.FORCE_DIRECTED))
        layoutGroupLayout.addWidget(forceBtn)

        toolLayout.addWidget(layoutGroup)

        # 控制按鈕群組
        controlGroup = QGroupBox("控制")
        controlGroupLayout = QHBoxLayout(controlGroup)

        exportBtn = QPushButton("匯出 DSM")
        exportBtn.clicked.connect(self.exportDsm)
        controlGroupLayout.addWidget(exportBtn)

        toolLayout.addWidget(controlGroup)
        toolLayout.addStretch()

        layout.addLayout(toolLayout)

    def loadWbs(self, wbsDf: pd.DataFrame) -> None:
        """載入 WBS 資料"""
        if wbsDf.empty:
            return

        yedYellow = QColor(255, 215, 0)

        cols = 5
        for i, row in wbsDf.iterrows():
            taskId = str(row.get("Task ID", f"Task_{i}"))
            name = str(row.get("Name", "未命名任務"))
            prop = str(row.get("Property", ""))

            if prop and prop != "nan":
                text = f"[{prop}] {name}"
            else:
                text = name

            # 檢查節點是否已存在，避免重複添加
            if taskId in self.nodes:
                continue

            node = TaskNode(taskId, text, yedYellow, self)
            node.setPos((i % cols) * 180, (i // cols) * 120)

            # 檢查項目是否已在場景中，避免重複添加警告
            if node.scene() != self.scene:
                self.scene.addItem(node)
            self.nodes[taskId] = node

    def executeCommand(self, command: Command) -> None:
        """執行命令並加入歷史記錄"""
        self.commandHistory = self.commandHistory[:self.commandIndex + 1]
        command.execute()
        self.commandHistory.append(command)
        self.commandIndex += 1
        self.updateUndoRedoState()

    def undo(self) -> None:
        """撤銷"""
        if self.commandIndex >= 0:
            self.commandHistory[self.commandIndex].undo()
            self.commandIndex -= 1
            self.updateUndoRedoState()

    def redo(self) -> None:
        """重做"""
        if self.commandIndex < len(self.commandHistory) - 1:
            self.commandIndex += 1
            self.commandHistory[self.commandIndex].execute()
            self.updateUndoRedoState()

    def updateUndoRedoState(self) -> None:
        """更新撤銷/重做按鈕狀態"""
        self.undoAction.setEnabled(self.commandIndex >= 0)
        self.redoAction.setEnabled(self.commandIndex < len(self.commandHistory) - 1)

    def toggleGrid(self) -> None:
        """切換網格顯示"""
        self.view.setGridVisible(self.gridAction.isChecked())

    def toggleSnapToGrid(self) -> None:
        """切換網格對齊"""
        self.view.setSnapToGrid(self.snapAction.isChecked())

    def addDependency(self, src: TaskNode, dst: TaskNode) -> None:
        """新增依賴關係"""
        if (src.taskId, dst.taskId) not in self.edges:
            command = AddEdgeCommand(self, src, dst)
            self.executeCommand(command)

    def removeEdge(self, edge: EdgeItem) -> None:
        """移除邊"""
        command = RemoveEdgeCommand(self, edge)
        self.executeCommand(command)

    def applyLayout(self, algorithm: LayoutAlgorithm) -> None:
        """套用佈局演算法"""
        if algorithm == LayoutAlgorithm.HIERARCHICAL:
            self.applyHierarchicalLayout()
        elif algorithm == LayoutAlgorithm.ORTHOGONAL:
            self.applyOrthogonalLayout()
        elif algorithm == LayoutAlgorithm.FORCE_DIRECTED:
            self.applyForceDirectedLayout()

    def applyHierarchicalLayout(self) -> None:
        """階層式佈局 - 增強循環檢測"""
        graph = nx.DiGraph()
        for taskId in self.nodes:
            graph.add_node(taskId)
        for src, dst in self.edges:
            graph.add_edge(src, dst)

        try:
            # 檢查是否有循環
            if not nx.is_directed_acyclic_graph(graph):
                print("警告：圖形包含循環，無法進行拓撲排序。使用替代佈局...")
                self.applySimpleHierarchicalLayout()
                return

            # 進行拓撲排序
            layers = {}
            for node in nx.topological_sort(graph):
                predecessors = list(graph.predecessors(node))
                if not predecessors:
                    layers[node] = 0
                else:
                    layers[node] = max(layers[pred] for pred in predecessors) + 1

            level_groups = {}
            for node, level in layers.items():
                if level not in level_groups:
                    level_groups[level] = []
                level_groups[level].append(node)

            level_spacing = 200
            node_spacing = 150

            for level, nodes in level_groups.items():
                y = level * level_spacing
                start_x = -(len(nodes) - 1) * node_spacing / 2

                for i, nodeId in enumerate(nodes):
                    x = start_x + i * node_spacing
                    if nodeId in self.nodes:
                        self.nodes[nodeId].setPos(x, y)

        except nx.NetworkXError as e:
            print(f"NetworkX 錯誤：{e}")
            self.applySimpleHierarchicalLayout()
        except Exception as e:
            print(f"佈局錯誤：{e}")
            self.applySimpleHierarchicalLayout()

    def applySimpleHierarchicalLayout(self) -> None:
        """簡單階層式佈局"""
        nodes = list(self.nodes.values())
        level_spacing = 200
        node_spacing = 150
        nodes_per_level = 4

        for i, node in enumerate(nodes):
            level = i // nodes_per_level
            pos_in_level = i % nodes_per_level

            start_x = -(nodes_per_level - 1) * node_spacing / 2
            x = start_x + pos_in_level * node_spacing
            y = level * level_spacing

            node.setPos(x, y)

    def applyOrthogonalLayout(self) -> None:
        """正交式佈局"""
        nodes = list(self.nodes.values())
        if not nodes:
            return

        node_count = len(nodes)
        cols = max(1, int(math.sqrt(node_count) * 1.5))

        spacing_x = 180
        spacing_y = 120

        total_width = (cols - 1) * spacing_x
        start_x = -total_width / 2

        for i, node in enumerate(nodes):
            row = i // cols
            col = i % cols

            x = start_x + col * spacing_x
            y = row * spacing_y

            node.setPos(x, y)

    def applyForceDirectedLayout(self) -> None:
        """力導向佈局"""
        graph = nx.Graph()
        for taskId in self.nodes:
            graph.add_node(taskId)
        for src, dst in self.edges:
            graph.add_edge(src, dst)

        if not graph.nodes():
            return

        try:
            pos = nx.spring_layout(
                graph,
                k=200,
                iterations=100,
                scale=300
            )

            for nodeId, (x, y) in pos.items():
                if nodeId in self.nodes:
                    self.nodes[nodeId].setPos(x, y)

        except Exception:
            self.applyOrthogonalLayout()

    def buildDsmMatrix(self) -> pd.DataFrame:
        """建立 DSM 矩陣"""
        taskIds = list(self.nodes.keys())
        matrix = pd.DataFrame(0, index=taskIds, columns=taskIds, dtype=int)
        for src, dst in self.edges:
            matrix.loc[dst, src] = 1
        return matrix

    def exportDsm(self) -> None:
        """匯出 DSM"""
        path, _ = QFileDialog.getSaveFileName(self, "匯出 DSM", "", "CSV Files (*.csv)")
        if path:
            try:
                self.buildDsmMatrix().to_csv(path, encoding="utf-8-sig")
                QMessageBox.information(self, "完成", f"已匯出 DSM：{path}")
            except OSError as e:
                QMessageBox.critical(self, "錯誤", f"匯出失敗：{e}")

    def keyPressEvent(self, event):
        """鍵盤事件處理"""
        if event.key() == Qt.Key_Escape:
            if hasattr(self.scene, 'connectionMode') and self.scene.connectionMode:
                self.scene.cancelConnectionMode()
            else:
                self.scene.clearSelection()
        elif event.key() == Qt.Key_Delete:
            selectedItems = self.scene.selectedItems()
            for item in selectedItems:
                if isinstance(item, TaskNode):
                    item.deleteNode()
                elif isinstance(item, EdgeItem) and not item.isTemporary:
                    self.removeEdge(item)
        elif event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            for item in self.scene.items():
                if isinstance(item, (TaskNode, EdgeItem)) and not getattr(item, 'isTemporary', False):
                    item.setSelected(True)
        else:
            super().keyPressEvent(event)
