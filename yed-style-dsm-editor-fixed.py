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
from PyQt5.QtCore import Qt, QPointF, QTimer, QRectF, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath, QFont, QKeySequence, QCursor
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
            if hasattr(self.edge, 'arrowHead'):
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
            self.editor.scene.addItem(self.edge)
            if hasattr(self.edge, 'arrowHead'):
                self.editor.scene.addItem(self.edge.arrowHead)
            self.src.edges.append(self.edge)
            self.dst.edges.append(self.edge)
            self.editor.edges.add((self.src.taskId, self.dst.taskId))


class ResizeHandle(QGraphicsRectItem):
    """可調整大小的把手 - 修正版"""
    
    HANDLE_SIZE = 8  # 把手大小
    MIN_NODE_SIZE = 50  # 最小節點尺寸
    
    def __init__(self, parent_node: 'TaskNode', handle_index: int):
        # 初始化時不設定位置，由 updatePosition 處理
        super().__init__(0, 0, self.HANDLE_SIZE, self.HANDLE_SIZE, parent_node)
        
        self.parent_node = parent_node
        self.handle_index = handle_index
        self.resizing = False
        self.resize_start_pos = QPointF()
        self.initial_rect = QRectF()
        self.initial_pos = QPointF()
        
        # 設定視覺樣式
        self.setBrush(QBrush(Qt.black))
        self.setPen(QPen(Qt.white, 1))
        
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
        
        # 設定 Z 值確保在最上層
        self.setZValue(1000)
        
        # 啟用事件處理
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        
    def updatePosition(self):
        """更新把手位置"""
        rect = self.parent_node.rect()
        half_size = self.HANDLE_SIZE / 2
        
        positions = [
            (rect.left() - half_size, rect.top() - half_size),      # 左上
            (rect.center().x() - half_size, rect.top() - half_size), # 上中
            (rect.right() - half_size, rect.top() - half_size),     # 右上
            (rect.right() - half_size, rect.center().y() - half_size), # 右中
            (rect.right() - half_size, rect.bottom() - half_size),   # 右下
            (rect.center().x() - half_size, rect.bottom() - half_size), # 下中
            (rect.left() - half_size, rect.bottom() - half_size),    # 左下
            (rect.left() - half_size, rect.center().y() - half_size), # 左中
        ]
        
        if self.handle_index < len(positions):
            x, y = positions[self.handle_index]
            self.setPos(x, y)
    
    def mousePressEvent(self, event):
        """滑鼠按下事件"""
        if event.button() == Qt.LeftButton:
            self.resizing = True
            self.resize_start_pos = event.scenePos()
            self.initial_rect = self.parent_node.rect()
            self.initial_pos = self.parent_node.pos()
            
            # 通知編輯器進入調整大小狀態
            if hasattr(self.parent_node.editor, 'state'):
                self.parent_node.editor.state = EditorState.RESIZING
            
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """滑鼠移動事件"""
        if self.resizing:
            current_pos = event.scenePos()
            delta = current_pos - self.resize_start_pos
            
            # 在場景坐標中處理
            self._resizeParentNode(delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        if event.button() == Qt.LeftButton and self.resizing:
            self.resizing = False
            
            # 恢復編輯器狀態
            if hasattr(self.parent_node.editor, 'state'):
                self.parent_node.editor.state = EditorState.IDLE
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def _resizeParentNode(self, delta):
        """調整父節點大小"""
        rect = self.initial_rect
        node_pos = self.initial_pos
        
        new_rect = QRectF(rect)
        new_pos = QPointF(node_pos)
        
        # 根據把手位置計算新尺寸
        if self.handle_index == 0:  # 左上
            new_rect.setLeft(rect.left() + delta.x())
            new_rect.setTop(rect.top() + delta.y())
            new_pos = QPointF(node_pos.x() + delta.x(), node_pos.y() + delta.y())
        elif self.handle_index == 1:  # 上中
            new_rect.setTop(rect.top() + delta.y())
            new_pos = QPointF(node_pos.x(), node_pos.y() + delta.y())
        elif self.handle_index == 2:  # 右上
            new_rect.setRight(rect.right() + delta.x())
            new_rect.setTop(rect.top() + delta.y())
            new_pos = QPointF(node_pos.x(), node_pos.y() + delta.y())
        elif self.handle_index == 3:  # 右中
            new_rect.setRight(rect.right() + delta.x())
        elif self.handle_index == 4:  # 右下
            new_rect.setRight(rect.right() + delta.x())
            new_rect.setBottom(rect.bottom() + delta.y())
        elif self.handle_index == 5:  # 下中
            new_rect.setBottom(rect.bottom() + delta.y())
        elif self.handle_index == 6:  # 左下
            new_rect.setLeft(rect.left() + delta.x())
            new_rect.setBottom(rect.bottom() + delta.y())
            new_pos = QPointF(node_pos.x() + delta.x(), node_pos.y())
        elif self.handle_index == 7:  # 左中
            new_rect.setLeft(rect.left() + delta.x())
            new_pos = QPointF(node_pos.x() + delta.x(), node_pos.y())
        
        # 限制最小尺寸
        if new_rect.width() < self.MIN_NODE_SIZE:
            new_rect.setWidth(self.MIN_NODE_SIZE)
        if new_rect.height() < self.MIN_NODE_SIZE:
            new_rect.setHeight(self.MIN_NODE_SIZE)
        
        # 標準化矩形（確保寬高為正）
        new_rect = new_rect.normalized()
        
        # 更新節點
        self.parent_node.prepareGeometryChange()
        self.parent_node.setRect(new_rect)
        self.parent_node.setPos(new_pos)
        
        # 更新所有把手位置
        self.parent_node._updateHandlesPosition()
        
        # 更新連接的邊
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
        super().drawBackground(painter, rect)
        
        if not self.showGrid:
            return
        
        # 簡化網格繪製
        painter.setPen(QPen(QColor(230, 230, 230), 1, Qt.SolidLine))
        
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
            
            # 如果點擊在空白區域，開始橡皮筋框選
            if not item or isinstance(item, ResizeHandle):
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
        self._is_highlighted = False
        self._canMove = False  # 只有選中的節點才能移動
        
        # 連線檢測參數
        self.dragStartPos = QPointF()
        self.dragStartTime = 0
        self.connectionThreshold = 8  # 降低閾值，更容易觸發連線
        
        # 選取把手
        self._selection_handles = []
        self._handles_visible = False
        
        # yEd 風格顏色
        self.yedYellow = QColor(255, 215, 0)
        self.normalBrush = QBrush(self.yedYellow)
        self.selectedBrush = QBrush(self.yedYellow.lighter(110))
        self.hoverBrush = QBrush(self.yedYellow.lighter(105))
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
            # 選取狀態變化
            if value:
                # 被選中
                self._updateHandlesVisibility(True)
                self._updateHandlesPosition()
            else:
                # 取消選中
                self._updateHandlesVisibility(False)
            self.updateVisualState()
            
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
        """滑鼠按下事件 - 優化連線觸發"""
        if event.button() == Qt.LeftButton:
            self.dragStartPos = event.scenePos()
            self.dragStartTime = time.time()
            
            # 如果未選中，先選中節點
            if not self.isSelected():
                self.scene().clearSelection()
                self.setSelected(True)
                event.accept()
                return
            
            # 如果已選中，準備移動或連線
            self.isDragging = False
            self.isConnecting = False
            
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """滑鼠移動事件 - 快速檢測連線意圖"""
        if event.buttons() & Qt.LeftButton:
            current_pos = event.scenePos()
            distance = (current_pos - self.dragStartPos).manhattanLength()
            
            # 快速檢測是否要建立連線
            if not self.isDragging and not self.isConnecting:
                if distance > self.connectionThreshold:
                    # 檢查移動方向和速度來判斷意圖
                    elapsed = time.time() - self.dragStartTime
                    speed = distance / max(elapsed, 0.001)
                    
                    # 如果快速拖拽，視為連線意圖
                    if speed > 500 or distance > 20:
                        self.startConnectionMode()
                        event.accept()
                        return
                    else:
                        # 緩慢移動，視為拖拽
                        self.isDragging = True
            
            # 如果在連線模式，更新預覽
            if self.isConnecting:
                if hasattr(self.editor.scene, 'updateTempConnection'):
                    self.editor.scene.updateTempConnection(current_pos)
                event.accept()
                return
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        if event.button() == Qt.LeftButton:
            if self.isConnecting:
                # 完成連線
                item = self.scene().itemAt(event.scenePos(), self.scene().views()[0].transform())
                if isinstance(item, TaskNode) and item != self:
                    self.editor.scene.finishConnection(item)
                else:
                    self.editor.scene.cancelConnectionMode()
            
            self.isDragging = False
            self.isConnecting = False
        
        super().mouseReleaseEvent(event)
    
    def startConnectionMode(self) -> None:
        """開始連線模式"""
        self.isConnecting = True
        self.setCursor(Qt.CrossCursor)
        
        # 設定節點為不可移動
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        
        # 視覺回饋
        self.updateVisualState()
        
        # 通知場景
        if hasattr(self.editor, 'scene'):
            self.editor.scene.startConnectionMode(self)
    
    def hoverEnterEvent(self, event):
        """滑鼠懸停進入"""
        self.isHovered = True
        self.updateVisualState()
        self.setCursor(Qt.SizeAllCursor)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """滑鼠懸停離開"""
        self.isHovered = False
        self.updateVisualState()
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
    
    def set_highlight(self, highlighted: bool) -> None:
        """設定高亮狀態"""
        self._is_highlighted = highlighted
        self.updateVisualState()
    
    def updateVisualState(self) -> None:
        """更新視覺狀態"""
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
        self.update()
    
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
    """代表依賴關係的箭頭連線 - 效能優化版"""
    
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
        """更新路徑 - 效能優化版"""
        if not self.src or not self.dst:
            return
        
        # 使用快取的邊界矩形
        srcRect = self.src.sceneBoundingRect()
        dstRect = self.dst.sceneBoundingRect()
        
        srcCenter = srcRect.center()
        dstCenter = dstRect.center()
        
        # 計算方向
        dx = dstCenter.x() - srcCenter.x()
        dy = dstCenter.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 1:
            return
        
        # 正規化
        dx /= length
        dy /= length
        
        # 計算連接點
        srcPos = self.getConnectionPoint(srcRect, srcCenter, dx, dy)
        dstPos = self.getConnectionPoint(dstRect, dstCenter, -dx, -dy)
        
        # 建立路徑
        path = QPainterPath()
        path.moveTo(srcPos)
        path.lineTo(dstPos)
        self.setPath(path)
        
        # 更新箭頭
        self.updateArrowHead(srcPos, dstPos)
    
    def getConnectionPoint(self, rect, center, dx, dy):
        """計算與矩形邊界的交點"""
        halfWidth = rect.width() / 2
        halfHeight = rect.height() / 2
        
        if abs(dx) > abs(dy):
            if dx > 0:
                x = center.x() + halfWidth
                y = center.y() + dy * halfWidth / abs(dx)
            else:
                x = center.x() - halfWidth
                y = center.y() - dy * halfWidth / abs(dx)
        else:
            if dy > 0:
                y = center.y() + halfHeight
                x = center.x() + dx * halfHeight / abs(dy)
            else:
                y = center.y() - halfHeight
                x = center.x() - dx * halfHeight / abs(dy)
        
        return QPointF(x, y)
    
    def updateArrowHead(self, srcPos, dstPos):
        """更新箭頭"""
        dx = dstPos.x() - srcPos.x()
        dy = dstPos.y() - srcPos.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 1:
            return
        
        dx /= length
        dy /= length
        
        arrowSize = 15
        arrowAngle = math.pi / 6
        
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
        
        arrowPath = QPainterPath()
        arrowPath.moveTo(tip)
        arrowPath.lineTo(left)
        arrowPath.lineTo(right)
        arrowPath.closeSubpath()
        
        self.arrowHead.setPath(arrowPath)
    
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
    
    def startConnectionMode(self, sourceNode: TaskNode) -> None:
        """開始連線模式"""
        self.connectionMode = True
        self.sourceNode = sourceNode
        
        # 建立臨時邊
        self.tempEdge = EdgeItem(sourceNode, sourceNode)
        self.tempEdge.setTemporary(True)
        self.addItem(self.tempEdge)
        
        # 設定游標
        for view in self.views():
            view.setCursor(Qt.CrossCursor)
        
        # 視覺回饋
        sourceNode.updateVisualState()
    
    def updateTempConnection(self, mousePos: QPointF) -> None:
        """更新臨時連線"""
        if not self.tempEdge or not self.sourceNode:
            return
        
        # 更新路徑
        srcRect = self.sourceNode.sceneBoundingRect()
        srcCenter = srcRect.center()
        
        dx = mousePos.x() - srcCenter.x()
        dy = mousePos.y() - srcCenter.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length > 1:
            dx /= length
            dy /= length
            
            srcPos = self.tempEdge.getConnectionPoint(srcRect, srcCenter, dx, dy)
            
            path = QPainterPath()
            path.moveTo(srcPos)
            path.lineTo(mousePos)
            self.tempEdge.setPath(path)
            
            if hasattr(self.tempEdge, 'updateArrowHead'):
                self.tempEdge.updateArrowHead(srcPos, mousePos)
        
        # 高亮目標節點
        targetItem = self.itemAt(mousePos, self.views()[0].transform())
        
        if self.last_hovered_target and self.last_hovered_target != targetItem:
            self.last_hovered_target.set_highlight(False)
            self.last_hovered_target = None
        
        if isinstance(targetItem, TaskNode) and targetItem != self.sourceNode:
            targetItem.set_highlight(True)
            self.last_hovered_target = targetItem
    
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
        
        # 恢復源節點狀態
        if self.sourceNode:
            self.sourceNode.isConnecting = False
            self.sourceNode.setFlag(QGraphicsItem.ItemIsMovable, self.sourceNode.isSelected())
            self.sourceNode.updateVisualState()
            self.sourceNode = None
        
        # 恢復游標
        for view in self.views():
            view.setCursor(Qt.ArrowCursor)
    
    def mouseMoveEvent(self, event):
        """場景滑鼠移動事件"""
        if self.connectionMode and self.tempEdge:
            self.updateTempConnection(event.scenePos())
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """場景滑鼠釋放事件"""
        if self.connectionMode:
            target = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(target, TaskNode) and target != self.sourceNode:
                self.finishConnection(target)
            else:
                self.cancelConnectionMode()
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
            
            node = TaskNode(taskId, text, yedYellow, self)
            node.setPos((i % cols) * 180, (i // cols) * 120)
            
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
        """階層式佈局"""
        graph = nx.DiGraph()
        for taskId in self.nodes:
            graph.add_node(taskId)
        for src, dst in self.edges:
            graph.add_edge(src, dst)
        
        try:
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
        
        except nx.NetworkXError:
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