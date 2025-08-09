from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QBrush, QPen
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem

if TYPE_CHECKING:
    from .nodes import TaskNode

from .enums import EditorState


class ResizeHandle(QGraphicsRectItem):
    """yEd 風格的調整大小把手 - 正確實現版"""

    HANDLE_SIZE = 6  # 把手視覺大小 - 符合 yEd 風格
    HANDLE_DISTANCE = 5  # 把手距離節點邊緣的固定距離
    HOVER_DETECTION_RANGE = 8  # 懸停檢測範圍（比把手稍大）
    MIN_NODE_SIZE = 50  # 最小節點尺寸

    def __init__(self, parent_node: TaskNode, handle_index: int):
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
            from .commands import ResizeNodeCommand
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