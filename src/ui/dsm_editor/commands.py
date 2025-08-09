from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from PyQt5.QtCore import QPointF, QRectF

if TYPE_CHECKING:
    from .main_editor import DsmEditor
    from .nodes import TaskNode
    from .edges import EdgeItem


class Command:
    """命令模式基類，用於撤銷/重做功能"""
    def execute(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError


class AddNodeCommand(Command):
    """新增節點命令"""
    def __init__(self, editor: DsmEditor, node: TaskNode):
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
    def __init__(self, editor: DsmEditor, src: TaskNode, dst: TaskNode):
        self.editor = editor
        self.src = src
        self.dst = dst
        self.edge: Optional[EdgeItem] = None

    def execute(self) -> None:
        if (self.src.taskId, self.dst.taskId) not in self.editor.edges:
            from .edges import EdgeItem
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
    def __init__(self, node: TaskNode, old_pos: QPointF, new_pos: QPointF):
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
    def __init__(self, node: TaskNode, old_rect: QRectF, new_rect: QRectF):
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