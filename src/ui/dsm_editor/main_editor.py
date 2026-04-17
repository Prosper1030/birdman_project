from __future__ import annotations

from pathlib import Path
from typing import Dict, Set, List

import pandas as pd

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenuBar,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .commands import Command, AddEdgeCommand, AddNodeCommand, RemoveEdgeCommand
from .edge_router_manager import create_yed_router_manager
from .edges import EdgeItem
from .enums import EditorState, LayoutAlgorithm
from .layouts import layout_hierarchical_with_info
from .nodes import TaskNode
from .scene import DsmScene
from .session import (
    AUTOSAVE_DIR_NAME,
    AUTOSAVE_INTERVAL_MS,
    DsmEditorSession,
    SccGroupSummary,
    buildSessionId,
    dsmEquals,
    findLatestRestorableSnapshot,
    loadSnapshotData,
    summarizeCyclicSccGroups,
    validateEditorInputs,
    writeSessionSnapshot,
)
from .view import CanvasView
from ...app_paths import projectRoot


class DsmEditor(QDialog):
    """視覺化 DSM 編輯器 - 主視窗"""

    def __init__(
        self,
        wbsDf: pd.DataFrame,
        parent=None,
        dsmDf: pd.DataFrame | None = None,
        wbsPath: str | None = None,
        dsmPath: str | None = None,
        autosaveRoot=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("依賴關係編輯器")
        self.resize(1400, 860)

        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        validatedWbs, validatedDsm = validateEditorInputs(wbsDf, dsmDf)
        autosavePath = autosaveRoot if autosaveRoot is not None else None
        self.session = DsmEditorSession(
            wbsDf=validatedWbs.copy(),
            dsmDf=validatedDsm.copy(),
            baselineDsmDf=validatedDsm.copy(),
            wbsPath=wbsPath,
            dsmPath=dsmPath,
            autosaveRoot=(
                Path(autosavePath)
                if autosavePath
                else projectRoot / AUTOSAVE_DIR_NAME
            ),
            sessionId=buildSessionId(
                wbsPath,
                dsmPath,
                validatedWbs["Task ID"].astype(str).tolist(),
            ),
        )

        self.state = EditorState.IDLE
        self.commandHistory: List[Command] = []
        self.commandIndex = -1

        self.nodes: Dict[str, TaskNode] = {}
        self.edges: Set[tuple[str, str]] = set()
        self.edge_ports: Dict[tuple[str, str], tuple] = {}
        self.layout_direction = "TB"
        self.layer_spacing = 200
        self.node_spacing = 150
        self.isolated_spacing = 100
        self.routing_enabled = False
        self.edge_router_manager = None
        self.current_edge_ports = {}
        self.highlightedSccTaskIds: set[str] = set()
        self.noticeText = "已載入編輯器。"
        self.graph = None
        self.autosaveTimer = QTimer(self)
        self.autosaveTimer.setSingleShot(True)
        self.autosaveTimer.setInterval(AUTOSAVE_INTERVAL_MS)
        self.autosaveTimer.timeout.connect(self._autosaveIfNeeded)

        self.setupUI()
        self._restoreLatestSnapshotIfNeeded()
        self.loadWbs(self.session.wbsDf)
        self.loadDsm(self.session.dsmDf)
        self._syncSessionState()
        if self.session.wbsDf.empty:
            self._setNotice("目前為空白依賴圖，可用「新增任務」開始建立。")
        elif not self.noticeText or self.noticeText == "已載入編輯器。":
            self._setNotice("已完成資料載入。")

    def setupUI(self) -> None:
        """設定使用者介面"""
        rootLayout = QVBoxLayout(self)

        menuBar = QMenuBar(self)
        rootLayout.setMenuBar(menuBar)

        fileMenu = menuBar.addMenu("檔案(&F)")

        saveSessionAction = QAction("儲存工作階段(&S)", self)
        saveSessionAction.setShortcut(QKeySequence.Save)
        saveSessionAction.triggered.connect(self.saveSessionSnapshot)
        fileMenu.addAction(saveSessionAction)

        exportAction = QAction("匯出 DSM(&E)...", self)
        exportAction.setShortcut(QKeySequence.SaveAs)
        exportAction.triggered.connect(self.exportDsm)
        fileMenu.addAction(exportAction)

        editMenu = menuBar.addMenu("編輯(&E)")

        addNodeAction = QAction("新增任務(&N)", self)
        addNodeAction.setShortcut(QKeySequence.New)
        addNodeAction.triggered.connect(self.promptCreateNode)
        editMenu.addAction(addNodeAction)

        editMenu.addSeparator()

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

        layoutMenu = menuBar.addMenu("佈局(&L)")

        hierarchicalAction = QAction("階層式佈局(&H)", self)
        hierarchicalAction.triggered.connect(self.showHierarchicalLayoutDialog)
        layoutMenu.addAction(hierarchicalAction)

        orthogonalAction = QAction("正交式佈局(&O)", self)
        orthogonalAction.triggered.connect(
            lambda: self.applyLayout(LayoutAlgorithm.ORTHOGONAL)
        )
        layoutMenu.addAction(orthogonalAction)

        forceAction = QAction("力導向佈局(&F)", self)
        forceAction.triggered.connect(
            lambda: self.applyLayout(LayoutAlgorithm.FORCE_DIRECTED)
        )
        layoutMenu.addAction(forceAction)

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

        statusWidget = QWidget(self)
        statusLayout = QHBoxLayout(statusWidget)
        statusLayout.setContentsMargins(8, 6, 8, 6)
        statusLayout.setSpacing(12)

        self.sourceLabel = QLabel()
        self.dirtyLabel = QLabel()
        self.cycleLabel = QLabel()
        self.sccLabel = QLabel()
        self.noticeLabel = QLabel()
        self.noticeLabel.setWordWrap(True)

        for label in (
            self.sourceLabel,
            self.dirtyLabel,
            self.cycleLabel,
            self.sccLabel,
        ):
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            statusLayout.addWidget(label)

        statusLayout.addStretch()
        statusLayout.addWidget(self.noticeLabel, stretch=2)
        rootLayout.addWidget(statusWidget)

        self.scene = DsmScene(self)
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.scene.setBackgroundBrush(QBrush(QColor(255, 255, 255)))
        self.view = CanvasView(self.scene)

        self.edge_router_manager = create_yed_router_manager(self.scene)

        self.min_node_node = 30.0
        self.min_node_edge = 15.0
        self.min_edge_edge = 15.0
        self.min_layer_layer = 10.0
        self.node_width = 120
        self.node_height = 60
        self.node_margin = 8
        self.min_gap = 16

        self.sccListWidget = QListWidget(self)
        self.sccListWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sccListWidget.currentItemChanged.connect(self._handleSccSelectionChanged)

        sidebar = QWidget(self)
        sidebarLayout = QVBoxLayout(sidebar)
        sidebarLayout.setContentsMargins(0, 0, 0, 0)
        sidebarLayout.addWidget(QLabel("循環 SCC 清單"))
        self.sccHintLabel = QLabel("目前沒有循環依賴。")
        self.sccHintLabel.setWordWrap(True)
        sidebarLayout.addWidget(self.sccHintLabel)
        sidebarLayout.addWidget(self.sccListWidget, stretch=1)
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(360)

        contentLayout = QHBoxLayout()
        contentLayout.addWidget(self.view, stretch=4)
        contentLayout.addWidget(sidebar, stretch=1)
        rootLayout.addLayout(contentLayout)

    def loadWbs(self, wbsDf: pd.DataFrame) -> None:
        """載入 WBS 資料。"""
        if wbsDf.empty:
            return

        yedYellow = QColor(255, 215, 0)
        cols = 5

        for i, row in wbsDf.iterrows():
            taskId = str(row.get("Task ID", f"Task_{i}")).strip()
            taskName = str(row.get("Name", "未命名任務"))
            taskProperty = str(row.get("Property", ""))
            if taskProperty == "nan":
                taskProperty = ""

            if taskId in self.nodes:
                continue

            displayText = self._formatNodeText(taskName, taskProperty)
            node = TaskNode(
                taskId,
                displayText,
                yedYellow,
                self,
                propertyValue=taskProperty,
                name=taskName,
            )
            node.setPos((i % cols) * 180, (i // cols) * 120)

            if node.scene() != self.scene:
                self.scene.addItem(node)
            self.nodes[taskId] = node

    def loadDsm(self, dsmDf: pd.DataFrame) -> None:
        """依據 DSM 建立現有依賴邊。"""
        if dsmDf.empty:
            return

        for rowTask in dsmDf.index:
            for colTask in dsmDf.columns:
                if int(dsmDf.at[rowTask, colTask]) != 1:
                    continue
                self._addDependencyDirect(str(colTask), str(rowTask))

    def executeCommand(self, command: Command) -> None:
        """執行命令並加入歷史記錄。"""
        self.commandHistory = self.commandHistory[: self.commandIndex + 1]
        command.execute()
        self.commandHistory.append(command)
        self.commandIndex += 1
        self.updateUndoRedoState()
        self._syncSessionState()

    def undo(self) -> None:
        """撤銷。"""
        if self.commandIndex >= 0:
            self.commandHistory[self.commandIndex].undo()
            self.commandIndex -= 1
            self.updateUndoRedoState()
            self._syncSessionState()

    def redo(self) -> None:
        """重做。"""
        if self.commandIndex < len(self.commandHistory) - 1:
            self.commandIndex += 1
            self.commandHistory[self.commandIndex].execute()
            self.updateUndoRedoState()
            self._syncSessionState()

    def updateUndoRedoState(self) -> None:
        """更新撤銷/重做按鈕狀態。"""
        self.undoAction.setEnabled(self.commandIndex >= 0)
        self.redoAction.setEnabled(self.commandIndex < len(self.commandHistory) - 1)

    def toggleGrid(self) -> None:
        """切換網格顯示。"""
        self.view.setGridVisible(self.gridAction.isChecked())

    def toggleSnapToGrid(self) -> None:
        """切換網格對齊。"""
        self.view.setSnapToGrid(self.snapAction.isChecked())

    def addDependency(self, src: TaskNode, dst: TaskNode) -> None:
        """新增依賴關係。"""
        if (src.taskId, dst.taskId) not in self.edges:
            command = AddEdgeCommand(self, src, dst)
            self.executeCommand(command)

    def addDependencyById(self, srcTaskId: str, dstTaskId: str) -> None:
        """以 Task ID 新增依賴關係。"""
        srcNode = self.nodes.get(srcTaskId)
        dstNode = self.nodes.get(dstTaskId)
        if srcNode is None or dstNode is None:
            raise ValueError("找不到指定的 Task ID，無法建立依賴關係。")
        self.addDependency(srcNode, dstNode)

    def _generateNextTaskId(self) -> str:
        """產生新的預設 Task ID。"""
        index = 1
        while True:
            candidate = f"TASK-{index:03d}"
            if candidate not in self.nodes:
                return candidate
            index += 1

    def promptCreateNode(self, scenePos=None) -> None:
        """彈出對話框建立新任務節點。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("新增任務")
        rootLayout = QVBoxLayout(dialog)

        formLayout = QFormLayout()
        taskIdEdit = QLineEdit(self._generateNextTaskId(), dialog)
        nameEdit = QLineEdit("", dialog)
        propertyEdit = QLineEdit("", dialog)
        formLayout.addRow("Task ID", taskIdEdit)
        formLayout.addRow("名稱", nameEdit)
        formLayout.addRow("Property", propertyEdit)
        rootLayout.addLayout(formLayout)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=dialog,
        )
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.rejected.connect(dialog.reject)
        rootLayout.addWidget(buttonBox)

        if dialog.exec_() != QDialog.Accepted:
            return

        taskId = taskIdEdit.text().strip()
        taskName = nameEdit.text().strip() or taskId
        taskProperty = propertyEdit.text().strip()

        try:
            self.createNode(
                taskId=taskId,
                taskName=taskName,
                taskProperty=taskProperty,
                scenePos=scenePos,
            )
        except ValueError as error:
            QMessageBox.warning(self, "警告", str(error))

    def createNode(
        self,
        *,
        taskId: str,
        taskName: str,
        taskProperty: str = "",
        scenePos=None,
    ) -> TaskNode:
        """建立新的任務節點並加入畫布。"""
        normalizedTaskId = taskId.strip()
        if not normalizedTaskId:
            raise ValueError("Task ID 不可為空白。")
        if normalizedTaskId in self.nodes:
            raise ValueError(f"Task ID {normalizedTaskId} 已存在。")

        node = TaskNode(
            normalizedTaskId,
            self._formatNodeText(taskName, taskProperty),
            QColor(255, 215, 0),
            self,
            propertyValue=taskProperty,
            name=taskName,
        )

        if scenePos is None:
            index = len(self.nodes)
            node.setPos((index % 5) * 180, (index // 5) * 120)
        else:
            snapPos = self.view.snapPointToGrid(scenePos)
            node.setPos(snapPos)

        self.executeCommand(AddNodeCommand(self, node))
        self._updateSceneRectToFitNodes(padding=300)
        self._ensureContentVisible(margin=80)
        self._setNotice(f"已新增任務：{normalizedTaskId}")
        return node

    def removeEdge(self, edge: EdgeItem) -> None:
        """移除邊。"""
        command = RemoveEdgeCommand(self, edge)
        self.executeCommand(command)

    def applyLayout(self, algorithm: LayoutAlgorithm) -> None:
        """套用佈局演算法。"""
        if algorithm == LayoutAlgorithm.HIERARCHICAL:
            self.applyHierarchicalLayout()
        elif algorithm == LayoutAlgorithm.ORTHOGONAL:
            self.applyOrthogonalLayout()
        elif algorithm == LayoutAlgorithm.FORCE_DIRECTED:
            self.applyForceDirectedLayout()

    def showHierarchicalLayoutDialog(self) -> None:
        """顯示階層佈局設定對話框。"""
        from .hierarchical_layout_dialog import HierarchicalLayoutDialog

        dialog = HierarchicalLayoutDialog(self)
        if dialog.exec() == dialog.Accepted:
            settings = dialog.getSettings()

            self.layout_direction = settings["orientation"]
            self.layer_spacing = settings["layer_spacing"]
            self.node_spacing = settings["node_spacing"]
            self.isolated_spacing = settings["isolated_spacing"]
            self.min_node_node = settings["min_node_node"]
            self.min_node_edge = settings["min_node_edge"]
            self.min_edge_edge = settings["min_edge_edge"]
            self.min_layer_layer = settings["min_layer_layer"]
            self.node_width = settings["node_width"]
            self.node_height = settings["node_height"]
            self.node_margin = settings["node_margin"]
            self.min_gap = settings["min_gap"]

            self.applyHierarchicalLayout()

    def applyHierarchicalLayout(self) -> None:
        """執行階層式佈局。"""
        wbsData = []
        for taskId, node in self.nodes.items():
            wbsData.append(
                {
                    "Task ID": taskId,
                    "Name": node.taskName,
                }
            )
        wbsDf = pd.DataFrame(wbsData)

        layoutResult = layout_hierarchical_with_info(
            wbsDf,
            edges=self.edges,
            direction=self.layout_direction,
            layer_spacing=self.layer_spacing,
            node_spacing=self.node_spacing,
            isolated_spacing=self.isolated_spacing,
            min_node_node=self.min_node_node,
            min_layer_layer=self.min_layer_layer,
            min_node_edge=self.min_node_edge,
        )

        positions = layoutResult["coordinates"]
        self.edge_ports = layoutResult.get("edge_ports", {})

        for taskId, (x, y) in positions.items():
            if taskId in self.nodes:
                self.nodes[taskId].setPos(x, y)

        self._applyEdgePortsToEdges()
        self._updateSceneRectToFitNodes(padding=300)
        self._ensureContentVisible(margin=80)
        self._apply_orthogonal_routing_after_layout()
        self._updateLayoutNotice("階層式")

    def _applyEdgePortsToEdges(self) -> None:
        """將佈局引擎計算的 edge_ports 套用到場景中的邊線。"""
        if not self.edge_ports:
            return

        processedEdges = set()
        for edge in self._iterEdgeItems():
            edgeId = id(edge)
            if edgeId in processedEdges:
                continue
            processedEdges.add(edgeId)
            edgeKey = (edge.src.taskId, edge.dst.taskId)
            if edgeKey not in self.edge_ports:
                edge.updatePath()
                continue

            srcPortPos, dstPortPos = self.edge_ports[edgeKey]
            from PyQt5.QtCore import QPointF

            edge.set_complex_path(
                [QPointF(*srcPortPos), QPointF(*dstPortPos)],
                offset_pixels=0,
            )

    def setLayoutDirection(self, direction: str) -> None:
        """設定佈局方向。"""
        if direction in ["TB", "LR"]:
            self.layout_direction = direction

    def setLayoutSpacing(
        self,
        layer_spacing: int = None,
        node_spacing: int = None,
        isolated_spacing: int = None,
    ) -> None:
        """設定佈局間距參數。"""
        if layer_spacing is not None:
            self.layer_spacing = layer_spacing
        if node_spacing is not None:
            self.node_spacing = node_spacing
        if isolated_spacing is not None:
            self.isolated_spacing = isolated_spacing

    def enableOrthogonalRouting(self, enabled: bool = True) -> None:
        """啟用或禁用正交路由。"""
        self.routing_enabled = enabled
        if enabled:
            self._apply_orthogonal_routing_after_layout()
            self._updateLayoutNotice("正交路由")
        else:
            self._resetToStraightEdges()
            self._setNotice("已切換為直線邊模式。")

    def applySimpleHierarchicalLayout(self) -> None:
        """簡單階層式佈局。"""
        nodes = list(self.nodes.values())
        levelSpacing = 200
        nodeSpacing = 150
        nodesPerLevel = 4

        for i, node in enumerate(nodes):
            level = i // nodesPerLevel
            posInLevel = i % nodesPerLevel
            startX = -(nodesPerLevel - 1) * nodeSpacing / 2
            x = startX + posInLevel * nodeSpacing
            y = level * levelSpacing
            node.setPos(x, y)

    def applyOrthogonalLayout(self) -> None:
        """正交式佈局。"""
        from .layouts import layout_orthogonal

        taskIds = list(self.nodes.keys())
        if not taskIds:
            return

        wbsDf = pd.DataFrame({"Task ID": taskIds})
        direction = getattr(self, "default_layout_direction", "TB")

        positions = layout_orthogonal(
            wbsDf,
            direction=direction,
            layer_spacing=200,
            node_spacing=180,
            grid_cols=5,
        )

        for taskId, (x, y) in positions.items():
            if taskId in self.nodes:
                self.nodes[taskId].setPos(x, y)

        self._updateSceneRectToFitNodes(padding=300)
        self._ensureContentVisible(margin=80)
        self._apply_orthogonal_routing_after_layout()
        self._updateLayoutNotice("正交式")

    def applyForceDirectedLayout(self) -> None:
        """力導向佈局。"""
        from .layouts import layout_force_directed

        taskIds = list(self.nodes.keys())
        if not taskIds:
            return

        wbsDf = pd.DataFrame({"Task ID": taskIds})
        edges = set(self.edges)

        try:
            nodeCount = len(taskIds)
            iterations = min(200, max(50, nodeCount * 2))
            positions = layout_force_directed(
                wbsDf,
                edges,
                iterations=iterations,
                k_spring=2.0,
                k_repulsion=1.0,
                scale=500,
                seed=42,
            )

            for taskId, (x, y) in positions.items():
                if taskId in self.nodes:
                    self.nodes[taskId].setPos(x, y)

            self._updateSceneRectToFitNodes(padding=300)
            self._ensureContentVisible(margin=80)
            self._updateLayoutNotice("力導向")

        except Exception as error:
            print(f"力導向佈局失敗: {error}")
            self.applyOrthogonalLayout()

    def _apply_orthogonal_routing_after_layout(self) -> None:
        """佈局完成後執行正交路由。"""
        if not self.edge_router_manager or not self.edge_ports:
            return

        edgesData = []
        from PyQt5.QtCore import QPointF

        for edgeItem in self._iterEdgeItems():
            edgeKey = (edgeItem.src.taskId, edgeItem.dst.taskId)
            if edgeKey not in self.edge_ports:
                continue
            srcPortPos, dstPortPos = self.edge_ports[edgeKey]
            startPos = QPointF(*srcPortPos)
            endPos = QPointF(*dstPortPos)
            edgesData.append((edgeItem, startPos, endPos))

        if not edgesData:
            return

        try:
            self.edge_router_manager.route_all_edges_for_layout(edgesData)
        except Exception as error:
            print(f"正交路由執行失敗: {error}")

    def _updateSceneRectToFitNodes(self, padding: int = 200) -> None:
        """將場景範圍擴張至涵蓋所有節點。"""
        if not self.nodes:
            return

        rect = None
        for node in self.nodes.values():
            nodeRect = node.sceneBoundingRect()
            rect = nodeRect if rect is None else rect.united(nodeRect)

        if rect is None:
            return

        expanded = rect.adjusted(-padding, -padding, padding, padding)
        current = self.scene.sceneRect()
        self.scene.setSceneRect(current.united(expanded))

    def _ensureContentVisible(self, margin: int = 50) -> None:
        """確保目前內容在視圖中可見。"""
        if not self.nodes:
            return

        rect = None
        for node in self.nodes.values():
            nodeRect = node.sceneBoundingRect()
            rect = nodeRect if rect is None else rect.united(nodeRect)
        if rect is None:
            return

        try:
            self.view.ensureVisible(rect, margin, margin)
        except Exception:
            self.view.centerOn(rect.center())

    def buildDsmMatrix(self) -> pd.DataFrame:
        """建立 DSM 矩陣。"""
        taskIds = list(self.nodes.keys())
        matrix = pd.DataFrame(0, index=taskIds, columns=taskIds, dtype=int)
        for src, dst in self.edges:
            if src in matrix.columns and dst in matrix.index:
                matrix.loc[dst, src] = 1
        return matrix

    def buildWbsSnapshot(self) -> pd.DataFrame:
        """根據目前節點建立最新的 WBS 快照。"""
        baseWbs = self.session.wbsDf.copy()
        baseColumns = list(baseWbs.columns)
        if "Task ID" not in baseColumns:
            baseColumns.insert(0, "Task ID")
        for requiredColumn in ("Name", "Property"):
            if requiredColumn not in baseColumns:
                baseColumns.append(requiredColumn)

        existingRows: dict[str, dict] = {}
        if not baseWbs.empty and "Task ID" in baseWbs.columns:
            for _, row in baseWbs.iterrows():
                existingRows[str(row.get("Task ID", "")).strip()] = row.to_dict()

        snapshotRows = []
        for taskId, node in self.nodes.items():
            rowData = existingRows.get(taskId, {})
            rowData["Task ID"] = taskId
            rowData["Name"] = node.taskName
            rowData["Property"] = node.taskProperty
            snapshotRows.append(rowData)

        if not snapshotRows:
            return pd.DataFrame(columns=baseColumns)

        snapshotDf = pd.DataFrame(snapshotRows)
        for column in baseColumns:
            if column not in snapshotDf.columns:
                snapshotDf[column] = ""
        return snapshotDf[baseColumns].reset_index(drop=True)

    def getCurrentDsmDataFrame(self) -> pd.DataFrame:
        """回傳目前 DSM DataFrame。"""
        return self.session.dsmDf.copy()

    def getCurrentSccSummary(self) -> list[SccGroupSummary]:
        """回傳目前循環 SCC 摘要。"""
        return list(self.session.sccGroups)

    def isSessionDirty(self) -> bool:
        """回傳目前是否有未儲存變更。"""
        return self.session.dirty

    def exportDsm(self) -> None:
        """匯出 DSM。"""
        if self.session.hasCycles:
            QMessageBox.warning(
                self,
                "循環依賴提醒",
                "目前依賴圖含有循環依賴，匯出不會被阻擋，但後續 CPM 或排序分析可能受影響。",
            )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 DSM",
            "",
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            self.buildDsmMatrix().to_csv(path, encoding="utf-8-sig")
            self._setNotice(f"已匯出 DSM：{path}")
            QMessageBox.information(self, "完成", f"已匯出 DSM：{path}")
        except OSError as error:
            QMessageBox.critical(self, "錯誤", f"匯出失敗：{error}")

    def saveSessionSnapshot(self) -> None:
        """手動儲存目前工作階段快照。"""
        self._refreshSessionFrames()
        try:
            snapshot = writeSessionSnapshot(self.session, reason="manual")
        except OSError as error:
            QMessageBox.critical(self, "錯誤", f"儲存工作階段失敗：{error}")
            return

        self._setNotice(
            f"已儲存工作階段快照：{snapshot.snapshotDir}"
        )
        QMessageBox.information(
            self,
            "完成",
            f"已儲存工作階段快照：\n{snapshot.snapshotDir}",
        )

    def notifyGraphStructureChanged(self) -> None:
        """當依賴圖結構有變化時同步更新狀態。"""
        self._syncSessionState()

    def _refreshSessionFrames(self) -> None:
        """將目前畫面資料同步回工作階段。"""
        self.session.wbsDf = self.buildWbsSnapshot()
        self.session.dsmDf = self.buildDsmMatrix()

    def _syncSessionState(self) -> None:
        """同步目前的圖狀態、dirty 狀態與 SCC 摘要。"""
        self._refreshSessionFrames()
        currentDsm = self.session.dsmDf.copy()
        graph, sccGroups = summarizeCyclicSccGroups(currentDsm)

        self.graph = graph
        self.session.dsmDf = currentDsm.copy()
        self.session.hasCycles = bool(sccGroups)
        self.session.sccGroups = sccGroups
        self.session.dirty = not dsmEquals(currentDsm, self.session.baselineDsmDf)

        self._scheduleAutosaveIfNeeded()
        self._updateStatusPanel()
        self._refreshSccListWidget()

    def _updateStatusPanel(self) -> None:
        """更新狀態區資訊。"""
        self.sourceLabel.setText(self.session.sourceSummary())
        self.dirtyLabel.setText(
            f"未儲存變更：{'是' if self.session.dirty else '否'}"
        )
        if self.session.hasCycles:
            self.cycleLabel.setText("循環依賴：有")
            self.cycleLabel.setStyleSheet("color: #c0392b; font-weight: bold;")
        else:
            self.cycleLabel.setText("循環依賴：無")
            self.cycleLabel.setStyleSheet("color: #1e8449; font-weight: bold;")
        self.sccLabel.setText(f"循環 SCC 群組：{len(self.session.sccGroups)}")
        self.noticeLabel.setText(self.noticeText)

    def _refreshSccListWidget(self) -> None:
        """刷新循環 SCC 清單。"""
        previousSelection = set(self.highlightedSccTaskIds)
        self.sccListWidget.blockSignals(True)
        self.sccListWidget.clear()

        if not self.session.sccGroups:
            self.sccHintLabel.setText("目前沒有循環依賴。")
            self.sccListWidget.setEnabled(False)
            self.sccListWidget.blockSignals(False)
            self._clearSccHighlight()
            return

        self.sccHintLabel.setText("點選群組可高亮對應節點與邊線。")
        self.sccListWidget.setEnabled(True)

        matchedItem = None
        for group in self.session.sccGroups:
            item = QListWidgetItem(
                f"SCC {group.groupId}｜" + "、".join(group.taskIds)
            )
            item.setData(Qt.UserRole, list(group.taskIds))
            self.sccListWidget.addItem(item)
            if previousSelection and set(group.taskIds) == previousSelection:
                matchedItem = item

        self.sccListWidget.blockSignals(False)
        if matchedItem is not None:
            self.sccListWidget.setCurrentItem(matchedItem)
        else:
            self._clearSccHighlight()

    def _handleSccSelectionChanged(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        """當 SCC 清單改變選取時高亮相關項目。"""
        del previous
        self._clearSccHighlight()
        if current is None:
            return

        taskIds = set(current.data(Qt.UserRole) or [])
        if not taskIds:
            return

        self.highlightedSccTaskIds = taskIds
        for taskId, node in self.nodes.items():
            node.set_highlight(taskId in taskIds)

        for edge in self._iterEdgeItems():
            edge.set_highlight(
                edge.src.taskId in taskIds and edge.dst.taskId in taskIds
            )

    def _clearSccHighlight(self) -> None:
        """清除 SCC 高亮。"""
        self.highlightedSccTaskIds = set()
        for node in self.nodes.values():
            node.set_highlight(False)
        for edge in self._iterEdgeItems():
            edge.set_highlight(False)

    def _setNotice(self, message: str) -> None:
        """更新狀態提醒文字。"""
        self.noticeText = message
        self.noticeLabel.setText(message)

    def _scheduleAutosaveIfNeeded(self) -> None:
        """依目前 dirty 狀態安排自動存檔。"""
        if self.session.dirty:
            self.autosaveTimer.start()
        else:
            self.autosaveTimer.stop()

    def _autosaveIfNeeded(self) -> None:
        """在有修改時寫入自動存檔。"""
        if not self.session.dirty:
            return
        self._refreshSessionFrames()
        try:
            snapshot = writeSessionSnapshot(self.session, reason="autosave")
        except OSError as error:
            self._setNotice(f"自動存檔失敗：{error}")
            return

        self._setNotice(
            f"已自動儲存工作階段：{snapshot.savedAt}"
        )

    def _updateLayoutNotice(self, layoutName: str) -> None:
        """依目前循環狀態更新佈局提示文案。"""
        if self.session.hasCycles:
            self._setNotice(
                f"{layoutName}視覺化重排完成；目前仍存在循環依賴，系統僅更新畫面配置。"
            )
        else:
            self._setNotice(f"{layoutName}佈局完成。")

    def _addDependencyDirect(self, srcTaskId: str, dstTaskId: str) -> None:
        """直接建立依賴關係，不記錄撤銷歷史。"""
        if (srcTaskId, dstTaskId) in self.edges:
            return
        srcNode = self.nodes.get(srcTaskId)
        dstNode = self.nodes.get(dstTaskId)
        if srcNode is None or dstNode is None:
            return

        edge = EdgeItem(srcNode, dstNode)
        if edge.scene() != self.scene:
            self.scene.addItem(edge)
        if hasattr(edge, "arrowHead") and edge.arrowHead.scene() != self.scene:
            self.scene.addItem(edge.arrowHead)
        srcNode.edges.append(edge)
        dstNode.edges.append(edge)
        self.edges.add((srcTaskId, dstTaskId))

    def _iterEdgeItems(self) -> list[EdgeItem]:
        """回傳場景中的唯一邊線項目。"""
        edges: list[EdgeItem] = []
        seen = set()
        for node in self.nodes.values():
            for edge in node.edges:
                edgeId = id(edge)
                if edgeId in seen:
                    continue
                seen.add(edgeId)
                edges.append(edge)
        return edges

    def _resetToStraightEdges(self) -> None:
        """重置所有邊線為直線模式。"""
        for edgeItem in self._iterEdgeItems():
            edgeItem.updatePath()

    def _formatNodeText(self, taskName: str, taskProperty: str) -> str:
        """建立節點顯示文字。"""
        if taskProperty:
            return f"[{taskProperty}] {taskName}"
        return taskName

    def _restoreLatestSnapshotIfNeeded(self) -> None:
        """若偵測到較新的快照，提供恢復選項。"""
        snapshot = findLatestRestorableSnapshot(self.session)
        if snapshot is None:
            return

        reply = QMessageBox.question(
            self,
            "恢復工作階段",
            (
                "偵測到較新的工作階段快照。\n"
                f"時間：{snapshot.savedAt}\n\n"
                "是否恢復最近自動存檔？\n"
                "此操作不會覆寫原始 DSM 檔案。"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            restoredWbs, restoredDsm, metadata = loadSnapshotData(snapshot)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            QMessageBox.warning(self, "警告", f"恢復快照失敗：{error}")
            return

        self.session.wbsDf = restoredWbs
        self.session.dsmDf = restoredDsm
        self.session.lastAutosavePath = str(snapshot.snapshotDir)
        self.session.lastAutosaveTime = str(metadata.get("saved_at", snapshot.savedAt))
        self._setNotice(
            f"已恢復工作階段快照：{self.session.lastAutosaveTime}"
        )

    def keyPressEvent(self, event):
        """鍵盤事件處理。"""
        if event.key() == Qt.Key_Escape:
            if hasattr(self.scene, "connectionMode") and self.scene.connectionMode:
                self.scene.cancelConnectionMode()
            else:
                self.scene.clearSelection()
                self.sccListWidget.clearSelection()
                self._clearSccHighlight()
        elif event.key() == Qt.Key_Delete:
            selectedItems = self.scene.selectedItems()
            for item in selectedItems:
                if isinstance(item, TaskNode):
                    item.deleteNode()
                elif isinstance(item, EdgeItem) and not item.isTemporary:
                    self.removeEdge(item)
        elif event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            for item in self.scene.items():
                if isinstance(item, (TaskNode, EdgeItem)) and not getattr(
                    item, "isTemporary", False
                ):
                    item.setSelected(True)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """關閉前提示循環風險。"""
        self.autosaveTimer.stop()
        if self.session.dirty:
            self._refreshSessionFrames()
            try:
                snapshot = writeSessionSnapshot(self.session, reason="close")
                self._setNotice(f"關閉前已儲存工作階段：{snapshot.savedAt}")
            except OSError as error:
                QMessageBox.warning(self, "警告", f"關閉前自動存檔失敗：{error}")
        if self.session.hasCycles:
            QMessageBox.warning(
                self,
                "循環依賴提醒",
                "目前依賴圖仍含循環依賴，關閉後若使用於 CPM 或排序分析，結果可能受影響。",
            )
        super().closeEvent(event)
