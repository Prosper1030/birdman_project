from __future__ import annotations

import math
from typing import Dict, Set, Optional, List
from enum import Enum

import pandas as pd
import networkx as nx
from PyQt5.QtCore import Qt, QPointF, QTimer
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
    """提供縮放與平移功能的畫布視圖"""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self._panning = False
        self._panStart = QPointF()
        self.showGrid = False
        self.gridSize = 50
        self.snapToGrid = False

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

    def drawBackground(self, painter: QPainter, rect) -> None:  # type: ignore[override]
        """繪製背景與網格"""
        super().drawBackground(painter, rect)

        if not self.showGrid:
            return

        # 繪製網格
        painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.DotLine))

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
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)


class TaskNode(QGraphicsRectItem):
    """代表任務節點的圖形物件 - 增強 yEd 風格互動"""

    WIDTH = 120
    HEIGHT = 60

    def __init__(self, taskId: str, text: str, color: QColor, editor: 'DsmEditor') -> None:
        super().__init__(-TaskNode.WIDTH / 2, -TaskNode.HEIGHT / 2, TaskNode.WIDTH, TaskNode.HEIGHT)
        self.taskId = taskId
        self.text = text
        self.originalColor = color
        self.editor = editor
        self.edges: list[EdgeItem] = []
        self.isEditing = False

        # yEd 風格狀態管理
        self.isHovered = False
        self.isDragging = False
        self.isConnecting = False
        self.dragStartTime = 0
        self.longPressThreshold = 300  # ms for long press detection
        self.longPressTimer = None

        # 視覺樣式定義
        self.normalBrush = QBrush(color)
        self.selectedBrush = QBrush(color.darker(110))
        self.hoverBrush = QBrush(color.lighter(115))
        self.connectingBrush = QBrush(QColor(100, 200, 255))  # 連線模式的藍色

        self.normalPen = QPen(Qt.black, 1)
        self.selectedPen = QPen(QColor(255, 140, 0), 3)  # 橙色選取框
        self.hoverPen = QPen(Qt.blue, 2)
        self.connectingPen = QPen(QColor(0, 120, 255), 3)  # 連線模式的藍色邊框

        # 設定初始樣式
        self.setBrush(self.normalBrush)
        self.setPen(self.normalPen)

        # 設定互動旗標
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 自訂屬性（基於設計文件）
        self.customData = {
            "assignee": "",      # 負責人
            "status": "",        # 狀態
            "duration": 0,       # 預計工時
            "priority": "Medium"  # 優先級
        }

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
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠懸停離開時還原節點"""
        self.isHovered = False
        self.updateVisualState()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠按下事件 - yEd 風格長壓檢測"""
        if event.button() == Qt.LeftButton:
            # 記錄按下時間，用於長壓檢測
            import time
            self.dragStartTime = time.time() * 1000

            # 設定長壓計時器
            if self.longPressTimer:
                self.longPressTimer.stop()

            self.longPressTimer = QTimer()
            self.longPressTimer.timeout.connect(self.startConnectionMode)
            self.longPressTimer.setSingleShot(True)
            self.longPressTimer.start(self.longPressThreshold)

            # 標準選取處理
            if not (event.modifiers() & Qt.ControlModifier):
                # 如果沒按 Ctrl，先清除其他選取
                if not self.isSelected():
                    self.scene().clearSelection()

            self.setSelected(True)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠移動事件 - 處理拖動與連線"""
        if self.longPressTimer and self.longPressTimer.isActive():
            # 如果開始移動，取消長壓計時器（變成拖動模式）
            self.longPressTimer.stop()
            self.isDragging = True

        # 如果在連線模式，更新連線預覽
        if self.isConnecting and hasattr(self.scene(), 'connectionMode'):
            self.scene().updateTempConnection(event.scenePos())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠釋放事件"""
        if self.longPressTimer and self.longPressTimer.isActive():
            self.longPressTimer.stop()

        self.isDragging = False

        # 如果在連線模式下釋放，嘗試完成連線
        if self.isConnecting and hasattr(self.scene(), 'connectionMode'):
            item = self.scene().itemAt(event.scenePos(), self.scene().views()[0].transform())
            if isinstance(item, TaskNode) and item != self:
                self.scene().finishConnection(item)
            else:
                self.scene().cancelConnectionMode()

        super().mouseReleaseEvent(event)

    def startConnectionMode(self) -> None:
        """開始連線模式（長壓觸發）"""
        if self.scene() and hasattr(self.scene(), 'startConnectionMode'):
            self.isConnecting = True
            self.updateVisualState()
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

    def updateVisualState(self) -> None:
        """更新視覺狀態"""
        if self.isConnecting:
            self.setBrush(self.connectingBrush)
            self.setPen(self.connectingPen)
        elif self.isSelected():
            self.setBrush(self.selectedBrush)
            self.setPen(self.selectedPen)
        elif self.isHovered:
            self.setBrush(self.hoverBrush)
            self.setPen(self.hoverPen)
        else:
            self.setBrush(self.normalBrush)
            self.setPen(self.normalPen)

    def startTextEditing(self) -> None:
        """開始文字編輯模式"""
        # 這裡可以實作內嵌文字編輯，目前使用對話框
        dialog = NodePropertiesDialog(self, self.editor)
        if dialog.exec_() == dialog.Accepted:
            self.update()

    def paint(self, painter, option, widget=None) -> None:  # type: ignore[override]
        """自訂繪製以顯示文字"""
        super().paint(painter, option, widget)

        # 設定字型
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        # 繪製文字，支援多行
        rect = self.rect()
        painter.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)

        # 如果被選取，繪製選取框
        if self.isSelected():
            painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
            painter.drawRect(rect)

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionChange:
            # 對齊網格（如果啟用）
            if hasattr(self.editor, 'view') and self.editor.view.snapToGrid:
                snapped_pos = self.editor.view.snapPointToGrid(value)  # type: ignore
                value = snapped_pos

            # 更新連接的邊
            for edge in self.edges:
                edge.updatePath()
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

        # 設定顯著的黃色連線
        self.normalPen = QPen(QColor(255, 215, 0), 4)  # 金黃色，粗線
        self.hoverPen = QPen(QColor(255, 140, 0), 5)   # 橙色，更粗
        self.selectedPen = QPen(QColor(255, 0, 0), 5)  # 紅色，選中時
        self.tempPen = QPen(QColor(128, 128, 128), 3, Qt.DashLine)  # 灰色虛線，臨時連線

        self.setPen(self.normalPen)
        self.setZValue(1)  # 確保在節點上方
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 建立箭頭的多邊形
        self.arrowHead = QGraphicsPathItem()
        self.arrowHead.setBrush(QBrush(QColor(255, 215, 0)))
        self.arrowHead.setPen(QPen(QColor(255, 215, 0), 1))
        self.arrowHead.setZValue(2)

        self.updatePath()

    def setTemporary(self, temporary: bool) -> None:
        """設定是否為臨時連線 - yEd 風格視覺回饋"""
        self.isTemporary = temporary
        if temporary:
            # 臨時連線使用更明顯的橙色實線
            self.tempPen = QPen(QColor(255, 140, 0), 3, Qt.SolidLine)
            self.setPen(self.tempPen)
            if hasattr(self, 'arrowHead'):
                self.arrowHead.setBrush(QBrush(QColor(255, 140, 0)))
                self.arrowHead.setPen(QPen(QColor(255, 140, 0), 1))
        else:
            self.setPen(self.normalPen)
            if hasattr(self, 'arrowHead'):
                self.arrowHead.setBrush(QBrush(QColor(255, 215, 0)))
                self.arrowHead.setPen(QPen(QColor(255, 215, 0), 1))

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
            if hasattr(self, 'arrowHead'):
                self.arrowHead.setBrush(QBrush(QColor(255, 140, 0)))
                self.arrowHead.setPen(QPen(QColor(255, 140, 0), 1))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        """滑鼠懸停離開"""
        if not self.isTemporary:
            if self.isSelected():
                self.setPen(self.selectedPen)
                if hasattr(self, 'arrowHead'):
                    self.arrowHead.setBrush(QBrush(QColor(255, 0, 0)))
                    self.arrowHead.setPen(QPen(QColor(255, 0, 0), 1))
            else:
                self.setPen(self.normalPen)
                if hasattr(self, 'arrowHead'):
                    self.arrowHead.setBrush(QBrush(QColor(255, 215, 0)))
                    self.arrowHead.setPen(QPen(QColor(255, 215, 0), 1))
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """項目變化處理"""
        if change == QGraphicsItem.ItemSelectedChange and not self.isTemporary:
            if value:  # 選中
                self.setPen(self.selectedPen)
                if hasattr(self, 'arrowHead'):
                    self.arrowHead.setBrush(QBrush(QColor(255, 0, 0)))
                    self.arrowHead.setPen(QPen(QColor(255, 0, 0), 1))
            else:  # 取消選中
                self.setPen(self.normalPen)
                if hasattr(self, 'arrowHead'):
                    self.arrowHead.setBrush(QBrush(QColor(255, 215, 0)))
                    self.arrowHead.setPen(QPen(QColor(255, 215, 0), 1))
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

        # 如果箭頭還沒加入場景
        if not self.arrowHead.scene() and self.scene():
            self.scene().addItem(self.arrowHead)

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

    def __init__(self, editor: DsmEditor) -> None:
        super().__init__()
        self.editor = editor
        self.connectionMode = False
        self.sourceNode = None
        self.tempEdge = None

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())

            # yEd 風格：點擊節點開始連線
            if isinstance(item, TaskNode):
                if not self.connectionMode:
                    # 開始連線模式
                    self.startConnectionMode(item)
                    return
                else:
                    # 完成連線
                    self.finishConnection(item)
                    return

            # 點擊空白區域取消連線模式
            if self.connectionMode:
                self.cancelConnectionMode()
                return

        # 右鍵取消連線模式
        if event.button() == Qt.RightButton and self.connectionMode:
            self.cancelConnectionMode()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.connectionMode and self.tempEdge:
            # 更新臨時連線的終點
            self.updateTempConnection(event.scenePos())
        else:
            super().mouseMoveEvent(event)

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
        """取消連線模式 - 清理所有狀態"""
        self.connectionMode = False

        # 移除臨時連線
        if self.tempEdge:
            self.removeItem(self.tempEdge)
            if hasattr(self.tempEdge, 'arrowHead') and self.tempEdge.arrowHead.scene():
                self.removeItem(self.tempEdge.arrowHead)
            self.tempEdge = None

        # 清理源節點狀態
        if self.sourceNode:
            self.sourceNode.isConnecting = False
            self.sourceNode.updateVisualState()
            self.sourceNode = None

        # 清理所有節點的臨時高亮狀態
        for item in self.items():
            if isinstance(item, TaskNode) and hasattr(item, '_wasHovered'):
                item.isHovered = item._wasHovered
                item.updateVisualState()
                delattr(item, '_wasHovered')

        # 恢復游標
        for view in self.views():
            view.setCursor(Qt.ArrowCursor)


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
        # 為每個屬性分配顏色
        colors: Dict[str, QColor] = {}
        for i, prop in enumerate(properties):
            hue = (i * 60) % 360
            colors[prop] = QColor.fromHsv(hue, 160, 200)

        # 預設顏色
        colors[""] = QColor("lightgray")
        colors["Default"] = QColor("lightblue")

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
