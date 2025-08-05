from __future__ import annotations

"""視覺化 DSM 編輯器核心類別"""

import math
from typing import Dict, Set, Tuple

import pandas as pd
from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QRectF, QLineF
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QTransform
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QGraphicsLineItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsItem,
    QStyle,
    QStyleOptionGraphicsItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class TaskNode(QGraphicsObject):
    """代表任務節點的圖形物件"""

    def __init__(self, taskId: str, name: str, width: float = 80, height: float = 40) -> None:
        """建立節點

        Args:
            taskId: 任務 ID。
            name: 任務名稱。
            width: 節點寬度。
            height: 節點高度。
        """
        super().__init__()
        self.taskId = taskId
        self.name = name
        self.rect = QRectF(-width / 2, -height / 2, width, height)
        self.edges: list[EdgeItem] = []
        self._highlight = False

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        """回傳節點邊界"""
        return self.rect

    def addEdge(self, edge: "EdgeItem") -> None:
        """登記與此節點相連的邊"""
        if edge not in self.edges:
            self.edges.append(edge)

    def setHighlight(self, enabled: bool) -> None:
        """設定是否高亮顯示"""
        if self._highlight != enabled:
            self._highlight = enabled
            self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:  # type: ignore[override]
        """繪製節點外觀"""
        opt = QStyleOptionGraphicsItem(option)
        if opt.state & QStyle.State_Selected:
            opt.state &= ~QStyle.State_Selected
        painter.setBrush(QColor("#E0E0E0"))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRoundedRect(self.rect, 5, 5)
        painter.drawText(self.rect, Qt.AlignCenter, self.name)
        if self.isSelected():
            painter.setPen(QPen(QColor("#0078D7"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect.adjusted(1, 1, -1, -1), 5, 5)
        if self._highlight:
            painter.setPen(QPen(QColor("#2ECC71"), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect, 5, 5)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """支援 SHIFT/CTRL 多選"""
        if event.modifiers() & Qt.ShiftModifier:
            event.setModifiers(event.modifiers() | Qt.ControlModifier)
        super().mousePressEvent(event)

    def itemChange(self, change, value):  # type: ignore[override]
        """節點移動時更新相連的邊"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.updatePath()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    """代表依賴關係的箭線"""

    def __init__(self, src: TaskNode, dst: TaskNode) -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.setPen(QPen(Qt.black, 2))
        self.setZValue(-1)
        self.src.addEdge(self)
        self.dst.addEdge(self)
        self.updatePath()

    def updatePath(self) -> None:
        """根據節點位置更新路徑並繪製箭頭"""
        source = self.src.scenePos() + self.src.boundingRect().center()
        dest = self.dst.scenePos() + self.dst.boundingRect().center()
        path = QPainterPath(source)
        path.lineTo(dest)
        line = QLineF(source, dest)
        angle = math.atan2(-line.dy(), line.dx())
        arrow = [
            dest,
            dest + QPointF(
                math.sin(angle - math.pi / 3) * 10,
                math.cos(angle - math.pi / 3) * 10,
            ),
            dest + QPointF(
                math.sin(angle - math.pi + math.pi / 3) * 10,
                math.cos(angle - math.pi + math.pi / 3) * 10,
            ),
        ]
        path.moveTo(arrow[1])
        path.lineTo(arrow[0])
        path.lineTo(arrow[2])
        self.setPath(path)


class DsmScene(QGraphicsScene):
    """處理邊創建的場景"""

    edge_created = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._mode = "idle"
        self._source: TaskNode | None = None
        self._preview: QGraphicsLineItem | None = None
        self._last_target: TaskNode | None = None

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        item = self.itemAt(event.scenePos(), QTransform())
        if event.button() == Qt.LeftButton and isinstance(item, TaskNode):
            self._mode = "drag"
            self._source = item
            start = item.scenePos() + item.boundingRect().center()
            self._preview = QGraphicsLineItem(QLineF(start, start))
            self._preview.setPen(QPen(Qt.black, 1, Qt.DashLine))
            self.addItem(self._preview)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._mode == "drag" and self._preview and self._source:
            line = QLineF(
                self._source.scenePos() + self._source.boundingRect().center(),
                event.scenePos(),
            )
            self._preview.setLine(line)
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, TaskNode) and item is not self._source:
                if self._last_target and self._last_target is not item:
                    self._last_target.setHighlight(False)
                item.setHighlight(True)
                self._last_target = item
            else:
                if self._last_target:
                    self._last_target.setHighlight(False)
                    self._last_target = None
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._mode == "drag":
            target = self.itemAt(event.scenePos(), QTransform())
            if isinstance(target, TaskNode) and target is not self._source:
                self.edge_created.emit(self._source.taskId, target.taskId)
            if self._last_target:
                self._last_target.setHighlight(False)
                self._last_target = None
            if self._preview:
                self.removeItem(self._preview)
                self._preview = None
            self._source = None
            self._mode = "idle"
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class DsmEditor(QDialog):
    """DSM 視覺化編輯器"""

    def __init__(self, wbs: pd.DataFrame, parent=None) -> None:
        """建立對話框並初始化節點

        Args:
            wbs: WBS 資料表。
            parent: 父物件。
        """
        super().__init__(parent)
        self.setWindowTitle("依賴關係編輯器")
        self.scene = DsmScene()
        self.view = QGraphicsView(self.scene)
        self.scene.edge_created.connect(self.onEdgeCreated)
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        export_btn = QPushButton("匯出 DSM")
        export_btn.clicked.connect(self.exportDsm)
        layout.addWidget(export_btn)

        self.nodes: Dict[str, TaskNode] = {}
        self.edges: Set[Tuple[str, str]] = set()

        for i, (_, row) in enumerate(wbs.iterrows()):
            node = TaskNode(row["Task ID"], str(row.get("Name", "")))
            node.setPos(i * 100, 0)
            self.scene.addItem(node)
            self.nodes[row["Task ID"]] = node

    def onEdgeCreated(self, src_id: str, dst_id: str) -> None:
        """場景通知建立邊時的處理"""
        src = self.nodes[src_id]
        dst = self.nodes[dst_id]
        edge = EdgeItem(src, dst)
        self.scene.addItem(edge)
        self.edges.add((src_id, dst_id))

    def addDependencyById(self, srcId: str, dstId: str) -> None:
        """以任務 ID 新增依賴關係（供測試使用）"""
        if srcId in self.nodes and dstId in self.nodes:
            self.onEdgeCreated(srcId, dstId)

    def buildDsmMatrix(self) -> pd.DataFrame:
        """生成 DSM 矩陣"""
        ids = list(self.nodes.keys())
        matrix = pd.DataFrame(0, index=ids, columns=ids, dtype=int)
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
