from __future__ import annotations

import math
from typing import Dict, Set, Optional, List
from enum import Enum

import pandas as pd
import networkx as nx
from PyQt5.QtCore import Qt, QPointF, QRectF
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
    QLineEdit,
    QGraphicsTextItem,
    QLabel,
    QSpinBox,
    QFormLayout,
    QGroupBox,
    QComboBox,
    QDialogButtonBox,
)


class EditorState(Enum):
    """編輯器狀態枚舉"""
    IDLE = "idle"
    CREATING_EDGE = "creating_edge"
    EDITING_TEXT = "editing_text"
    SELECTING = "selecting"


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
            self.editor.scene.addItem(self.edge)
            # 確保箭頭也被加入場景
            if hasattr(self.edge, 'arrowHead'):
                self.editor.scene.addItem(self.edge.arrowHead)
            self.src.edges.append(self.edge)
            self.dst.edges.append(self.edge)
            self.editor.edges.add((self.src.taskId, self.dst.taskId))

    def undo(self) -> None:
        if self.edge:
            self.editor.scene.removeItem(self.edge)
            # 同時移除箭頭
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
            self.editor.scene.addItem(self.edge)
            if hasattr(self.edge, 'arrowHead'):
                self.editor.scene.addItem(self.edge.arrowHead)
            self.src.edges.append(self.edge)
            self.dst.edges.append(self.edge)
            self.editor.edges.add((self.src.taskId, self.dst.taskId))


class NodePropertiesDialog(QDialog):
    """節點屬性編輯對話框"""

    def __init__(self, node: 'TaskNode', editor: 'DsmEditor', parent=None):
        super().__init__(parent)
        self.node = node
        self.editor = editor
        self.setWindowTitle(f"編輯節點屬性: {node.taskId}")
        self.setModal(True)
        self.setupUI()

    def setupUI(self) -> None:
        """設定對話框介面"""
        layout = QVBoxLayout(self)

        # 基本資訊群組
        basicGroup = QGroupBox("基本資訊")
        basicLayout = QFormLayout(basicGroup)

        self.taskIdLabel = QLabel(self.node.taskId)
        basicLayout.addRow("任務 ID:", self.taskIdLabel)

        self.nameEdit = QLineEdit(self.node.text)
        basicLayout.addRow("名稱:", self.nameEdit)

        layout.addWidget(basicGroup)

        # 自訂屬性群組
        customGroup = QGroupBox("自訂屬性")
        customLayout = QFormLayout(customGroup)

        self.assigneeEdit = QLineEdit(self.node.customData.get("assignee", ""))
        customLayout.addRow("負責人:", self.assigneeEdit)

        self.statusCombo = QComboBox()
        self.statusCombo.addItems(["", "未開始", "進行中", "已完成", "暫停", "取消"])
        self.statusCombo.setCurrentText(self.node.customData.get("status", ""))
        customLayout.addRow("狀態:", self.statusCombo)

        self.durationSpin = QSpinBox()
        self.durationSpin.setRange(0, 9999)
        self.durationSpin.setSuffix(" 小時")
        self.durationSpin.setValue(self.node.customData.get("duration", 0))
        customLayout.addRow("預計工時:", self.durationSpin)

        self.priorityCombo = QComboBox()
        self.priorityCombo.addItems(["Low", "Medium", "High", "Critical"])
        self.priorityCombo.setCurrentText(self.node.customData.get("priority", "Medium"))
        customLayout.addRow("優先級:", self.priorityCombo)

        layout.addWidget(customGroup)

        # 按鈕
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def accept(self) -> None:
        """確認修改"""
        # 更新節點資料
        self.node.text = self.nameEdit.text()
        self.node.customData.update({
            "assignee": self.assigneeEdit.text(),
            "status": self.statusCombo.currentText(),
            "duration": self.durationSpin.value(),
            "priority": self.priorityCombo.currentText()
        })

        # 重新繪製節點
        self.node.update()
        super().accept()


class CanvasView(QGraphicsView):
    """提供縮放與平移功能的畫布視圖 - yEd 風格"""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self._panning = False
        self._panStart = QPointF()
        self.showGrid = True  # yEd 風格預設顯示網格
        self.gridSize = 20   # 更細密的網格
        self.snapToGrid = True  # 預設啟用對齊
        self.snapDistance = 8  # 吸附距離

        # 效能最佳化設定
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)

        # 對齊輔助線系統
        self.alignmentLines = []
        self.showAlignmentLines = True

        # 框選功能
        self._rubberBand = None
        self._rubberBandStart = QPointF()
        self._selecting = False

    def setGridVisible(self, visible: bool) -> None:
        """設定網格可見性"""
        self.showGrid = visible
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

    def addAlignmentLine(self, line):
        """新增對齊輔助線"""
        if self.showAlignmentLines:
            self.alignmentLines.append(line)
            self.scene().addItem(line)

    def clearAlignmentLines(self):
        """清除所有對齊輔助線"""
        for line in self.alignmentLines:
            if line.scene():
                self.scene().removeItem(line)
        self.alignmentLines.clear()

    def drawBackground(self, painter: QPainter, rect) -> None:  # type: ignore[override]
        """繪製 yEd 風格的背景與網格"""
        super().drawBackground(painter, rect)

        if not self.showGrid:
            return

        # yEd 風格網格 - 更淡的灰色
        painter.setPen(QPen(QColor(230, 230, 230), 1, Qt.SolidLine))

        left = int(rect.left()) - (int(rect.left()) % self.gridSize)
        top = int(rect.top()) - (int(rect.top()) % self.gridSize)

        # 垂直線
        x = left
        while x < rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += self.gridSize

        # 水平線
        y = top
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += self.gridSize

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        """支援滾輪縮放"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._panStart = QPointF(event.pos())
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            # 檢查是否點擊在空白區域以開始框選
            item = self.itemAt(event.pos())
            if not item or not isinstance(item, (TaskNode, EdgeItem)):
                # 如果沒有按住 Ctrl/Shift，清除選取
                if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                    self.scene().clearSelection()

                # 開始框選
                from PyQt5.QtWidgets import QRubberBand
                self._selecting = True
                self._rubberBandStart = self.mapToScene(event.pos())
                if not self._rubberBand:
                    self._rubberBand = QRubberBand(QRubberBand.Rectangle, self)
                self._rubberBand.setGeometry(event.pos().x(), event.pos().y(), 0, 0)
                self._rubberBand.show()
                return

            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._panning:
            delta = event.pos() - self._panStart
            self._panStart = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
        elif self._selecting and self._rubberBand:
            # 更新橡皮筋框選區域
            start_pos = self.mapFromScene(self._rubberBandStart)
            rect = QRectF(start_pos, event.pos()).normalized()
            self._rubberBand.setGeometry(rect.toRect())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.LeftButton and self._selecting:
            # 完成框選
            if self._rubberBand:
                end_pos = self.mapToScene(event.pos())
                selection_rect = QRectF(self._rubberBandStart, end_pos).normalized()

                # 選取框選區域內的所有節點
                for item in self.scene().items(selection_rect):
                    if isinstance(item, TaskNode):
                        item.setSelected(True)

                self._rubberBand.hide()
                self._selecting = False
        else:
            super().mouseReleaseEvent(event)


class ResizeHandle(QGraphicsRectItem):
    """可調整大小的把手"""

    def __init__(self, x, y, width, height, parent_node, handle_index):
        super().__init__(x, y, width, height, parent_node)
        self.parent_node = parent_node
        self.handle_index = handle_index
        self.resizing = False
        self.resize_start_pos = QPointF()
        self.initial_rect = QRectF()
        self._parent_movable = bool(parent_node.flags() & QGraphicsItem.ItemIsMovable)

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

        # 讓把手可以處理滑鼠事件
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        self.setZValue(1000)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resizing = True
            self.resize_start_pos = event.scenePos()
            self.initial_rect = self.parent_node.rect()
            self._parent_movable = bool(self.parent_node.flags() & QGraphicsItem.ItemIsMovable)
            self.parent_node.setFlag(QGraphicsItem.ItemIsMovable, False)
            event.accept()

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.scenePos() - self.resize_start_pos
            self._resizeParent(delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resizing = False
            self.parent_node.setFlag(QGraphicsItem.ItemIsMovable, self._parent_movable)
            event.accept()

    def _resizeParent(self, delta):
        """根據把手拖動調整父節點大小"""
        rect = self.initial_rect
        min_size = 50  # 最小尺寸

        # 根據把手位置調整矩形
        if self.handle_index == 0:  # 左上
            new_x = rect.x() + delta.x()
            new_y = rect.y() + delta.y()
            new_width = rect.width() - delta.x()
            new_height = rect.height() - delta.y()
        elif self.handle_index == 1:  # 上中
            new_x = rect.x()
            new_y = rect.y() + delta.y()
            new_width = rect.width()
            new_height = rect.height() - delta.y()
        elif self.handle_index == 2:  # 右上
            new_x = rect.x()
            new_y = rect.y() + delta.y()
            new_width = rect.width() + delta.x()
            new_height = rect.height() - delta.y()
        elif self.handle_index == 3:  # 右中
            new_x = rect.x()
            new_y = rect.y()
            new_width = rect.width() + delta.x()
            new_height = rect.height()
        elif self.handle_index == 4:  # 右下
            new_x = rect.x()
            new_y = rect.y()
            new_width = rect.width() + delta.x()
            new_height = rect.height() + delta.y()
        elif self.handle_index == 5:  # 下中
            new_x = rect.x()
            new_y = rect.y()
            new_width = rect.width()
            new_height = rect.height() + delta.y()
        elif self.handle_index == 6:  # 左下
            new_x = rect.x() + delta.x()
            new_y = rect.y()
            new_width = rect.width() - delta.x()
            new_height = rect.height() + delta.y()
        elif self.handle_index == 7:  # 左中
            new_x = rect.x() + delta.x()
            new_y = rect.y()
            new_width = rect.width() - delta.x()
            new_height = rect.height()
        else:
            return

        # 限制最小尺寸
        if new_width < min_size or new_height < min_size:
            return

        # 更新節點矩形
        new_rect = QRectF(new_x, new_y, new_width, new_height)
        self.parent_node.setRect(new_rect)

        # 更新把手位置
        self.parent_node._updateHandlesPosition()

        # 更新連接的邊
        for edge in self.parent_node.edges:
            if hasattr(edge, 'updatePath'):
                edge.updatePath()


class TaskNode(QGraphicsRectItem):
    """代表任務節點的圖形物件 - 增強 yEd 風格互動"""

    WIDTH = 120
    HEIGHT = 60

    def __init__(self, taskId: str, text: str, color: QColor, editor: 'DsmEditor') -> None:
        super().__init__(-TaskNode.WIDTH / 2, -TaskNode.HEIGHT / 2, TaskNode.WIDTH, TaskNode.HEIGHT)
        self.taskId = taskId
        self.text = text
        self.editor = editor
        self.edges: list[EdgeItem] = []
        self.isEditing = False

        # yEd 風格狀態管理
        self.isHovered = False
        self.isDragging = False
        self.isConnecting = False
        self.mousePressPos = QPointF()  # 記錄按下位置
        self.connectionThreshold = 8   # 連線觸發閾值
        self.dragThreshold = 12        # 拖動觸發閾值
        self._was_selected = False

        # 新增目標高亮狀態與選取把手
        self._is_highlighted = False
        self._selection_handles = []
        self._handles_visible = False

        # yEd 風格顏色 - 黃色背景，黑色邊框
        self.yedYellow = QColor(255, 215, 0)  # 金黃色，類似 yEd
        self.normalBrush = QBrush(self.yedYellow)
        self.selectedBrush = QBrush(self.yedYellow.lighter(110))
        self.hoverBrush = QBrush(self.yedYellow.lighter(105))
        self.highlightBrush = QBrush(QColor(46, 204, 113))  # 目標高亮的綠色

        self.normalPen = QPen(Qt.black, 1)
        self.selectedPen = QPen(Qt.black, 2)  # 選取時依然黑色邊框，但加粗
        self.hoverPen = QPen(Qt.black, 1)
        self.highlightPen = QPen(QColor(46, 204, 113), 2, Qt.DashLine)

        # 設定初始樣式
        self.setBrush(self.normalBrush)
        self.setPen(self.normalPen)

        # 設定互動旗標
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 初始化選取把手
        self._createSelectionHandles()

        # 自訂屬性（基於設計文件）
        self.customData = {
            "assignee": "",      # 負責人
            "status": "",        # 狀態
            "duration": 0,       # 預計工時
            "priority": "Medium"  # 優先級
        }

    def _createSelectionHandles(self) -> None:
        """建立 yEd 風格的 8 個選取把手"""
        handle_size = 6
        positions = [
            (-self.WIDTH/2, -self.HEIGHT/2),  # 左上
            (0, -self.HEIGHT/2),              # 上中
            (self.WIDTH/2, -self.HEIGHT/2),   # 右上
            (self.WIDTH/2, 0),                # 右中
            (self.WIDTH/2, self.HEIGHT/2),    # 右下
            (0, self.HEIGHT/2),               # 下中
            (-self.WIDTH/2, self.HEIGHT/2),   # 左下
            (-self.WIDTH/2, 0),               # 左中
        ]

        for i, (x, y) in enumerate(positions):
            handle = ResizeHandle(
                x - handle_size/2,
                y - handle_size/2,
                handle_size,
                handle_size,
                self,
                i  # 把手編號
            )
            handle.setBrush(QBrush(Qt.black))
            handle.setPen(QPen(Qt.black, 1))
            handle.setVisible(False)
            self._selection_handles.append(handle)

    def _updateHandlesVisibility(self, visible: bool) -> None:
        """更新選取把手的可見性"""
        self._handles_visible = visible
        for handle in self._selection_handles:
            handle.setVisible(visible)

    def _updateHandlesPosition(self) -> None:
        """更新把手位置以匹配節點大小"""
        if not self._selection_handles:
            return

        rect = self.rect()
        handle_size = 6
        positions = [
            (rect.left(), rect.top()),         # 左上
            (rect.center().x(), rect.top()),   # 上中
            (rect.right(), rect.top()),        # 右上
            (rect.right(), rect.center().y()),  # 右中
            (rect.right(), rect.bottom()),      # 右下
            (rect.center().x(), rect.bottom()),  # 下中
            (rect.left(), rect.bottom()),      # 左下
            (rect.left(), rect.center().y()),   # 左中
        ]

        for i, (handle, (x, y)) in enumerate(zip(self._selection_handles, positions)):
            handle.setRect(
                x - handle_size/2,
                y - handle_size/2,
                handle_size,
                handle_size
            )

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """節點右鍵選單"""
        menu = QMenu()

        editAction = menu.addAction("編輯標籤")
        editAction.triggered.connect(self.startTextEdit)

        propertiesAction = menu.addAction("編輯屬性...")
        propertiesAction.triggered.connect(self.showPropertiesDialog)

        menu.addSeparator()

        deleteAction = menu.addAction("刪除節點")
        deleteAction.triggered.connect(self.deleteNode)

        menu.exec_(event.screenPos())

    def startTextEdit(self) -> None:
        """開始文字編輯模式"""
        if self.isEditing:
            return

        self.isEditing = True
        self.editor.state = EditorState.EDITING_TEXT

        # 建立文字編輯器
        textItem = QGraphicsTextItem(self.text)
        textItem.setPos(self.sceneBoundingRect().topLeft())
        textItem.setTextInteractionFlags(Qt.TextEditorInteraction)
        textItem.setFocus()
        self.scene().addItem(textItem)

        # 完成編輯時的處理
        def finishEdit():
            self.text = textItem.toPlainText()
            self.scene().removeItem(textItem)
            self.isEditing = False
            self.editor.state = EditorState.IDLE
            self.update()

        textItem.focusOutEvent = lambda event: (finishEdit(), super(QGraphicsTextItem, textItem).focusOutEvent(event))

    def showPropertiesDialog(self) -> None:
        """顯示屬性編輯對話框"""
        dialog = NodePropertiesDialog(self, self.editor)
        dialog.exec_()

    def deleteNode(self) -> None:
        """刪除節點"""
        # 刪除所有相關的邊
        edges_to_remove = self.edges.copy()
        for edge in edges_to_remove:
            self.editor.removeEdge(edge)

        # 從場景和資料中移除節點
        self.scene().removeItem(self)
        del self.editor.nodes[self.taskId]

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠懸停進入時高亮節點"""
        self.isHovered = True
        self.updateVisualState()
        # 設定移動游標（十字箭頭）
        self.setCursor(Qt.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠懸停離開時還原節點"""
        self.isHovered = False
        self.updateVisualState()
        # 還原預設游標
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠按下事件 - 先選取再允許移動"""
        if event.button() == Qt.LeftButton:
            self.mousePressPos = event.scenePos()
            self._was_selected = self.isSelected()

            if not self.isSelected():
                # 第一次點擊僅進行選取
                self.scene().clearSelection()
                self.setSelected(True)
                self.updateVisualState()
                event.accept()
                return
            else:
                # 已選取狀態下才允許拖動
                self.isDragging = True

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠移動事件 - 判斷連線或拖動"""
        if event.buttons() & Qt.LeftButton:
            distance = (event.scenePos() - self.mousePressPos).manhattanLength()

            if not self._was_selected and distance > self.connectionThreshold and not self.isConnecting:
                # 未選取狀態下拖曳進入連線模式
                self.startConnectionMode()
                return

            if self.isDragging and distance > self.dragThreshold:
                self._showAlignmentGuides(event.scenePos())

        if self.isConnecting and hasattr(self.scene(), 'connectionMode'):
            self.scene().updateTempConnection(event.scenePos())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠釋放事件"""
        # 清除對齊輔助線
        if self.isDragging:
            self._clearAlignmentGuides()

        self.isDragging = False

        # 如果在連線模式下釋放，嘗試完成連線
        if self.isConnecting and hasattr(self.scene(), 'connectionMode'):
            item = self.scene().itemAt(event.scenePos(), self.scene().views()[0].transform())
            if isinstance(item, TaskNode) and item != self:
                self.scene().finishConnection(item)
            else:
                self.scene().cancelConnectionMode()

        super().mouseReleaseEvent(event)
        self._was_selected = False

    def startConnectionMode(self) -> None:
        """開始連線模式"""
        if self.scene() and hasattr(self.scene(), 'startConnectionMode'):
            self.isConnecting = True
            self.updateVisualState()

            # 視覺回饋
            self.setCursor(Qt.CrossCursor)
            if hasattr(self.editor, 'view'):
                self.editor.view.setCursor(Qt.CrossCursor)

            self.scene().startConnectionMode(self)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        """雙擊編輯文字"""
        if event.button() == Qt.LeftButton:
            self.startTextEditing()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """鍵盤事件 - F2 編輯文字"""
        if event.key() == Qt.Key_F2:
            self.startTextEditing()
        elif event.key() == Qt.Key_Delete:
            self.deleteNode()
        else:
            super().keyPressEvent(event)

    def set_highlight(self, highlighted: bool) -> None:
        """設定節點是否作為有效目標高亮"""
        if self._is_highlighted != highlighted:
            self._is_highlighted = highlighted
            self.update()  # 觸發重繪

    def updateVisualState(self) -> None:
        """更新視覺狀態 - yEd 風格"""
        # 確保把手已創建
        if not self._selection_handles:
            self._createSelectionHandles()

        # 更新選取把手的顯示狀態
        self._updateHandlesVisibility(self.isSelected())

        # 如果選中，也更新把手位置
        if self.isSelected():
            self._updateHandlesPosition()

        if self._is_highlighted:
            # 目標高亮狀態（連線時）
            self.setBrush(self.highlightBrush)
            self.setPen(self.highlightPen)
        elif self.isSelected():
            # 選取狀態 - 依然黃色，但顯示把手
            self.setBrush(self.selectedBrush)
            self.setPen(self.selectedPen)
        elif self.isHovered:
            # 懸停狀態
            self.setBrush(self.hoverBrush)
            self.setPen(self.hoverPen)
        else:
            # 正常狀態
            self.setBrush(self.normalBrush)
            self.setPen(self.normalPen)

    def startTextEditing(self) -> None:
        """開始文字編輯模式"""
        # 這裡可以實作內嵌文字編輯，目前使用對話框
        dialog = NodePropertiesDialog(self, self.editor)
        if dialog.exec_() == dialog.Accepted:
            self.update()

    def paint(self, painter, option, widget=None) -> None:  # type: ignore[override]
        """繪製節點，並根據選取和高亮狀態提供視覺回饋"""
        from PyQt5.QtWidgets import QStyleOptionGraphicsItem, QStyle

        # 建立 option 的副本以進行修改，避免影響原始狀態
        opt = QStyleOptionGraphicsItem(option)

        # 如果節點被選取，則不繪製預設的虛線框
        if opt.state & QStyle.State_Selected:
            opt.state &= ~QStyle.State_Selected

        # yEd 風格基礎繪製
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(self.rect())  # 使用方形而非圓角矩形

        # 繪製文字
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)  # yEd 風格 - 粗體字
        painter.setFont(font)
        painter.setPen(QPen(Qt.black))
        painter.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, self.text)

    def _showAlignmentGuides(self, mousePos):
        """顯示對齊輔助線"""
        if not hasattr(self.editor, 'view'):
            return

        view = self.editor.view
        if not view.showAlignmentLines:
            return

        # 清除現有的輔助線
        view.clearAlignmentLines()

        scene_rect = self.scene().sceneRect()
        current_center = mousePos

        # 跟其他節點對齊
        for item in self.scene().items():
            if isinstance(item, TaskNode) and item != self:
                other_center = item.sceneBoundingRect().center()

                # 水平對齊
                if abs(other_center.y() - current_center.y()) < view.snapDistance:
                    from PyQt5.QtWidgets import QGraphicsLineItem
                    line = QGraphicsLineItem(scene_rect.left(), other_center.y(),
                                             scene_rect.right(), other_center.y())
                    line.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))  # 紅色虛線
                    view.addAlignmentLine(line)

                # 垂直對齊
                if abs(other_center.x() - current_center.x()) < view.snapDistance:
                    from PyQt5.QtWidgets import QGraphicsLineItem
                    line = QGraphicsLineItem(other_center.x(), scene_rect.top(),
                                             other_center.x(), scene_rect.bottom())
                    line.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))  # 紅色虛線
                    view.addAlignmentLine(line)

    def _clearAlignmentGuides(self):
        """清除對齊輔助線"""
        if hasattr(self.editor, 'view'):
            self.editor.view.clearAlignmentLines()

    def itemChange(self, change, value):  # type: ignore[override]
        """
        覆寫 itemChange 以在節點移動時更新相連的邊。
        這是處理此類更新的官方推薦方式。
        """
        if change == QGraphicsItem.ItemPositionHasChanged:
            # 當節點位置實際改變後，通知每條邊進行自我調整
            for edge in self.edges:
                if hasattr(edge, 'adjust'):
                    edge.adjust()
                elif hasattr(edge, 'updatePath'):
                    edge.updatePath()
        elif change == QGraphicsItem.ItemPositionChange:
            # 對齊網格和對齊輔助
            if hasattr(self.editor, 'view'):
                view = self.editor.view
                if view.snapToGrid:
                    value = view.snapPointToGrid(value)  # type: ignore

                # 對齊其他節點
                scene = self.scene()
                if scene:
                    for item in scene.items():
                        if isinstance(item, TaskNode) and item != self:
                            other_center = item.sceneBoundingRect().center()
                            new_center = QPointF(value.x() + self.WIDTH/2, value.y() + self.HEIGHT/2)

                            # X 軸對齊
                            if abs(other_center.x() - new_center.x()) < view.snapDistance:
                                value.setX(other_center.x() - self.WIDTH/2)

                            # Y 軸對齊
                            if abs(other_center.y() - new_center.y()) < view.snapDistance:
                                value.setY(other_center.y() - self.HEIGHT/2)

        elif change == QGraphicsItem.ItemSelectedChange:
            # 選取狀態變化時更新視覺樣式
            self.updateVisualState()

        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    """代表依賴關係的箭頭連線 - 模仿 yEd 的視覺效果"""

    def __init__(self, src: TaskNode, dst: TaskNode) -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.label = ""
        self.isTemporary = False  # 是否為臨時連線

        # yEd 風格的黑色連線
        self.normalPen = QPen(Qt.black, 2, Qt.SolidLine)  # 黑色實線
        self.hoverPen = QPen(Qt.black, 3, Qt.SolidLine)   # 懸停時稍粗
        self.selectedPen = QPen(Qt.blue, 3, Qt.SolidLine)  # 選中時藍色
        self.tempPen = QPen(Qt.black, 2, Qt.SolidLine)  # 臨時連線也是實線

        self.setPen(self.normalPen)
        self.setZValue(1)  # 確保在節點上方
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 建立 yEd 風格的黑色箭頭
        self.arrowHead = QGraphicsPathItem()
        self.arrowHead.setBrush(QBrush(Qt.black))
        self.arrowHead.setPen(QPen(Qt.black, 1))
        self.arrowHead.setZValue(2)

        # 將箭頭設為此邊線的子物件
        self.arrowHead.setParentItem(self)

        self.updatePath()

    def adjust(self) -> None:
        """根據源和目標節點的位置更新邊的線段"""
        if not self.src or not self.dst:
            return

        # 準備幾何變更並更新路徑
        self.prepareGeometryChange()
        self.updatePath()

    def setTemporary(self, temporary: bool) -> None:
        """設定是否為臨時連線 - yEd 風格視覺回饋"""
        self.isTemporary = temporary
        if temporary:
            # 臨時連線使用黑色實線，與預覽保持一致
            self.tempPen = QPen(Qt.black, 2, Qt.SolidLine)
            self.setPen(self.tempPen)
            if hasattr(self, 'arrowHead'):
                self.arrowHead.setBrush(QBrush(Qt.black))
                self.arrowHead.setPen(QPen(Qt.black, 1))
        else:
            # 正式連線使用黑色實線
            self.setPen(QPen(Qt.black, 2, Qt.SolidLine))
            if hasattr(self, 'arrowHead'):
                self.arrowHead.setBrush(QBrush(Qt.black))
                self.arrowHead.setPen(QPen(Qt.black, 1))

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """邊的右鍵選單"""
        menu = QMenu()

        editLabelAction = menu.addAction("編輯標籤")
        editLabelAction.triggered.connect(self.editLabel)

        deleteAction = menu.addAction("刪除依賴")
        deleteAction.triggered.connect(self.deleteEdge)

        menu.exec_(event.screenPos())

    def editLabel(self) -> None:
        """編輯邊標籤"""
        from PyQt5.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(
            None,
            "編輯標籤",
            "輸入依賴關係描述:",
            text=self.label
        )

        if ok:
            self.label = text
            self.update()

    def deleteEdge(self) -> None:
        """刪除此邊"""
        if self.isTemporary:
            return

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

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠懸停進入 - 高亮顯示"""
        if not self.isTemporary:
            self.setPen(self.hoverPen)
            # yEd 風格 - 懸停時箭頭依然保持黑色
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠懸停離開"""
        if not self.isTemporary:
            if self.isSelected():
                self.setPen(self.selectedPen)
            else:
                self.setPen(self.normalPen)
            # yEd 風格 - 箭頭始終保持黑色
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """項目變化處理"""
        if change == QGraphicsItem.ItemSelectedChange and not self.isTemporary:
            if value:  # 選中
                self.setPen(self.selectedPen)
            else:  # 取消選中
                self.setPen(self.normalPen)
            # yEd 風格 - 箭頭始終保持黑色
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None) -> None:  # type: ignore[override]
        """自訂繪製以顯示標籤"""
        # 繪製邊線
        super().paint(painter, option, widget)

        # 如果有標籤，在邊的中點繪製
        if self.label:
            srcPos = self.src.sceneBoundingRect().center()
            dstPos = self.dst.sceneBoundingRect().center()
            midPoint = QPointF(
                (srcPos.x() + dstPos.x()) / 2,
                (srcPos.y() + dstPos.y()) / 2
            )

            # 設定字型和背景
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)

            # 繪製背景矩形
            textRect = painter.fontMetrics().boundingRect(self.label)
            textRect.moveCenter(midPoint.toPoint())
            textRect.adjust(-2, -1, 2, 1)

            painter.fillRect(textRect, QBrush(QColor(255, 255, 255, 200)))
            painter.setPen(QPen(Qt.black))
            painter.drawRect(textRect)

            # 繪製文字
            painter.drawText(textRect, Qt.AlignCenter, self.label)

    def updatePath(self) -> None:
        """更新箭頭路徑 - 參考 yEd 的連線算法"""
        if not self.src or not self.dst:
            return

        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()

        # 計算最佳連接點（邊界交點）
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()

        # 計算方向向量
        dx = dstCenter.x() - srcCenter.x()
        dy = dstCenter.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1:  # 避免除零
            return

        # 正規化
        dx /= length
        dy /= length

        # 計算與節點邊界的交點
        srcPos = self.getConnectionPoint(srcRect, srcCenter, dx, dy, True)
        dstPos = self.getConnectionPoint(dstRect, dstCenter, -dx, -dy, False)

        # 建立主線路徑
        path = QPainterPath()
        path.moveTo(srcPos)
        path.lineTo(dstPos)
        self.setPath(path)

        # 更新箭頭
        self.updateArrowHead(srcPos, dstPos)

    def getConnectionPoint(self, rect, center, dx, dy, isSource):
        """計算與矩形邊界的交點"""
        # 計算到各邊的距離
        halfWidth = rect.width() / 2
        halfHeight = rect.height() / 2

        # 計算交點
        if abs(dx) > abs(dy):
            # 主要是水平方向
            if dx > 0:
                # 右邊
                x = center.x() + halfWidth
                y = center.y() + dy * halfWidth / abs(dx)
            else:
                # 左邊
                x = center.x() - halfWidth
                y = center.y() - dy * halfWidth / abs(dx)
        else:
            # 主要是垂直方向
            if dy > 0:
                # 下邊
                y = center.y() + halfHeight
                x = center.x() + dx * halfHeight / abs(dy)
            else:
                # 上邊
                y = center.y() - halfHeight
                x = center.x() - dx * halfHeight / abs(dy)

        return QPointF(x, y)

    def updateArrowHead(self, srcPos, dstPos):
        """更新箭頭形狀"""
        if not hasattr(self, 'arrowHead'):
            return

        # 箭頭已經設為父項目，不需要再加入場景

        # 計算箭頭方向
        dx = dstPos.x() - srcPos.x()
        dy = dstPos.y() - srcPos.y()
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1:
            return

        # 正規化
        dx /= length
        dy /= length

        # 箭頭大小
        arrowSize = 18
        arrowAngle = math.pi / 5  # 36度

        # 計算箭頭的三個點
        tip = dstPos
        angle = math.atan2(dy, dx)

        left = QPointF(
            tip.x() - arrowSize * math.cos(angle - arrowAngle),
            tip.y() - arrowSize * math.sin(angle - arrowAngle)
        )
        right = QPointF(
            tip.x() - arrowSize * math.cos(angle + arrowAngle),
            tip.y() - arrowSize * math.sin(angle + arrowAngle)
        )

        # 建立箭頭路徑
        arrowPath = QPainterPath()
        arrowPath.moveTo(tip)
        arrowPath.lineTo(left)
        arrowPath.lineTo(right)
        arrowPath.closeSubpath()

        self.arrowHead.setPath(arrowPath)


class DsmScene(QGraphicsScene):
    """支援 yEd 風格連線操作的場景"""

    # 狀態常量
    MODE_IDLE = 0
    MODE_DRAGGING_EDGE = 1

    def __init__(self, editor: 'DsmEditor') -> None:
        super().__init__()
        self.editor = editor

        # 狀態機屬性
        self.mode = self.MODE_IDLE
        self.source_node = None
        self.preview_edge = None
        self.last_hovered_target = None

        # 保留舊的相容性屬性
        self.connectionMode = False
        self.sourceNode = None
        self.tempEdge = None

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        # 連線模式改為只有在 TaskNode 明確觸發時才啟動
        # 這樣節點的移動功能才不會被干擾

        # 右鍵取消連線模式
        if event.button() == Qt.RightButton and self.mode == self.MODE_DRAGGING_EDGE:
            self._cleanupConnectionMode()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.mode == self.MODE_DRAGGING_EDGE and self.preview_edge:
            # 不斷更新 preview_edge 的終點到當前滑鼠位置
            line = self.preview_edge.line()
            line.setP2(event.scenePos())
            self.preview_edge.setLine(line)

            # 偵測滑鼠下的物件進行高亮處理
            target_item = self.itemAt(event.scenePos(), self.views()[0].transform())

            # 清除上一個高亮的目標
            if self.last_hovered_target and self.last_hovered_target != target_item:
                if hasattr(self.last_hovered_target, 'set_highlight'):
                    self.last_hovered_target.set_highlight(False)
                self.last_hovered_target = None

            # 如果懸停在有效的 TaskNode 目標上，呼叫該節點的 set_highlight(True) 方法
            if isinstance(target_item, TaskNode) and target_item != self.source_node:
                if hasattr(target_item, 'set_highlight'):
                    target_item.set_highlight(True)
                self.last_hovered_target = target_item

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠釋放事件處理"""
        if self.mode == self.MODE_DRAGGING_EDGE:
            # 檢查滑鼠是否在一個有效的 TaskNode 目標上釋放
            target_item = self.itemAt(event.scenePos(), self.views()[0].transform())

            if isinstance(target_item, TaskNode) and target_item != self.source_node:
                # 呼叫主編輯器的 addDependency 來建立永久的 EdgeItem
                if hasattr(self.editor, 'addDependency'):
                    self.editor.addDependency(self.source_node, target_item)

            # 清理現場：移除 preview_edge，並將狀態重設回 MODE_IDLE
            self._cleanupConnectionMode()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _cleanupConnectionMode(self) -> None:
        """清理連線模式狀態"""
        # 清理高亮目標
        if self.last_hovered_target and hasattr(self.last_hovered_target, 'set_highlight'):
            self.last_hovered_target.set_highlight(False)
            self.last_hovered_target = None

        # 移除預覽線
        if self.preview_edge:
            self.removeItem(self.preview_edge)
            self.preview_edge = None

        # 重設狀態
        self.mode = self.MODE_IDLE
        if self.source_node:
            self.source_node.isConnecting = False
            self.source_node.setCursor(Qt.ArrowCursor)
            self.source_node.updateVisualState()
        self.source_node = None

        # 清理相容性屬性
        self.connectionMode = False
        self.sourceNode = None
        if self.tempEdge:
            self.removeItem(self.tempEdge)
            if hasattr(self.tempEdge, 'arrowHead') and self.tempEdge.arrowHead.scene():
                self.removeItem(self.tempEdge.arrowHead)
            self.tempEdge = None

        # 恢復游標
        for view in self.views():
            view.setCursor(Qt.ArrowCursor)

    def startConnectionMode(self, sourceNode: TaskNode) -> None:
        """開始連線模式 - yEd 風格長壓拖拽"""
        self.connectionMode = True
        self.sourceNode = sourceNode

        # 建立臨時連線（帶箭頭的實線預覽）
        self.tempEdge = EdgeItem(sourceNode, sourceNode)
        self.tempEdge.setTemporary(True)
        self.addItem(self.tempEdge)

        # 確保箭頭也被加入場景
        if hasattr(self.tempEdge, 'arrowHead'):
            self.addItem(self.tempEdge.arrowHead)

        # 變更游標樣式表示連線模式
        for view in self.views():
            view.setCursor(Qt.CrossCursor)

        # 給予源節點視覺回饋
        sourceNode.isConnecting = True
        sourceNode.updateVisualState()

    def updateTempConnection(self, mousePos: QPointF) -> None:
        """更新臨時連線 - 實時跟隨滑鼠並顯示箭頭"""
        if not self.tempEdge or not self.sourceNode:
            return

        # 重新計算連線路徑
        srcRect = self.sourceNode.sceneBoundingRect()
        srcCenter = srcRect.center()

        dx = mousePos.x() - srcCenter.x()
        dy = mousePos.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)

        if length > 1:
            dx /= length
            dy /= length

            # 從節點邊緣開始連線
            srcPos = self.tempEdge.getConnectionPoint(srcRect, srcCenter, dx, dy, True)

            # 建立主線路徑
            path = QPainterPath()
            path.moveTo(srcPos)
            path.lineTo(mousePos)
            self.tempEdge.setPath(path)

            # 更新箭頭位置
            if hasattr(self.tempEdge, 'arrowHead'):
                self.tempEdge.updateArrowHead(srcPos, mousePos)

        # 檢查是否懸停在目標節點上，提供視覺回饋
        targetItem = self.itemAt(mousePos, self.views()[0].transform())
        if isinstance(targetItem, TaskNode) and targetItem != self.sourceNode:
            # 目標節點高亮
            if not hasattr(targetItem, '_wasHovered'):
                targetItem._wasHovered = targetItem.isHovered
            targetItem.isHovered = True
            targetItem.updateVisualState()
        else:
            # 清除之前的目標節點高亮
            for item in self.items():
                if isinstance(item, TaskNode) and hasattr(item, '_wasHovered'):
                    item.isHovered = item._wasHovered
                    item.updateVisualState()
                    delattr(item, '_wasHovered')

    def finishConnection(self, targetNode: TaskNode) -> None:
        """完成連線"""
        if not self.connectionMode or not self.sourceNode or targetNode == self.sourceNode:
            self.cancelConnectionMode()
            return

        # 檢查是否已經存在連線
        if (self.sourceNode.taskId, targetNode.taskId) not in self.editor.edges:
            # 建立正式連線
            self.editor.addDependency(self.sourceNode, targetNode)

        self.cancelConnectionMode()

    def cancelConnectionMode(self) -> None:
        """取消連線模式 - 保留舊方法名稱以兼容"""
        self._cleanupConnectionMode()


class DsmEditor(QDialog):
    """視覺化 DSM 編輯器"""

    def __init__(self, wbsDf: pd.DataFrame, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("依賴關係編輯器")
        self.resize(1200, 800)

        # 初始化狀態
        self.state = EditorState.IDLE
        self.commandHistory: List[Command] = []
        self.commandIndex = -1

        self.setupUI()

        self.nodes: Dict[str, TaskNode] = {}
        self.edges: Set[tuple[str, str]] = set()
        self.tempLine: EdgeItem | None = None
        self.isConnecting = False
        self.srcNode: TaskNode | None = None

        self.loadWbs(wbsDf)

    def setupUI(self) -> None:
        """設定使用者介面"""
        # 主佈局
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
        self.gridAction.triggered.connect(self.toggleGrid)
        viewMenu.addAction(self.gridAction)

        self.snapAction = QAction("對齊網格(&S)", self)
        self.snapAction.setCheckable(True)
        self.snapAction.triggered.connect(self.toggleSnapToGrid)
        viewMenu.addAction(self.snapAction)

        viewMenu.addSeparator()

        self.maximizeAction = QAction("最大化視窗(&M)", self)
        self.maximizeAction.setShortcut("F11")
        self.maximizeAction.setCheckable(True)
        self.maximizeAction.triggered.connect(self.toggleMaximize)
        viewMenu.addAction(self.maximizeAction)

        self.fullscreenAction = QAction("全螢幕(&F)", self)
        self.fullscreenAction.setShortcut(QKeySequence.FullScreen)
        self.fullscreenAction.setCheckable(True)
        self.fullscreenAction.triggered.connect(self.toggleFullscreen)
        viewMenu.addAction(self.fullscreenAction)

        # 建立場景和視圖
        self.scene = DsmScene(self)
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
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

        undoBtn = QPushButton("撤銷")
        undoBtn.clicked.connect(self.undo)
        controlGroupLayout.addWidget(undoBtn)

        redoBtn = QPushButton("重做")
        redoBtn.clicked.connect(self.redo)
        controlGroupLayout.addWidget(redoBtn)

        exportBtn = QPushButton("匯出 DSM")
        exportBtn.clicked.connect(self.exportDsm)
        controlGroupLayout.addWidget(exportBtn)

        toolLayout.addWidget(controlGroup)

        layout.addLayout(toolLayout)

    def executeCommand(self, command: Command) -> None:
        """執行命令並加入歷史記錄"""
        # 清除重做歷史
        self.commandHistory = self.commandHistory[:self.commandIndex + 1]

        # 執行命令
        command.execute()

        # 加入歷史記錄
        self.commandHistory.append(command)
        self.commandIndex += 1

        # 更新 UI 狀態
        self.updateUndoRedoState()

    def undo(self) -> None:
        """撤銷上一個操作"""
        if self.commandIndex >= 0:
            self.commandHistory[self.commandIndex].undo()
            self.commandIndex -= 1
            self.updateUndoRedoState()

    def redo(self) -> None:
        """重做下一個操作"""
        if self.commandIndex < len(self.commandHistory) - 1:
            self.commandIndex += 1
            self.commandHistory[self.commandIndex].execute()
            self.updateUndoRedoState()

    def updateUndoRedoState(self) -> None:
        """更新撤銷/重做按鈕狀態"""
        can_undo = self.commandIndex >= 0
        can_redo = self.commandIndex < len(self.commandHistory) - 1

        self.undoAction.setEnabled(can_undo)
        self.redoAction.setEnabled(can_redo)

    def toggleGrid(self) -> None:
        """切換網格顯示"""
        visible = self.gridAction.isChecked()
        self.view.setGridVisible(visible)

    def toggleSnapToGrid(self) -> None:
        """切換網格對齊"""
        snap = self.snapAction.isChecked()
        self.view.setSnapToGrid(snap)

    def toggleMaximize(self) -> None:
        """切換視窗最大化"""
        if self.maximizeAction.isChecked():
            self.showMaximized()
        else:
            self.showNormal()

    def toggleFullscreen(self) -> None:
        """切換全螢幕模式"""
        if self.fullscreenAction.isChecked():
            self.showFullScreen()
        else:
            self.showNormal()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """處理鍵盤事件 - 增強版"""
        if event.key() == Qt.Key_Escape:
            # ESC 鍵的優先級處理
            if hasattr(self.scene, 'connectionMode') and self.scene.connectionMode:
                # 第一優先：取消連線模式
                self.scene.cancelConnectionMode()
            elif self.isFullScreen():
                # 第二優先：退出全螢幕
                self.fullscreenAction.setChecked(False)
                self.showNormal()
            else:
                # 第三優先：清除所有選取
                self.scene.clearSelection()
        elif event.key() == Qt.Key_Delete:
            # Delete 鍵刪除選中的項目
            selectedItems = self.scene.selectedItems()
            for item in selectedItems:
                if isinstance(item, TaskNode):
                    item.deleteNode()
                elif isinstance(item, EdgeItem) and not item.isTemporary:
                    self.removeEdge(item)
        elif event.key() == Qt.Key_F2:
            # F2 編輯選中節點的標籤
            selectedItems = self.scene.selectedItems()
            for item in selectedItems:
                if isinstance(item, TaskNode):
                    item.startTextEditing()
                    break
        elif event.key() == Qt.Key_F11:
            # F11 切換最大化視窗
            self.maximizeAction.setChecked(not self.maximizeAction.isChecked())
            self.toggleMaximize()
        elif event.key() == Qt.Key_F12:
            # F12 切換全螢幕
            self.fullscreenAction.setChecked(not self.fullscreenAction.isChecked())
            self.toggleFullscreen()
        elif event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            # Ctrl+A 全選
            for item in self.scene.items():
                if isinstance(item, (TaskNode, EdgeItem)) and not getattr(item, 'isTemporary', False):
                    item.setSelected(True)
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event) -> None:  # type: ignore[override]
        """處理視窗狀態變化"""
        if event.type() == event.WindowStateChange:
            # 同步選單狀態與實際視窗狀態
            if self.isMaximized():
                self.maximizeAction.setChecked(True)
            elif self.isFullScreen():
                self.fullscreenAction.setChecked(True)
            else:
                self.maximizeAction.setChecked(False)
                self.fullscreenAction.setChecked(False)
        super().changeEvent(event)

    def loadWbs(self, wbsDf: pd.DataFrame) -> None:
        """依據 WBS 自動建立任務節點"""
        if wbsDf.empty:
            return

        # 安全地獲取屬性列表
        try:
            properties = wbsDf["Property"].dropna().unique().tolist()
        except KeyError:
            properties = ["Default"]
        # yEd 風格 - 統一使用黃色節點
        yedYellow = QColor(255, 215, 0)  # 金黃色
        colors: Dict[str, QColor] = {}
        for prop in properties:
            colors[prop] = yedYellow

        # 預設顏色也是黃色
        colors[""] = yedYellow
        colors["Default"] = yedYellow

        # 建立節點
        cols = 5
        for i, row in wbsDf.iterrows():
            try:
                # 安全地獲取節點資料
                taskId = str(row.get("Task ID", f"Task_{i}"))
                name = str(row.get("Name", "未命名任務"))
                prop = str(row.get("Property", ""))

                # 建立節點顯示文字
                if prop and prop != "nan":
                    text = f"[{prop}] {name}"
                else:
                    text = name
                    prop = "Default"

                # 建立節點
                node = TaskNode(taskId, text, colors.get(prop, QColor("lightgray")), self)

                # 設定節點位置
                node.setPos((i % cols) * 150, (i // cols) * 120)

                # 加入場景和節點字典
                self.scene.addItem(node)
                self.nodes[taskId] = node

            except Exception as e:
                print(f"建立節點時發生錯誤: {e}")
                continue

    def startConnection(self, node: TaskNode) -> None:
        """開始連線操作（保留於相容性）"""
        # 使用新的 scene 連線模式
        self.scene.startConnectionMode(node)

    def updateConnection(self, pos: QPointF) -> None:
        """更新連線狀態（保留於相容性）"""
        # 新的實作中自動處理
        pass

    def finishConnection(self, item) -> None:
        """完成連線操作（保留於相容性）"""
        # 新的實作中自動處理
        pass

    def addDependency(self, src: TaskNode, dst: TaskNode) -> None:
        """新增依賴關係並繪製箭頭"""
        if (src.taskId, dst.taskId) not in self.edges:
            command = AddEdgeCommand(self, src, dst)
            self.executeCommand(command)

    def removeEdge(self, edge: EdgeItem) -> None:
        """移除邊"""
        self.scene.removeItem(edge)
        edge.src.edges.remove(edge)
        edge.dst.edges.remove(edge)
        self.edges.discard((edge.src.taskId, edge.dst.taskId))

    def applyLayout(self, algorithm: LayoutAlgorithm) -> None:
        """套用指定的佈局演算法"""
        if algorithm == LayoutAlgorithm.HIERARCHICAL:
            self.applyHierarchicalLayout()
        elif algorithm == LayoutAlgorithm.ORTHOGONAL:
            self.applyOrthogonalLayout()
        elif algorithm == LayoutAlgorithm.FORCE_DIRECTED:
            self.applyForceDirectedLayout()

    def applyHierarchicalLayout(self) -> None:
        """套用階層式佈局（Sugiyama 風格）"""
        # 建立 NetworkX 圖
        graph = nx.DiGraph()
        for taskId in self.nodes:
            graph.add_node(taskId)
        for src, dst in self.edges:
            graph.add_edge(src, dst)

        try:
            # 計算拓樸層級
            layers = {}
            for node in nx.topological_sort(graph):
                # 計算該節點的最大前驅層級
                predecessors = list(graph.predecessors(node))
                if not predecessors:
                    layers[node] = 0
                else:
                    layers[node] = max(layers[pred] for pred in predecessors) + 1

            # 按層級分組
            level_groups = {}
            for node, level in layers.items():
                if level not in level_groups:
                    level_groups[level] = []
                level_groups[level].append(node)

            # 設定節點位置
            level_spacing = 200
            node_spacing = 150

            for level, nodes in level_groups.items():
                y = level * level_spacing
                start_x = -(len(nodes) - 1) * node_spacing / 2

                for i, nodeId in enumerate(nodes):
                    x = start_x + i * node_spacing
                    if nodeId in self.nodes:
                        self.nodes[nodeId].setPos(x, y)

        except nx.NetworkXError:
            # 如果圖有循環，使用簡單的層級排列
            self.applySimpleHierarchicalLayout()

    def applySimpleHierarchicalLayout(self) -> None:
        """簡單的階層式佈局（當圖有循環時使用）"""
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
        """套用正交式佈局（網格式）"""
        nodes = list(self.nodes.values())
        if not nodes:
            return

        # 計算網格大小
        node_count = len(nodes)
        cols = max(1, int(math.sqrt(node_count) * 1.5))

        # 網格間距
        spacing_x = 180
        spacing_y = 120

        # 計算起始位置（置中）
        total_width = (cols - 1) * spacing_x
        start_x = -total_width / 2

        for i, node in enumerate(nodes):
            row = i // cols
            col = i % cols

            x = start_x + col * spacing_x
            y = row * spacing_y

            node.setPos(x, y)

    def applyForceDirectedLayout(self) -> None:
        """套用力導向佈局（物理模擬）"""
        # 建立 NetworkX 圖
        graph = nx.Graph()  # 使用無向圖進行力導向佈局
        for taskId in self.nodes:
            graph.add_node(taskId)
        for src, dst in self.edges:
            graph.add_edge(src, dst)

        if not graph.nodes():
            return

        try:
            # 使用 spring 佈局
            pos = nx.spring_layout(
                graph,
                k=200,  # 理想邊長
                iterations=100,  # 迭代次數
                scale=300  # 整體縮放
            )

            # 套用位置
            for nodeId, (x, y) in pos.items():
                if nodeId in self.nodes:
                    self.nodes[nodeId].setPos(x, y)

        except Exception:
            # 如果力導向佈局失敗，回退到正交佈局
            self.applyOrthogonalLayout()

    def addDependencyById(self, srcId: str, dstId: str) -> None:
        """透過任務 ID 新增依賴關係（供測試使用）"""
        src = self.nodes.get(srcId)
        dst = self.nodes.get(dstId)
        if src and dst:
            self.addDependency(src, dst)

    def buildDsmMatrix(self) -> pd.DataFrame:
        """依目前連線生成 DSM 矩陣"""
        taskIds = list(self.nodes.keys())
        matrix = pd.DataFrame(0, index=taskIds, columns=taskIds, dtype=int)
        for src, dst in self.edges:
            matrix.loc[src, dst] = 1
        return matrix

    def exportDsm(self) -> None:
        """匯出 DSM 矩陣為 CSV"""
        path, _ = QFileDialog.getSaveFileName(self, "匯出 DSM", "", "CSV Files (*.csv)")
        if path:
            try:
                self.buildDsmMatrix().to_csv(path, encoding="utf-8-sig")
                QMessageBox.information(self, "完成", f"已匯出 DSM：{path}")
            except OSError as e:
                QMessageBox.critical(self, "錯誤", f"匯出失敗：{e}")
