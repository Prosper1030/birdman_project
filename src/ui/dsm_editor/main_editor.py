from __future__ import annotations

from typing import Dict, Set, List
import pandas as pd
import networkx as nx
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QKeySequence
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QMenuBar, QAction, QFileDialog,
    QMessageBox
)

from .enums import EditorState, LayoutAlgorithm
from .commands import Command, AddEdgeCommand, RemoveEdgeCommand
from .scene import DsmScene
from .view import CanvasView
from .nodes import TaskNode
from .edges import EdgeItem
from .routing import SimpleEdgeRouter
from .layouts import layout_hierarchical


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

        # 邊線路由器
        self.edge_router = SimpleEdgeRouter()

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
        """
        階層式佈局 - 使用模組化的佈局演算法。
        
        LAYOUT: moved to src/layouts/hierarchical.py
        """
        # 準備 WBS DataFrame
        task_ids = list(self.nodes.keys())
        wbs_data = []
        for task_id, node in self.nodes.items():
            wbs_data.append({
                'Task ID': task_id,
                'Name': node.text
            })
        wbs_df = pd.DataFrame(wbs_data)
        
        # 取得佈局方向（如果有設定的話）
        direction = getattr(self, 'default_layout_direction', 'TB')
        
        # 呼叫模組化的佈局函數
        positions = layout_hierarchical(
            wbs_df,
            edges=self.edges,
            direction=direction,
            layer_spacing=200,
            node_spacing=150
        )
        
        # 套用位置到節點
        for task_id, (x, y) in positions.items():
            if task_id in self.nodes:
                self.nodes[task_id].setPos(x, y)
        
        # 佈局完成後調整場景範圍並確保內容可見
        self._updateSceneRectToFitNodes(padding=300)
        self._ensureContentVisible(margin=80)

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
        """
        正交式佈局 - 使用模組化的網格佈局。
        
        LAYOUT: moved to src/layouts/hierarchical.py (_simple_grid_layout)
        """
        from .layouts import _simple_grid_layout
        
        task_ids = list(self.nodes.keys())
        
        # 使用模組化的網格佈局
        positions = _simple_grid_layout(
            task_ids,
            node_spacing=180,
            layer_spacing=120,
            direction='TB'
        )
        
        # 套用位置
        for task_id, (x, y) in positions.items():
            if task_id in self.nodes:
                self.nodes[task_id].setPos(x, y)
        
        self._updateSceneRectToFitNodes(padding=300)
        self._ensureContentVisible(margin=80)

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

            # 佈局完成後調整場景範圍並確保內容可見
            self._updateSceneRectToFitNodes(padding=300)
            self._ensureContentVisible(margin=80)

        except Exception:
            self.applyOrthogonalLayout()

    def _updateSceneRectToFitNodes(self, padding: int = 200) -> None:
        """將場景範圍擴張至涵蓋所有節點，避免節點被裁切。僅在佈局完成後呼叫。"""
        if not self.nodes:
            return

        rect = None
        for node in self.nodes.values():
            r = node.sceneBoundingRect()
            rect = r if rect is None else rect.united(r)

        if rect is None:
            return

        expanded = rect.adjusted(-padding, -padding, padding, padding)
        current = self.scene.sceneRect()
        target = current.united(expanded)
        self.scene.setSceneRect(target)

    def _ensureContentVisible(self, margin: int = 50) -> None:
        """確保目前內容在視圖中可見（不改變縮放比例）。"""
        if not self.nodes:
            return
        rect = None
        for node in self.nodes.values():
            r = node.sceneBoundingRect()
            rect = r if rect is None else rect.united(r)
        if rect is None:
            return
        try:
            self.view.ensureVisible(rect, margin, margin)
        except Exception:
            self.view.centerOn(rect.center())

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