from __future__ import annotations

import math
from typing import Dict, Set

import pandas as pd
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath
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
)


class CanvasView(QGraphicsView):
    """提供縮放與平移功能的畫布視圖"""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self._panning = False
        self._panStart = QPointF()

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
    """代表任務節點的圖形物件"""

    WIDTH = 120
    HEIGHT = 60

    def __init__(self, taskId: str, text: str, color: QColor) -> None:
        super().__init__(-TaskNode.WIDTH / 2, -TaskNode.HEIGHT / 2, TaskNode.WIDTH, TaskNode.HEIGHT)
        self.taskId = taskId
        self.text = text
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.black))
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.edges: list[EdgeItem] = []

    def paint(self, painter, option, widget=None) -> None:  # type: ignore[override]
        """自訂繪製以顯示文字"""
        super().paint(painter, option, widget)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionChange:
            for edge in self.edges:
                edge.updatePath()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    """代表依賴關係的箭頭連線"""

    def __init__(self, src: TaskNode, dst: TaskNode) -> None:
        super().__init__()
        self.src = src
        self.dst = dst
        self.setZValue(-1)
        self.setPen(QPen(Qt.black, 2))
        self.updatePath()

    def updatePath(self) -> None:
        """更新箭頭路徑以跟隨節點移動"""
        srcPos = self.src.sceneBoundingRect().center()
        dstPos = self.dst.sceneBoundingRect().center()
        path = QPainterPath(srcPos)
        path.lineTo(dstPos)
        # 箭頭
        lineAngle = math.atan2(dstPos.y() - srcPos.y(), dstPos.x() - srcPos.x())
        arrowSize = 10
        p1 = dstPos + QPointF(
            -arrowSize * math.cos(lineAngle - math.pi / 6),
            -arrowSize * math.sin(lineAngle - math.pi / 6),
        )
        p2 = dstPos + QPointF(
            -arrowSize * math.cos(lineAngle + math.pi / 6),
            -arrowSize * math.sin(lineAngle + math.pi / 6),
        )
        path.moveTo(p1)
        path.lineTo(dstPos)
        path.lineTo(p2)
        self.setPath(path)


class DsmScene(QGraphicsScene):
    """支援連線操作的場景"""

    def __init__(self, editor: DsmEditor) -> None:
        super().__init__()
        self.editor = editor

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        if isinstance(item, TaskNode) and event.button() == Qt.LeftButton:
            self.editor.startConnection(item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.editor.isConnecting:
            self.editor.updateConnection(event.scenePos())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self.editor.isConnecting and event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            self.editor.finishConnection(item)
        else:
            super().mouseReleaseEvent(event)


class DsmEditor(QDialog):
    """視覺化 DSM 編輯器"""

    def __init__(self, wbsDf: pd.DataFrame, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("依賴關係編輯器")
        self.scene = DsmScene(self)
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.view = CanvasView(self.scene)
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)

        buttonLayout = QHBoxLayout()
        exportBtn = QPushButton("匯出 DSM")
        exportBtn.clicked.connect(self.exportDsm)
        buttonLayout.addWidget(exportBtn)
        layout.addLayout(buttonLayout)

        self.nodes: Dict[str, TaskNode] = {}
        self.edges: Set[tuple[str, str]] = set()
        self.tempLine: EdgeItem | None = None
        self.isConnecting = False
        self.srcNode: TaskNode | None = None

        self.loadWbs(wbsDf)

    def loadWbs(self, wbsDf: pd.DataFrame) -> None:
        """依據 WBS 自動建立任務節點"""
        properties = list(dict.fromkeys(wbsDf.get("Property", pd.Series(dtype=str)).tolist()))
        colors: Dict[str, QColor] = {}
        for i, prop in enumerate(properties):
            hue = (i * 60) % 360
            colors[prop] = QColor.fromHsv(hue, 160, 200)
        cols = 5
        for i, row in wbsDf.iterrows():
            taskId = row.get("Task ID")
            name = row.get("Name", "")
            prop = row.get("Property", "")
            text = f"[{prop}] {name}"
            node = TaskNode(taskId, text, colors.get(prop, QColor("lightgray")))
            node.setPos((i % cols) * 150, (i // cols) * 120)
            self.scene.addItem(node)
            self.nodes[str(taskId)] = node

    def startConnection(self, node: TaskNode) -> None:
        """開始連線操作"""
        self.isConnecting = True
        self.srcNode = node
        self.tempLine = QGraphicsPathItem()
        self.tempLine.setPen(QPen(Qt.gray, 1, Qt.DashLine))
        self.scene.addItem(self.tempLine)
        self.updateConnection(self.srcNode.sceneBoundingRect().center())

    def updateConnection(self, pos: QPointF) -> None:
        """更新連線暫存線段"""
        if self.tempLine and self.srcNode:
            path = QPainterPath(self.srcNode.sceneBoundingRect().center())
            path.lineTo(pos)
            self.tempLine.setPath(path)

    def finishConnection(self, item) -> None:
        """完成連線並建立依賴關係"""
        if not self.isConnecting or not self.srcNode:
            return
        self.isConnecting = False
        if self.tempLine:
            self.scene.removeItem(self.tempLine)
        self.tempLine = None
        self.tempLine = None
        if isinstance(item, TaskNode) and item != self.srcNode:
            self.addDependency(self.srcNode, item)
        if self.srcNode:
            self.srcNode = None

    def addDependency(self, src: TaskNode, dst: TaskNode) -> None:
        """新增依賴關係並繪製箭頭"""
        edge = EdgeItem(src, dst)
        self.scene.addItem(edge)
        src.edges.append(edge)
        dst.edges.append(edge)
        self.edges.add((src.taskId, dst.taskId))

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
