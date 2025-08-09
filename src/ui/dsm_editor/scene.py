from __future__ import annotations

import math
from typing import TYPE_CHECKING, List
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainterPath
from PyQt5.QtWidgets import QGraphicsScene

if TYPE_CHECKING:
    from .main_editor import DsmEditor
    from .nodes import TaskNode

from .edges import EdgeItem


class DsmScene(QGraphicsScene):
    """支援連線操作的場景 - 優化版"""

    def __init__(self, editor: DsmEditor) -> None:
        super().__init__()
        self.editor = editor

        # 狀態管理
        self.connectionMode = False
        self.sourceNode = None
        self.tempEdge = None
        self.last_hovered_target = None

        # 多固定點連線模式
        self.fixedPoints: List[QPointF] = []  # 存儲多個固定點的列表

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

        # 動態導入以避免循環導入
        from .nodes import TaskNode
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
            from .nodes import TaskNode
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