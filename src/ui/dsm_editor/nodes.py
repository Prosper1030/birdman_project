from __future__ import annotations

import time
from typing import TYPE_CHECKING, List
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QBrush, QPen, QFont
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QMenu, QInputDialog

if TYPE_CHECKING:
    from .main_editor import DsmEditor
    from .edges import EdgeItem

from .handles import ResizeHandle
from .commands import MoveNodeCommand
from ..shared.selection_styles import SelectionStyleManager


class TaskNode(QGraphicsRectItem):
    """代表任務節點的圖形物件 - 完整修正版"""

    DEFAULT_WIDTH = 120
    DEFAULT_HEIGHT = 60

    def __init__(self, taskId: str, text: str, color: QColor, editor: DsmEditor) -> None:
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

        # 基礎顏色設定：以亮黃色為主體顏色
        baseColor = QColor(255, 255, 0)

        # 基礎筆刷與畫筆定義（選取樣式將由 SelectionStyleManager 動態產生）
        self.normalBrush = QBrush(baseColor)
        self.highlightBrush = QBrush(QColor(46, 204, 113))

        self.normalPen = QPen(Qt.black, 1)
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

        # 如果仍然選中，顯示調整把手並恢復選取樣式
        if self.isSelected():
            for handle in self._selection_handles:
                handle.setVisible(True)
            self.setBrush(SelectionStyleManager.create_selection_brush(self.normalBrush, "selected"))
            self.setPen(SelectionStyleManager.create_selection_pen(self.normalPen, "selected"))
        else:
            # 未選中時恢復一般樣式
            self.setBrush(self.normalBrush)
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
            # 透過 SelectionStyleManager 產生選取樣式
            self.setBrush(SelectionStyleManager.create_selection_brush(self.normalBrush, "selected"))
            self.setPen(SelectionStyleManager.create_selection_pen(self.normalPen, "selected"))
            # 更新鼠標樣式為移動模式
            if self.isHovered:
                self.setCursor(Qt.SizeAllCursor)
            print(f"節點 '{self.taskId}' 已選中，可拖動移動")
        else:
            # 取消選中：立即隱藏把手並恢復原色
            self._updateHandlesVisibility(False)
            if self.isHovered:
                # 懸停時使用 hover 樣式
                self.setBrush(SelectionStyleManager.create_selection_brush(self.normalBrush, "hovered"))
                self.setPen(SelectionStyleManager.create_selection_pen(self.normalPen, "hovered"))
                # 恢復一般鼠標
                self.setCursor(Qt.ArrowCursor)
            else:
                # 未懸停使用一般樣式
                self.setBrush(self.normalBrush)
                self.setPen(self.normalPen)
            print(f"節點 '{self.taskId}' 取消選中")

    def updateVisualState(self) -> None:
        """更新視覺狀態 - 立即反應選取狀態變化"""
        if self._is_highlighted:
            self.setBrush(self.highlightBrush)
            self.setPen(self.highlightPen)
        elif self.isSelected():
            self.setBrush(SelectionStyleManager.create_selection_brush(self.normalBrush, "selected"))
            self.setPen(SelectionStyleManager.create_selection_pen(self.normalPen, "selected"))
        elif self.isHovered:
            self.setBrush(SelectionStyleManager.create_selection_brush(self.normalBrush, "hovered"))
            self.setPen(SelectionStyleManager.create_selection_pen(self.normalPen, "hovered"))
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