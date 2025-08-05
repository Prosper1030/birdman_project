# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
import json
import os
import networkx as nx
import numpy as np
from functools import partial
from scipy.stats import gaussian_kde

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QLabel,
    QTableView,
    QFormLayout,
    QLineEdit,
    QDialog,
    QCheckBox,
    QComboBox,
    QAction,
    QDialogButtonBox,
    QScrollArea,
    QTextEdit,
    QProgressBar,
    QSpinBox,
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QAbstractTableModel
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import qdarkstyle
import pandas as pd
from pandas import DataFrame

from .dsm_processor import (
    readDsm,
    processDsm,
    buildTaskMapping,
    buildMergedDsm,
)
from .wbs_processor import readWbs, mergeByScc, validateIds
from .cpm_processor import (
    cpmForwardPass,
    cpmBackwardPass,
    calculateSlack,
    findCriticalPath,
    extractDurationFromWbs,
)
from .rcpsp_solver import solveRcpsp
from .resource_processor import readResources
from . import visualizer


class MonteCarloWorker(QObject):
    """執行蒙地卡羅模擬的背景工作執行緒"""

    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(
        self,
        wbsDf: pd.DataFrame,
        graph: nx.DiGraph,
        roleKey: str,
        iterations: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.wbsDf = wbsDf
        self.graph = graph
        self.roleKey = roleKey
        self.iterations = iterations
        self.isRunning = True

    def run(self) -> None:
        """執行模擬並回報進度"""
        oCol = f"O_{self.roleKey}"
        mCol = f"M_{self.roleKey}"
        pCol = f"P_{self.roleKey}"
        for field in (oCol, mCol, pCol):
            if field not in self.wbsDf.columns:
                self.finished.emit([])
                return
        wbsDf = self.wbsDf.set_index("Task ID")
        simulationResults: list[float] = []
        for i in range(max(1, self.iterations)):
            if not self.isRunning:
                break
            sampled: dict[str, float] = {}
            for taskId in wbsDf.index:
                o = wbsDf.loc[taskId, oCol]
                m = wbsDf.loc[taskId, mCol]
                p = wbsDf.loc[taskId, pCol]
                if p == o:
                    simulatedDuration = o
                else:
                    mu = (o + 4 * m + p) / 6
                    mu = max(o, min(p, mu))
                    if mu == o:
                        alpha = 1
                    else:
                        alpha = 1 + 4 * ((mu - o) / (p - o))
                    if mu == p:
                        beta = 1
                    else:
                        beta = 1 + 4 * ((p - mu) / (p - o))
                    randomBeta = np.random.beta(alpha, beta)
                    simulatedDuration = o + randomBeta * (p - o)
                sampled[taskId] = float(simulatedDuration)
            forward = cpmForwardPass(self.graph, sampled)
            projectEnd = max(v[1] for v in forward.values())
            simulationResults.append(projectEnd)
            self.progress.emit(i + 1)
            if not self.isRunning:
                break
        self.finished.emit(simulationResults)

    def stop(self) -> None:
        """停止模擬"""
        self.isRunning = False


class PandasModel(QAbstractTableModel):
    def __init__(self, df: DataFrame, dsmMode=False):
        super().__init__()
        self._df = df
        self._dsmMode = dsmMode

    def rowCount(self, parent=None):
        return self._df.shape[0]

    def columnCount(self, parent=None):
        return self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        value = self._df.iloc[index.row(), index.column()]
        # 顯示內容
        if role == Qt.DisplayRole:
            return str(value)
        # 只有DSM分頁才標紅依賴格子
        if self._dsmMode and role == Qt.BackgroundRole:
            """若值為 1 則以紅色標示，避免解析失敗"""
            try:
                if str(value).strip() in {"1", "1.0"}:
                    from PyQt5.QtGui import QColor

                    return QColor(255, 120, 120)
                if float(value) == 1:
                    from PyQt5.QtGui import QColor

                    return QColor(255, 120, 120)
            except (ValueError, TypeError):
                # 轉型失敗時忽略，避免整體流程中斷
                pass
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                # DSM 模式下，直接使用索引作為行表頭（Task ID）
                if self._dsmMode:
                    return str(self._df.index[section])
                # 其他情況維持 1 起始的列號
                return str(section + 1)
        return None


class SettingsDialog(QDialog):
    def __init__(self, current_params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("k 係數參數設定")
        self.setModal(True)

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # 建立輸入框
        self.trfScaleInput = QLineEdit(str(current_params.get("trf_scale", 1.0)))
        self.trfDivisorInput = QLineEdit(str(current_params.get("trf_divisor", 10.0)))
        self.nCoefInput = QLineEdit(str(current_params.get("n_coef", 0.05)))

        # Override 相關元件
        self.overrideCheck = QCheckBox("直接覆蓋 k 值 (Override)")
        self.overrideInput = QLineEdit(str(current_params.get("override", "")))
        self.overrideInput.setEnabled(False)

        # 加入到表單佈局
        form_layout.addRow("轉換比例 (trf_scale):", self.trfScaleInput)
        form_layout.addRow("轉換除數 (trf_divisor):", self.trfDivisorInput)
        form_layout.addRow("數量係數 (n_coef):", self.nCoefInput)
        form_layout.addRow(self.overrideCheck)
        form_layout.addRow("覆寫值:", self.overrideInput)

        layout.addLayout(form_layout)

        # 按鈕
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # 連接 override checkbox 的信號
        self.overrideCheck.stateChanged.connect(
            lambda state: self.overrideInput.setEnabled(state == Qt.Checked)
        )

        # 初始化 override 狀態
        if current_params.get("override") is not None:
            self.overrideCheck.setChecked(True)
            self.overrideInput.setEnabled(True)
            self.overrideInput.setText(str(current_params["override"]))

    def get_settings(self):
        """獲取使用者輸入的設定值"""
        try:
            settings = {
                "base": 1.0,  # 固定值
                "trf_scale": float(self.trfScaleInput.text()),
                "trf_divisor": float(self.trfDivisorInput.text()),
                "n_coef": float(self.nCoefInput.text()),
                "override": None,
            }

            if self.overrideCheck.isChecked():
                overrideValue = self.overrideInput.text().strip()
                if overrideValue:
                    settings["override"] = float(overrideValue)

            return settings
        except ValueError:
            return None


class BirdmanQtApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Birdman Project 進階 GUI")
        # 設定更合適的初始窗口尺寸和最小尺寸
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.dsmPath = ""
        self.wbsPath = ""
        self.resourcePath = ""
        self.manualResourceCap: dict[str, int] = {}
        self.sortedWbs = None
        self.mergedWbs = None
        self.sortedDsm = None
        self.isDarkMode = False
        self.graph = None

        # 圖表相關物件初始化
        self.graphFigure = None
        self.graphCanvas = None
        self.mergedGraphFigure = None
        self.mergedGraphCanvas = None
        self.ganttFigure = None
        self.ganttCanvas = None

        # 蒙地卡羅模擬相關初始化
        self.mcFigure = None
        self.mcCanvas = None
        self.mcLastResults = None
        self.mcThread = None
        self.mcWorker = None

        # CPM 分析相關資料
        self.cmpResult = None
        self.criticalPath = None
        self.mergedGraph = None
        self.mergedDsm = None
        # 儲存不同情境下的甘特圖資料
        self.ganttResults = {}
        # 儲存目前顯示的 CPM 報告 DataFrame
        self.currentDisplayCpmDf = None

        # 儲存分群與分層對應表
        self.scc_map = {}
        self.layer_map = {}
        self.merged_scc_map = {}
        self.merged_layer_map = {}

        # 預設的 k 參數值
        self.defaultKParams = {
            "base": 1.0,  # 固定值
            "trf_scale": 1.0,
            "trf_divisor": 10.0,
            "n_coef": 0.05,
            "override": None,
        }

        # 嘗試從 config.json 讀取設定
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                self.kParams = config.get("merge_k_params", self.defaultKParams)
        except (OSError, json.JSONDecodeError):
            # 檔案不存在或解析失敗時以預設值處理
            self.kParams = self.defaultKParams

        self.initUI()

    def configure_chart_theme(self):
        """統一設定所有圖表的深色模式顏色，以蒙地卡羅圖表為標準"""
        if self.isDarkMode:
            # 統一的深色背景色（以蒙地卡羅為標準）
            dark_bg_color = "#2b2b2b"
            text_color = "white"
            grid_color = "#555555"
            edge_color = "#666666"

            # 更新 matplotlib 的全域設定
            plt.rcParams.update(
                {
                    "figure.facecolor": dark_bg_color,
                    "axes.facecolor": dark_bg_color,
                    "axes.labelcolor": text_color,
                    "axes.edgecolor": edge_color,
                    "text.color": text_color,
                    "xtick.color": text_color,
                    "ytick.color": text_color,
                    "grid.color": grid_color,
                    "axes.spines.left": True,
                    "axes.spines.bottom": True,
                    "axes.spines.top": True,
                    "axes.spines.right": True,
                }
            )
        else:
            # 淺色模式
            light_bg_color = "white"
            text_color = "black"
            grid_color = "#cccccc"
            edge_color = "black"

            plt.rcParams.update(
                {
                    "figure.facecolor": light_bg_color,
                    "axes.facecolor": light_bg_color,
                    "axes.labelcolor": text_color,
                    "axes.edgecolor": edge_color,
                    "text.color": text_color,
                    "xtick.color": text_color,
                    "ytick.color": text_color,
                    "grid.color": grid_color,
                    "axes.spines.left": True,
                    "axes.spines.bottom": True,
                    "axes.spines.top": True,
                    "axes.spines.right": True,
                }
            )

    def get_critical_path_edges(self, graph, critical_path_nodes):
        """將關鍵路徑節點轉換為關鍵路徑邊線集合"""
        if not critical_path_nodes or len(critical_path_nodes) < 2:
            return set()

        criticalEdges = set()
        for i in range(len(critical_path_nodes) - 1):
            currentNode = critical_path_nodes[i]
            nextNode = critical_path_nodes[i + 1]

            # 檢查圖中是否存在這個邊
            if graph.has_edge(currentNode, nextNode):
                criticalEdges.add((currentNode, nextNode))

        return criticalEdges

    def closeEvent(self, event):
        """處理視窗關閉事件，確保正確清理 QThread"""
        # 檢查是否有正在運行的蒙地卡羅模擬
        if hasattr(self, "mcThread") and self.mcThread is not None:
            try:
                if self.mcThread.isRunning():
                    # 詢問用戶是否要強制關閉
                    reply = QMessageBox.question(
                        self,
                        "確認關閉",
                        "蒙地卡羅模擬正在進行中，強制關閉可能導致數據丟失。\n確定要關閉應用程式嗎？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )

                    if reply == QMessageBox.No:
                        event.ignore()
                        return

                    # 用戶選擇強制關閉，停止線程和工作對象
                    if hasattr(self, "mcWorker") and self.mcWorker is not None:
                        # 斷開信號連接，避免在清理過程中觸發信號
                        try:
                            self.mcWorker.progress.disconnect()
                            self.mcWorker.finished.disconnect()
                        except (RuntimeError, TypeError):
                            pass

                    # 終止線程
                    self.mcThread.terminate()
                    self.mcThread.wait(3000)  # 等待3秒讓線程正常結束

                    if self.mcThread.isRunning():
                        # 如果還在運行，強制終止
                        self.mcThread.quit()
                        self.mcThread.wait(1000)

            except RuntimeError:
                # 線程已被刪除，正常繼續
                pass

        # 接受關閉事件
        event.accept()

    def initUI(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 建立主分頁容器
        self.main_tabs = QTabWidget()
        self.tab_setup = QWidget()
        self.tab_results_main = QWidget()
        self.main_tabs.addTab(self.tab_setup, "1. 設定與輸入 (Setup & Input)")
        self.main_tabs.addTab(self.tab_results_main, "2. 分析結果 (Analysis Results)")
        main_layout.addWidget(self.main_tabs)

        setup_layout = QVBoxLayout()
        self.tab_setup.setLayout(setup_layout)

        results_layout = QVBoxLayout()
        self.tab_results_main.setLayout(results_layout)

        # 初始將結果分頁禁用
        self.main_tabs.setTabEnabled(1, False)

        results_layout.addWidget(QLabel("點擊「開始分析」後，結果將會顯示於此"))

        # 檔案路徑顯示區
        self.path_layout = QHBoxLayout()

        self.dsm_label = QLabel("DSM 檔案:")
        self.dsm_path_label = QLabel("")
        self.path_layout.addWidget(self.dsm_label)
        self.path_layout.addWidget(self.dsm_path_label)

        self.wbs_label = QLabel("WBS 檔案:")
        self.wbs_path_label = QLabel("")
        self.path_layout.addWidget(self.wbs_label)
        self.path_layout.addWidget(self.wbs_path_label)

        self.resources_label = QLabel("Resources 檔案:")
        self.resources_path_label = QLabel("")
        self.path_layout.addWidget(self.resources_label)
        self.path_layout.addWidget(self.resources_path_label)

        # 頂端選單列
        menubar = self.menuBar()
        file_menu = menubar.addMenu("檔案")
        settings_menu = menubar.addMenu("設定")
        theme_menu = menubar.addMenu("主題")

        # k 係數參數設定動作
        kParamsAction = QAction("k 係數參數設定...", self)
        kParamsAction.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(kParamsAction)

        # 深色模式切換動作
        self.dark_mode_action = QAction("啟用深色模式", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.toggled.connect(self.toggle_dark_mode)
        theme_menu.addAction(self.dark_mode_action)

        # 檔案選單 - 匯入與匯出
        import_menu = file_menu.addMenu("匯入")
        import_wbs_action = QAction("匯入 WBS 檔案...", self)
        import_wbs_action.triggered.connect(self.chooseWbs)
        import_menu.addAction(import_wbs_action)
        import_dsm_action = QAction("匯入 DSM 檔案...", self)
        import_dsm_action.triggered.connect(self.chooseDsm)
        import_menu.addAction(import_dsm_action)
        import_resources_action = QAction("匯入 Resources 檔案...", self)
        import_resources_action.triggered.connect(self.chooseResources)
        import_menu.addAction(import_resources_action)
        import_folder_action = QAction("匯入資料夾...", self)
        import_folder_action.triggered.connect(self.import_from_folder)
        import_menu.addAction(import_folder_action)

        export_menu = file_menu.addMenu("匯出")
        export_wbs_menu = export_menu.addMenu("匯出合併後的 WBS")
        export_wbs_csv = QAction("存成 CSV 檔案... (.csv)", self)
        export_wbs_csv.triggered.connect(partial(self.exportMergedWbs, "csv"))
        export_wbs_menu.addAction(export_wbs_csv)
        export_wbs_xlsx = QAction("存成 Excel 檔案... (.xlsx)", self)
        export_wbs_xlsx.triggered.connect(partial(self.exportMergedWbs, "xlsx"))
        export_wbs_menu.addAction(export_wbs_xlsx)

        export_dsm_menu = export_menu.addMenu("匯出合併後的 DSM")
        export_dsm_csv = QAction("存成 CSV 檔案... (.csv)", self)
        export_dsm_csv.triggered.connect(partial(self.exportMergedDsm, "csv"))
        export_dsm_menu.addAction(export_dsm_csv)
        export_dsm_xlsx = QAction("存成 Excel 檔案... (.xlsx)", self)
        export_dsm_xlsx.triggered.connect(partial(self.exportMergedDsm, "xlsx"))
        export_dsm_menu.addAction(export_dsm_xlsx)

        export_gantt_menu = export_menu.addMenu("匯出甘特圖")
        export_gantt_png = QAction("存成 PNG 圖片... (.png)", self)
        export_gantt_png.triggered.connect(partial(self.exportGanttChart, "png"))
        export_gantt_menu.addAction(export_gantt_png)
        export_gantt_svg = QAction("存成 SVG 圖片... (.svg)", self)
        export_gantt_svg.triggered.connect(partial(self.exportGanttChart, "svg"))
        export_gantt_menu.addAction(export_gantt_svg)

        export_graph_menu = export_menu.addMenu("匯出原始依賴關係圖")
        export_graph_png = QAction("存成 PNG 圖片... (.png)", self)
        export_graph_png.triggered.connect(partial(self.exportGraph, "png"))
        export_graph_menu.addAction(export_graph_png)
        export_graph_svg = QAction("存成 SVG 圖片... (.svg)", self)
        export_graph_svg.triggered.connect(partial(self.exportGraph, "svg"))
        export_graph_menu.addAction(export_graph_svg)

        export_m_graph_menu = export_menu.addMenu("匯出合併後依賴關係圖")
        export_m_graph_png = QAction("存成 PNG 圖片... (.png)", self)
        export_m_graph_png.triggered.connect(partial(self.exportMergedGraph, "png"))
        export_m_graph_menu.addAction(export_m_graph_png)
        export_m_graph_svg = QAction("存成 SVG 圖片... (.svg)", self)
        export_m_graph_svg.triggered.connect(partial(self.exportMergedGraph, "svg"))
        export_m_graph_menu.addAction(export_m_graph_svg)

        export_cpm_menu = export_menu.addMenu("匯出 CPM 分析結果")
        export_cpm_csv = QAction("存成 CSV 檔案... (.csv)", self)
        export_cpm_csv.triggered.connect(partial(self.export_cpm_results, "csv"))
        export_cpm_menu.addAction(export_cpm_csv)
        export_cpm_xlsx = QAction("存成 Excel 檔案... (.xlsx)", self)
        export_cpm_xlsx.triggered.connect(partial(self.export_cpm_results, "xlsx"))
        export_cpm_menu.addAction(export_cpm_xlsx)

        # 蒙地卡羅匯出
        export_mc_menu = export_menu.addMenu("匯出蒙地卡羅分析")
        export_mc_png = QAction("存成 PNG 圖片... (.png)", self)
        export_mc_png.triggered.connect(partial(self.export_monte_carlo_chart, "png"))
        export_mc_menu.addAction(export_mc_png)
        export_mc_svg = QAction("存成 SVG 圖片... (.svg)", self)
        export_mc_svg.triggered.connect(partial(self.export_monte_carlo_chart, "svg"))
        export_mc_menu.addAction(export_mc_svg)

        # 執行分析按鈕
        self.full_analysis_button = QPushButton("執行完整分析 (Run Full Analysis)")
        self.full_analysis_button.clicked.connect(self.run_full_analysis)

        setup_layout.addLayout(self.path_layout)
        setup_layout.addWidget(self.full_analysis_button)

        # 分析結果分頁集合 (移除原始DSM和原始WBS)
        self.tabs_results = QTabWidget()
        self.tab_sorted_wbs = QWidget()
        self.tab_merged_wbs = QWidget()
        self.tab_merged_dsm = QWidget()
        self.tab_sorted_dsm = QWidget()
        self.tab_graph = QWidget()
        self.tab_merged_graph = QWidget()
        self.tab_cmp_result = QWidget()
        self.tab_gantt_chart = QWidget()
        self.tab_monte_carlo = QWidget()
        self.tab_advanced_analysis = QWidget()  # 新增進階分析分頁
        # 按照要求的順序：先排序，再合併，最後依賴關係圖
        self.tabs_results.addTab(self.tab_sorted_wbs, "排序 WBS")
        self.tabs_results.addTab(self.tab_sorted_dsm, "排序 DSM")
        self.tabs_results.addTab(self.tab_graph, "依賴關係圖")
        self.tabs_results.addTab(self.tab_merged_wbs, "合併 WBS")
        self.tabs_results.addTab(self.tab_merged_dsm, "合併 DSM")
        self.tabs_results.addTab(self.tab_merged_graph, "合併後依賴圖")
        self.tabs_results.addTab(self.tab_cmp_result, "CPM 分析結果")
        self.tabs_results.addTab(self.tab_gantt_chart, "甘特圖")
        self.tabs_results.addTab(self.tab_monte_carlo, "蒙地卡羅模擬 (Monte Carlo)")
        self.tabs_results.addTab(self.tab_advanced_analysis, "進階分析")
        results_layout.addWidget(self.tabs_results)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 表格 (移除原始DSM和原始WBS視圖)
        self.sorted_wbs_view = QTableView()
        self.merged_wbs_view = QTableView()
        self.sorted_dsm_view = QTableView()
        self.merged_dsm_view = QTableView()
        self.cmp_result_view = QTableView()
        # 預覽用表格
        self.dsm_preview = QTableView()
        self.wbs_preview = QTableView()
        self.resources_preview = QTableView()

        # 預覽分頁
        self.preview_tabs = QTabWidget()
        self.wbs_preview_tab = QWidget()
        self.dsm_preview_tab = QWidget()
        self.resources_preview_tab = QWidget()
        self.preview_tabs.addTab(self.wbs_preview_tab, "WBS Preview")
        self.preview_tabs.addTab(self.dsm_preview_tab, "DSM Preview")
        self.preview_tabs.addTab(self.resources_preview_tab, "Resources Preview")
        self.wbs_preview_tab.setLayout(QVBoxLayout())
        self.wbs_preview_tab.layout().addWidget(self.wbs_preview)
        self.dsm_preview_tab.setLayout(QVBoxLayout())
        self.dsm_preview_tab.layout().addWidget(self.dsm_preview)
        self.resources_preview_tab.setLayout(QVBoxLayout())
        self.resources_preview_tab.layout().addWidget(self.resources_preview)

        setup_layout.addWidget(self.preview_tabs, 1)  # 設定伸縮比例，讓預覽區域可以伸縮
        # 移除重複的按鈕添加，按鈕已經在前面加入過了
        # 依賴關係圖容器（Canvas 之後動態加入）
        self.graph_container = QWidget()
        self.graph_container_layout = QVBoxLayout(self.graph_container)
        self.graph_container_layout.setContentsMargins(0, 0, 0, 0)

        # 合併後依賴圖容器
        self.merged_graph_container = QWidget()
        self.merged_graph_container_layout = QVBoxLayout(self.merged_graph_container)
        self.merged_graph_container_layout.setContentsMargins(0, 0, 0, 0)

        # 建立外層容器（用於控制大小和捲動）
        self.graph_outer_container = QWidget()
        self.graph_outer_layout = QVBoxLayout(self.graph_outer_container)
        self.graph_outer_layout.setContentsMargins(0, 0, 0, 0)

        # 合併後圖的容器與捲動區域
        self.merged_graph_outer_container = QWidget()
        self.merged_graph_outer_layout = QVBoxLayout(self.merged_graph_outer_container)
        self.merged_graph_outer_layout.setContentsMargins(0, 0, 0, 0)

        # 設定固定的參考尺寸
        self.graph_container.setMinimumSize(1000, 800)
        self.merged_graph_container.setMinimumSize(1000, 800)

        # 建立捲動區域
        self.scrollArea = QScrollArea(self.graph_outer_container)
        self.scrollArea.setWidget(self.graph_container)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.merged_scroll_area = QScrollArea(self.merged_graph_outer_container)
        self.merged_scroll_area.setWidget(self.merged_graph_container)
        self.merged_scroll_area.setWidgetResizable(True)
        self.merged_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.merged_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.graph_outer_layout.addWidget(self.scrollArea)
        self.merged_graph_outer_layout.addWidget(self.merged_scroll_area)

        # 只在 WBS 相關表格隱藏行號
        for view in [
            self.sorted_wbs_view,
            self.merged_wbs_view,
            self.cmp_result_view,
        ]:
            view.verticalHeader().setVisible(False)
        # DSM 表格顯示行號 (Task ID)
        self.sorted_dsm_view.verticalHeader().setVisible(True)
        self.merged_dsm_view.verticalHeader().setVisible(True)
        self.tab_sorted_wbs.setLayout(QVBoxLayout())
        self.tab_sorted_wbs.layout().addWidget(self.sorted_wbs_view)
        self.tab_merged_wbs.setLayout(QVBoxLayout())
        self.tab_merged_wbs.layout().addWidget(self.merged_wbs_view)
        self.tab_merged_dsm.setLayout(QVBoxLayout())
        self.tab_merged_dsm.layout().addWidget(self.merged_dsm_view)
        self.tab_sorted_dsm.setLayout(QVBoxLayout())
        self.tab_sorted_dsm.layout().addWidget(self.sorted_dsm_view)
        self.tab_graph.setLayout(QVBoxLayout())
        self.tab_graph.layout().addWidget(self.graph_outer_container)
        self.tab_merged_graph.setLayout(QVBoxLayout())
        self.tab_merged_graph.layout().addWidget(self.merged_graph_outer_container)
        self.tab_cmp_result.setLayout(QVBoxLayout())
        cpm_top_layout = QHBoxLayout()

        # 左邊完整的控制區域
        cpm_display_label = QLabel("顯示模式：")
        cpm_top_layout.addWidget(cpm_display_label)
        self.cpmDisplayCombo = QComboBox()
        self.cpmDisplayCombo.currentIndexChanged.connect(self.update_cpm_display)
        cpm_top_layout.addWidget(self.cpmDisplayCombo)

        cpm_top_layout.addStretch()
        self.tab_cmp_result.layout().addLayout(cpm_top_layout)
        self.tab_cmp_result.layout().addWidget(self.cmp_result_view)
        self.tab_gantt_chart.setLayout(QVBoxLayout())
        self.tab_advanced_analysis.setLayout(QVBoxLayout())

        # --- RCPSP 排程區塊 ---
        rcpsp_group = QWidget()
        rcpsp_layout = QVBoxLayout()
        rcpsp_group.setLayout(rcpsp_layout)

        rcpsp_title = QLabel("<h3>RCPSP 資源排程 (RCPSP Resource Scheduling)</h3>")
        rcpsp_layout.addWidget(rcpsp_title)

        self.configResourcesButton = QPushButton("設定資源容量")
        rcpsp_layout.addWidget(self.configResourcesButton)

        self.runRcpspButton = QPushButton("執行 RCPSP 資源排程")
        rcpsp_layout.addWidget(self.runRcpspButton)

        rcpsp_layout.addStretch()
        self.tab_advanced_analysis.layout().addWidget(rcpsp_group)

        # --- 蒙地卡羅模擬分頁 ---
        mc_main_layout = QVBoxLayout()
        self.tab_monte_carlo.setLayout(mc_main_layout)

        mc_top_layout = QHBoxLayout()
        mc_main_layout.addLayout(mc_top_layout)

        mc_top_layout.addWidget(QLabel("分析對象:"))
        self.mc_role_select_combo = QComboBox()
        self.mc_role_select_combo.addItems(["新手 (Novice)", "專家 (Expert)"])
        mc_top_layout.addWidget(self.mc_role_select_combo)

        mc_top_layout.addWidget(QLabel("模擬次數:"))
        self.mc_iterations_spinbox = QSpinBox()
        self.mc_iterations_spinbox.setMaximum(100000)
        self.mc_iterations_spinbox.setValue(1000)
        mc_top_layout.addWidget(self.mc_iterations_spinbox)

        mc_top_layout.addWidget(QLabel("圖表模式:"))
        self.mc_chart_mode_combo = QComboBox()
        self.mc_chart_mode_combo.addItems(["次數模式", "密度模式"])
        self.mc_chart_mode_combo.setCurrentIndex(0)  # 預設為次數模式
        mc_top_layout.addWidget(self.mc_chart_mode_combo)

        self.mc_run_button = QPushButton("開始模擬")
        mc_top_layout.addWidget(self.mc_run_button)

        self.mc_progress_bar = QProgressBar()
        mc_top_layout.addWidget(self.mc_progress_bar)
        mc_top_layout.addStretch()

        mcResultLayout = QHBoxLayout()
        mc_main_layout.addLayout(mcResultLayout)

        # 增大直方圖尺寸
        self.mcFigure = Figure(figsize=(8, 5))
        self.mcCanvas = FigureCanvas(self.mcFigure)

        # 初始化空白圖表，根據當前模式設定顏色
        self.initialize_monte_carlo_chart()

        mcResultLayout.addWidget(self.mcCanvas)

        # 統計資訊區域，調整寬度比例
        mc_stats_widget = QWidget()
        mc_stats_widget.setMaximumWidth(220)  # 限制統計區域寬度
        mc_stats_layout = QVBoxLayout()
        mc_stats_widget.setLayout(mc_stats_layout)

        self.mc_mean_label = QLabel("平均總工時：-")
        self.mc_std_label = QLabel("標準差：-")
        self.mc_p50_label = QLabel("50% 完成機率：-")
        self.mc_p85_label = QLabel("85% 完成機率：-")
        self.mc_p95_label = QLabel("95% 完成機率：-")

        # 設定標籤的字體和對齊
        for label in [
            self.mc_mean_label,
            self.mc_std_label,
            self.mc_p50_label,
            self.mc_p85_label,
            self.mc_p95_label,
        ]:
            label.setAlignment(Qt.AlignLeft)
            label.setStyleSheet("padding: 2px; margin: 1px;")

        mc_stats_layout.addWidget(self.mc_mean_label)
        mc_stats_layout.addWidget(self.mc_std_label)
        mc_stats_layout.addWidget(self.mc_p50_label)
        mc_stats_layout.addWidget(self.mc_p85_label)
        mc_stats_layout.addWidget(self.mc_p95_label)
        mc_stats_layout.addStretch()

        mcResultLayout.addWidget(mc_stats_widget)

        # --- 按鈕連接 ---
        self.mc_run_button.clicked.connect(self.run_monte_carlo_simulation)
        self.mc_chart_mode_combo.currentIndexChanged.connect(self.on_chart_mode_changed)
        self.runRcpspButton.clicked.connect(self.runRcpspOptimization)
        self.configResourcesButton.clicked.connect(self.openResourceConfigDialog)

        # 甘特圖情境切換下拉選單
        gantt_top_layout = QHBoxLayout()

        # 左邊角色選擇
        role_label = QLabel("角色：")
        gantt_top_layout.addWidget(role_label)
        self.role_selection_combo = QComboBox()
        self.role_selection_combo.addItems(["新手 (Novice)", "專家 (Expert)"])
        gantt_top_layout.addWidget(self.role_selection_combo)

        # 中間的顯示模式選擇
        self.ganttDisplayCombo = QComboBox()
        self.ganttDisplayCombo.currentIndexChanged.connect(self.update_gantt_display)
        gantt_top_layout.addWidget(self.ganttDisplayCombo)

        # 右邊的總工時顯示
        self.total_hours_label = QLabel("總工時：0 小時")
        gantt_top_layout.addWidget(self.total_hours_label)
        gantt_top_layout.addStretch()
        self.tab_gantt_chart.layout().addLayout(gantt_top_layout)

        # 甘特圖容器
        self.gantt_container = QWidget()
        self.gantt_container.setLayout(QVBoxLayout())
        self.tab_gantt_chart.layout().addWidget(self.gantt_container)

        # 初始化圖表主題配置
        self.configure_chart_theme()

    def chooseDsm(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 DSM 檔案", "", "CSV Files (*.csv)"
        )
        if path:
            self.dsmPath = path
            self.dsm_path_label.setText(path)
            try:
                dsm = readDsm(path)
                model = PandasModel(dsm.head(100), dsmMode=True)
                self.dsm_preview.setModel(model)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, "錯誤", f"DSM 載入失敗：{e}")

    def chooseWbs(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 WBS 檔案", "", "CSV Files (*.csv)"
        )
        if path:
            self.wbsPath = path
            self.wbs_path_label.setText(path)
            try:
                wbs = readWbs(path)
                wbs = self._add_no_column(wbs)
                model = PandasModel(wbs.head(100))
                self.wbs_preview.setModel(model)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, "錯誤", f"WBS 載入失敗：{e}")

    def chooseResources(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 Resources 檔案", "", "CSV Files (*.csv)"
        )
        if path:
            try:
                # 讀取並預覽 Resources 資料
                resources = pd.read_csv(path, encoding="utf-8-sig")
                model = PandasModel(resources.head(100))
                self.resources_preview.setModel(model)
                self.resourcePath = path
                self.resources_path_label.setText(path)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, "錯誤", f"Resources 載入失敗：{e}")

    def import_from_folder(self):
        """從資料夾匯入 WBS、DSM，若有 Resources 亦一併匯入"""
        folder = QFileDialog.getExistingDirectory(self, "選擇資料夾", "")
        if not folder:
            return
        files = os.listdir(folder)
        wbsFiles = [f for f in files if "wbs" in f.lower()]
        dsmFiles = [f for f in files if "dsm" in f.lower()]
        resourceFiles = [f for f in files if "resource" in f.lower()]
        if len(wbsFiles) != 1 or len(dsmFiles) != 1:
            QMessageBox.warning(
                self, "錯誤", "請選擇一個剛好包含一份 WBS 和一份 DSM 檔案的資料夾。"
            )
            return
        wbsPath = os.path.join(folder, wbsFiles[0])
        dsmPath = os.path.join(folder, dsmFiles[0])
        try:
            wbs = readWbs(wbsPath)
            wbs_display = self._add_no_column(wbs)
            dsm = readDsm(dsmPath)
        except (OSError, pd.errors.ParserError, ValueError):
            QMessageBox.critical(
                self, "錯誤", "資料夾中的 WBS 或 DSM 檔案格式不正確，請檢查檔案內容。"
            )
            return
        self.wbsPath = wbsPath
        self.dsmPath = dsmPath
        self.wbs_path_label.setText(wbsPath)
        self.dsm_path_label.setText(dsmPath)
        model_wbs = PandasModel(wbs_display.head(100))
        self.wbs_preview.setModel(model_wbs)
        model_dsm = PandasModel(dsm.head(100), dsmMode=True)
        self.dsm_preview.setModel(model_dsm)

        # 匯入並預覽 Resources（可選）
        self.resourcePath = ""
        self.resources_path_label.setText("")
        self.resources_preview.setModel(PandasModel(pd.DataFrame()))
        if len(resourceFiles) > 1:
            QMessageBox.warning(
                self, "錯誤", "資料夾中最多只能有一份 Resources 檔案，將忽略多餘檔案。"
            )
        elif len(resourceFiles) == 1:
            resourcePath = os.path.join(folder, resourceFiles[0])
            try:
                resources = pd.read_csv(resourcePath, encoding="utf-8-sig")
                model_res = PandasModel(resources.head(100))
                self.resources_preview.setModel(model_res)
                self.resourcePath = resourcePath
                self.resources_path_label.setText(resourcePath)
            except (OSError, pd.errors.ParserError, ValueError):
                QMessageBox.warning(
                    self, "錯誤", "Resources 檔案格式不正確，將忽略。"
                )

    def runAnalysis(self, show_notification=True):
        try:
            dsm = readDsm(self.dsmPath)
            wbs = readWbs(self.wbsPath)
            # 預覽原始資料 (保留在預覽區，但不在分析結果顯示)
            model_dsm = PandasModel(dsm.head(100), dsmMode=True)
            self.dsm_preview.setModel(model_dsm)
            wbs_with_no = self._add_no_column(wbs)
            model_wbs = PandasModel(wbs_with_no.head(100))
            self.wbs_preview.setModel(model_wbs)

            validateIds(wbs, dsm)

            # 統一設定圖表主題顏色
            self.configure_chart_theme()

            sortedDsm, sortedWbs, graph = processDsm(dsm, wbs)
            self.sortedWbs = self._add_no_column(sortedWbs)
            self.sortedDsm = sortedDsm
            self.graph = graph  # 儲存圖形物件供後續使用

            merged = mergeByScc(sortedWbs, self.kParams)
            self.mergedWbs = self._add_no_column(merged)

            # 建立原始 Task ID 到合併後 Task ID 的對應
            task_mapping = buildTaskMapping(sortedWbs, merged)
            # 依映射產生合併後的 DSM
            mergedDsm = buildMergedDsm(self.graph, task_mapping)
            # 根據合併後的 DSM 重新計算層次與圖形
            (
                self.mergedDsm,
                merged_sorted_wbs,
                self.mergedGraph,
            ) = processDsm(
                mergedDsm,
                merged,
            )

            # 儲存原始圖的映射
            self.scc_map = dict(zip(sortedWbs["Task ID"], sortedWbs["SCC_ID"]))
            self.layer_map = dict(zip(sortedWbs["Task ID"], sortedWbs["Layer"]))

            # 計算並儲存合併後圖形的映射
            try:
                source_nodes = [
                    node for node, deg in self.mergedGraph.in_degree() if deg == 0
                ]
                self.merged_layer_map = {}
                for node in self.mergedGraph.nodes():
                    max_dist = 0
                    for src in source_nodes:
                        try:
                            paths = nx.all_simple_paths(self.mergedGraph, src, node)
                            dist = max((len(p) - 1 for p in paths), default=-1)
                            if dist > max_dist:
                                max_dist = dist
                        except nx.NetworkXNoPath:
                            continue
                    self.merged_layer_map[node] = max_dist
            except (ValueError, nx.NetworkXError):
                self.merged_layer_map = {
                    node: i for i, node in enumerate(self.mergedGraph.nodes())
                }

            self.merged_scc_map = {
                node: i for i, node in enumerate(self.mergedGraph.nodes())
            }

            # 重新繪製依賴關係圖
            self.redraw_graph()
            # 預覽
            self.sorted_wbs_view.setModel(PandasModel(self.sortedWbs.head(100)))
            self.merged_wbs_view.setModel(PandasModel(self.mergedWbs.head(100)))
            self.sorted_dsm_view.setModel(
                PandasModel(self.sortedDsm.head(100), dsmMode=True)
            )
            self.merged_dsm_view.setModel(
                PandasModel(self.mergedDsm.head(100), dsmMode=True)
            )
            # 啟用結果分頁並自動切換
            self.main_tabs.setTabEnabled(1, True)
            self.main_tabs.setCurrentIndex(1)
            if show_notification:
                QMessageBox.information(self, "完成", "分析完成，可切換分頁預覽與匯出")
            return True
        except (
            OSError,
            ValueError,
            KeyError,
            nx.NetworkXError,
            pd.errors.ParserError,
        ) as e:
            # 執行流程中可能發生多種錯誤，此處統一彙整顯示訊息
            QMessageBox.critical(self, "錯誤", str(e))
            return False

    def _add_no_column(self, df):
        # 僅針對 WBS 及其衍生表格加 No. 欄，且不覆蓋 Task ID
        df = df.copy()
        # 若最左欄是純數字且不是 Task ID，移除
        first_col = df.columns[0]
        if first_col != "Task ID" and first_col != "No.":
            try:
                as_num = pd.to_numeric(df[first_col], errors="coerce")
                if as_num.notnull().all():
                    df = df.drop(columns=[first_col])
            except (ValueError, TypeError):
                # 轉型失敗時直接忽略
                pass
        df.insert(0, "No.", range(1, len(df) + 1))
        return df

    def _create_cpm_display_df(self, full_results_df, roleKey, time_key):
        """產生精簡版 CPM 結果表"""
        core_display_cols = [
            "Task ID",
            "Name",
            "ES",
            "EF",
            "LS",
            "LF",
            "TF",
            "FF",
            "Critical",
        ]

        role_map = {"novice": "newbie", "expert": "expert"}
        role_suffix = role_map.get(roleKey.lower(), roleKey.lower())
        time_column = f"{time_key}_{role_suffix}"

        columns = core_display_cols.copy()
        if time_column in full_results_df.columns:
            insert_index = columns.index("Name") + 1
            columns.insert(insert_index, time_column)

        existing_cols = [c for c in columns if c in full_results_df.columns]
        display_df = full_results_df[existing_cols].copy()
        return display_df

    def exportSortedWbs(self):
        if self.sortedWbs is None:
            QMessageBox.warning(self, "警告", "請先執行分析")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出排序 WBS", "", "CSV Files (*.csv)"
        )
        if path:
            self.sortedWbs.to_csv(path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "完成", f"已匯出 {path}")

    def exportMergedWbs(self, fmt="csv"):
        """匯出合併後的 WBS"""
        if self.mergedWbs is None:
            QMessageBox.warning(self, "警告", "請先執行分析")
            return
        if fmt == "xlsx":
            fileFilter = "Excel 檔案 (*.xlsx)"
            path, _ = QFileDialog.getSaveFileName(self, "匯出合併 WBS", "", fileFilter)
            if not path:
                return
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.mergedWbs.to_excel(path, index=False)
        else:
            fileFilter = "CSV Files (*.csv)"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "匯出合併 WBS",
                "",
                fileFilter,
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            self.mergedWbs.to_csv(path, encoding="utf-8-sig", index=False)
        QMessageBox.information(self, "完成", f"已匯出 {path}")

    def exportSortedDsm(self):
        if self.sortedDsm is None:
            QMessageBox.warning(self, "警告", "請先執行分析")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出排序 DSM", "", "CSV Files (*.csv)"
        )
        if path:
            self.sortedDsm.to_csv(path, encoding="utf-8-sig")
            QMessageBox.information(self, "完成", f"已匯出 {path}")

    def exportMergedDsm(self, fmt="csv"):
        """匯出合併後的 DSM"""
        if self.mergedDsm is None:
            QMessageBox.warning(self, "警告", "請先執行分析")
            return
        if fmt == "xlsx":
            fileFilter = "Excel 檔案 (*.xlsx)"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "匯出合併 DSM",
                "",
                fileFilter,
            )
            if not path:
                return
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.mergedDsm.to_excel(path, index=False)
        else:
            fileFilter = "CSV Files (*.csv)"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "匯出合併 DSM",
                "",
                fileFilter,
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            self.mergedDsm.to_csv(path, encoding="utf-8-sig", index=False)
        QMessageBox.information(self, "完成", f"已匯出 {path}")

    def exportGraph(self, fmt="png"):
        """匯出原始依賴關係圖"""
        if not hasattr(self, "graph") or self.graph is None:
            QMessageBox.warning(self, "警告", "請先執行分析")
            return

        fileFilter = "PNG 圖片 (*.png)" if fmt == "png" else "SVG 向量圖 (*.svg)"
        path, _ = QFileDialog.getSaveFileName(self, "匯出依賴關係圖", "", fileFilter)
        if not path:
            return

        try:
            if not path.lower().endswith(f".{fmt}"):
                path += f".{fmt}"
            self.graphCanvas.figure.savefig(
                path,
                format=fmt,
                bbox_inches="tight",
                dpi=300,
            )
            QMessageBox.information(self, "完成", f"已匯出依賴關係圖至：{path}")
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "錯誤", f"匯出圖檔時發生錯誤：{e}")

    def exportMergedGraph(self, fmt="png"):
        """匯出合併後依賴關係圖"""
        if not hasattr(self, "mergedGraph") or self.mergedGraph is None:
            QMessageBox.warning(self, "警告", "請先執行分析")
            return

        fileFilter = "PNG 圖片 (*.png)" if fmt == "png" else "SVG 向量圖 (*.svg)"
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出合併後依賴關係圖", "", fileFilter
        )
        if not path:
            return

        try:
            if not path.lower().endswith(f".{fmt}"):
                path += f".{fmt}"
            self.mergedGraphCanvas.figure.savefig(
                path,
                format=fmt,
                bbox_inches="tight",
                dpi=300,
            )
            QMessageBox.information(self, "完成", f"已匯出合併後依賴圖至：{path}")
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "錯誤", f"匯出圖檔時發生錯誤：{e}")

    def runCmpAnalysis(self):
        """執行 CPM 分析"""
        if not (hasattr(self, "mergedGraph") and hasattr(self, "mergedWbs")):
            QMessageBox.warning(self, "警告", "請先執行基本分析")
            return

        try:
            # 檢查合併後的圖是否存在循環
            cycles = list(nx.simple_cycles(self.mergedGraph))
            if cycles:
                cycle_str = " -> ".join(cycles[0] + [cycles[0][0]])
                raise ValueError(
                    f"發現循環依賴：{cycle_str}\n" "請先解決循環依賴問題再進行 CPM 分析"
                )

            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            cmp_params = config.get("cmp_params", {})
            baseField = cmp_params.get("default_duration_field", "Te_newbie")

            # 使用預設角色 newbie，或者可以從其他設定獲取
            role_suffix = "newbie"  # 預設使用新手角色
            partsRole = baseField.split("_", 1)
            if len(partsRole) == 2:
                baseField = f"{partsRole[0]}_{role_suffix}"
            else:
                baseField = f"{baseField}_{role_suffix}"

            # 解析使用者選擇的情境
            choice = self.ganttDisplayCombo.currentText()
            if choice == "All Scenarios":
                scenarios = ["O", "P", "M", "Te"]
            else:
                key = choice.split("(")[-1].split(")")[0]
                scenarios = ["Te" if key.upper() == "TE" else key]

            self.ganttResults = {}

            for sc in scenarios:
                parts = baseField.split("_", 1)
                if len(parts) == 2:
                    durationField = f"{sc}_{parts[1]}"
                else:
                    durationField = sc

                durationsHours = extractDurationFromWbs(
                    self.mergedWbs.drop(columns=["No."]), durationField
                )

                forwardData = cpmForwardPass(
                    self.mergedGraph,
                    durationsHours,
                )
                projectEnd = max(ef for _, ef in forwardData.values())
                backwardData = cpmBackwardPass(
                    self.mergedGraph,
                    durationsHours,
                    projectEnd,
                )
                cpmResult = calculateSlack(
                    forwardData,
                    backwardData,
                    self.mergedGraph,
                )
                wbsWithCpm = self.mergedWbs.copy()
                for col in ["ES", "EF", "LS", "LF", "TF", "FF", "Critical"]:
                    wbsWithCpm[col] = (
                        wbsWithCpm["Task ID"].map(cpmResult[col].to_dict()).fillna(0)
                    )

                self.ganttResults[sc] = (
                    cpmResult,
                    durationsHours,
                    wbsWithCpm,
                    projectEnd,
                )

            # 更新情境下拉選單並顯示第一個結果
            keys = list(self.ganttResults.keys())
            self.ganttDisplayCombo.blockSignals(True)
            self.cpmDisplayCombo.blockSignals(True)
            self.ganttDisplayCombo.clear()
            self.cpmDisplayCombo.clear()
            self.ganttDisplayCombo.addItems(keys)
            self.cpmDisplayCombo.addItems(keys)
            self.ganttDisplayCombo.blockSignals(False)
            self.cpmDisplayCombo.blockSignals(False)
            self.ganttDisplayCombo.setCurrentIndex(0)
            self.cpmDisplayCombo.setCurrentIndex(0)
            self.update_gantt_display()

            QMessageBox.information(self, 'CPM 分析完成', 'CPM 分析已完成')
        except (ValueError, KeyError, nx.NetworkXError) as e:
            QMessageBox.critical(self, '錯誤', f'CPM 分析失敗：{e}')

    def run_full_analysis(self):
        """執行所有情境的 CPM 分析"""
        success = self.runAnalysis(show_notification=False)  # 不顯示基本分析通知
        if not success:
            return

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            cmp_params = config.get("cmp_params", {})
            baseField = cmp_params.get("default_duration_field", "Te_newbie")
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, "錯誤", f"設定檔讀取失敗：{e}")
            return

        roles = {
            "新手": "newbie",
            "專家": "expert",
        }
        time_types = {
            "樂觀時間": "O",
            "悲觀時間": "P",
            "最可能時間": "M",
            "期望時間": "Te",
        }

        self.ganttResults = {}

        for role_text, roleKey in roles.items():
            # 依角色調整基準欄位名稱
            partsRole = baseField.split("_", 1)
            if len(partsRole) == 2:
                baseField = f"{partsRole[0]}_{roleKey}"
            else:
                baseField = f"{baseField}_{roleKey}"

            for time_text, time_key in time_types.items():
                durationField = f"{time_key}_{roleKey}"

                durationsHours = extractDurationFromWbs(
                    self.mergedWbs.drop(columns=["No."]), durationField
                )
                forwardData = cpmForwardPass(
                    self.mergedGraph,
                    durationsHours,
                )
                projectEnd = max(ef for _, ef in forwardData.values())
                backwardData = cpmBackwardPass(
                    self.mergedGraph,
                    durationsHours,
                    projectEnd,
                )
                cpmResult = calculateSlack(
                    forwardData,
                    backwardData,
                    self.mergedGraph,
                )

                wbsWithCpm = self.mergedWbs.copy()
                for col in ["ES", "EF", "LS", "LF", "TF", "FF", "Critical"]:
                    wbsWithCpm[col] = (
                        wbsWithCpm["Task ID"].map(cpmResult[col].to_dict()).fillna(0)
                    )

                key = f"{role_text} - {time_text} ({durationField})"
                self.ganttResults[key] = (
                    cpmResult,
                    durationsHours,
                    wbsWithCpm,
                    projectEnd,
                )

        keys = list(self.ganttResults.keys())
        self.ganttDisplayCombo.blockSignals(True)
        self.cpmDisplayCombo.blockSignals(True)
        self.ganttDisplayCombo.clear()
        self.cpmDisplayCombo.clear()
        self.ganttDisplayCombo.addItems(keys)
        self.cpmDisplayCombo.addItems(keys)
        self.ganttDisplayCombo.blockSignals(False)
        self.cpmDisplayCombo.blockSignals(False)

        default_key = "新手 - 期望時間 (Te_newbie)"
        default_index = keys.index(default_key) if default_key in keys else 0
        self.ganttDisplayCombo.setCurrentIndex(default_index)
        self.cpmDisplayCombo.setCurrentIndex(default_index)
        self.update_gantt_display()

        QMessageBox.information(
            self,
            "完整分析完成",
            f"已完成所有情境的 CPM 分析，共生成 {len(self.ganttResults)} 種情境結果",
        )

    def drawGanttChart(self, cpmData, durations, title, wbsDf):
        """繪製甘特圖並回傳 Figure

        參數:
            cpmData: CPM 計算結果
            durations: 任務工期字典
            title: 圖表標題
            wbsDf: 含任務順序的 WBS 資料
        """
        try:
            fig = Figure(figsize=(16, 12), dpi=100)
            ax = fig.add_subplot(111)

            fig.patch.set_facecolor(plt.rcParams["figure.facecolor"])
            ax.set_facecolor(plt.rcParams["axes.facecolor"])

            fig.subplots_adjust(
                top=0.9,
                bottom=0.15,
                left=0.2,
                right=0.95,
            )

            # 取得任務列表和相關數據
            tasks = wbsDf["Task ID"].tolist()
            start_times = [cpmData.at[t, "ES"] for t in tasks]
            task_durations = [durations.get(t, 0) for t in tasks]

            # 設定任務條的位置和顏色
            y_positions = range(len(tasks))
            colors = ["red" if cpmData.at[t, "Critical"] else "skyblue" for t in tasks]

            # 繪製任務條
            ax.barh(
                y_positions,
                task_durations,
                left=start_times,
                color=colors,
                alpha=0.8,
                height=0.6,
                edgecolor=plt.rcParams["axes.edgecolor"],
                linewidth=1,
                zorder=2,
            )

            # 設定 Y 軸標籤
            ax.set_yticks(y_positions)
            ax.set_yticklabels(
                tasks,
                fontsize=10,
                fontweight="bold",
                color=plt.rcParams["axes.labelcolor"],
            )

            ax.tick_params(axis="x", colors=plt.rcParams["xtick.color"])
            ax.tick_params(axis="y", colors=plt.rcParams["ytick.color"])

            for spine in ax.spines.values():
                spine.set_edgecolor(plt.rcParams["axes.edgecolor"])

            # 加強網格線
            ax.grid(
                True,
                axis="x",
                linestyle="--",
                color=plt.rcParams["grid.color"],
                alpha=0.3,
                zorder=1,
            )
            ax.set_axisbelow(True)

            # 設定標籤和標題
            ax.set_xlabel(
                "時間 (小時)",
                fontsize=11,
                fontweight="bold",
                color=plt.rcParams["axes.labelcolor"],
            )
            ax.set_title(
                title,
                fontsize=14,
                pad=20,
                color=plt.rcParams["axes.labelcolor"],
            )
            # 在每個任務條上添加持續時間標籤
            for i, (duration, start) in enumerate(zip(task_durations, start_times)):
                if duration > 0:
                    ax.text(
                        start + duration + 2,
                        i,
                        f"{duration:.1f}h",
                        va="center",
                        fontsize=9,
                        alpha=0.7,
                        color=plt.rcParams["text.color"],
                    )

            # 反轉 Y 軸
            ax.invert_yaxis()

            return fig
        except Exception as e:
            QMessageBox.warning(self, "警告", f"甘特圖繪製失敗：{e}")
            return Figure()

    def drawRcpspGanttChart(self, scheduleDf, durationField, title):
        """繪製 RCPSP 甘特圖並回傳 Figure"""
        try:
            fig = Figure(figsize=(16, 12), dpi=100)
            ax = fig.add_subplot(111)
            fig.patch.set_facecolor(plt.rcParams["figure.facecolor"])
            ax.set_facecolor(plt.rcParams["axes.facecolor"])
            fig.subplots_adjust(top=0.9, bottom=0.15, left=0.2, right=0.95)
            tasks = scheduleDf["Task ID"].tolist()
            startTimes = scheduleDf["Start"].tolist()
            durations = scheduleDf[durationField].tolist()
            yPos = range(len(tasks))
            ax.barh(
                yPos,
                durations,
                left=startTimes,
                color="dodgerblue",
                alpha=0.8,
                height=0.6,
                edgecolor=plt.rcParams["axes.edgecolor"],
                linewidth=1,
                zorder=2,
            )
            ax.set_yticks(list(yPos))
            ax.set_yticklabels(
                tasks,
                fontsize=10,
                fontweight="bold",
                color=plt.rcParams["axes.labelcolor"],
            )
            ax.tick_params(axis="x", colors=plt.rcParams["xtick.color"])
            ax.tick_params(axis="y", colors=plt.rcParams["ytick.color"])
            for spine in ax.spines.values():
                spine.set_edgecolor(plt.rcParams["axes.edgecolor"])
            ax.grid(
                True,
                axis="x",
                linestyle="--",
                color=plt.rcParams["grid.color"],
                alpha=0.3,
                zorder=1,
            )
            ax.set_axisbelow(True)
            ax.set_xlabel(
                "時間 (小時)",
                fontsize=11,
                fontweight="bold",
                color=plt.rcParams["axes.labelcolor"],
            )
            ax.set_title(
                title,
                fontsize=14,
                pad=20,
                color=plt.rcParams["axes.labelcolor"],
            )
            for i, (dur, start) in enumerate(zip(durations, startTimes)):
                if dur > 0:
                    ax.text(
                        start + dur + 0.1,
                        i,
                        f"{dur:.1f}h",
                        va="center",
                        fontsize=9,
                        alpha=0.7,
                        color=plt.rcParams["text.color"],
                    )
            ax.invert_yaxis()
            return fig
        except Exception as e:
            QMessageBox.warning(self, "警告", f"RCPSP 甘特圖繪製失敗：{e}")
            return Figure()

    def update_gantt_display(self):
        """根據下拉選單切換甘特圖與結果顯示"""
        key = self.ganttDisplayCombo.currentText()
        if hasattr(self, "cpmDisplayCombo"):
            self.cpmDisplayCombo.blockSignals(True)
            if self.cpmDisplayCombo.currentText() != key:
                self.cpmDisplayCombo.setCurrentText(key)
            self.cpmDisplayCombo.blockSignals(False)
        if key not in self.ganttResults:
            return
        cpmDf, durations, wbsDf, projectEnd = self.ganttResults[key]
        self.cmpResult = wbsDf

        roleKey = "novice" if "新手" in key else "expert"
        if "(O_" in key:
            time_key = "O"
        elif "(P_" in key:
            time_key = "P"
        elif "(M_" in key:
            time_key = "M"
        else:
            time_key = "Te"

        self.currentDisplayCpmDf = self._create_cpm_display_df(wbsDf, roleKey, time_key)
        self.criticalPath = findCriticalPath(cpmDf)

        # 更新關鍵路徑後，重繪合併後的依賴圖以顯示關鍵路徑
        self.redraw_merged_graph()

        self.cmp_result_view.setModel(PandasModel(self.currentDisplayCpmDf.head(100)))
        self.total_hours_label.setText(f"總工時：{projectEnd:.1f} 小時")
        newTitle = f"{key}\n總工時: {projectEnd:.2f} 小時"

        # 先清除舊的圖表
        layout = self.gantt_container.layout()
        for i in reversed(range(layout.count())):
            oldWidget = layout.itemAt(i).widget()
            if oldWidget:
                oldWidget.setParent(None)

        # 重新產生甘特圖並加入佈局
        self.ganttFigure = self.drawGanttChart(
            cpmDf,
            durations,
            newTitle,
            wbsDf,
        )
        self.ganttCanvas = FigureCanvas(self.ganttFigure)
        scrollArea = QScrollArea()
        scrollArea.setWidget(self.ganttCanvas)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setMinimumHeight(1000)
        self.ganttCanvas.setMinimumSize(1200, max(1000, len(wbsDf) * 35))

        containerLayout = QVBoxLayout()
        containerLayout.setContentsMargins(20, 40, 20, 40)
        containerLayout.addWidget(scrollArea)
        container = QWidget()
        container.setLayout(containerLayout)
        self.gantt_container.layout().addWidget(container)
        self.ganttCanvas.draw()

    def update_cpm_display(self):
        """切換 CPM 結果顯示並同步甘特圖"""
        index = self.cpmDisplayCombo.currentIndex()
        if index != self.ganttDisplayCombo.currentIndex():
            self.ganttDisplayCombo.setCurrentIndex(index)
        else:
            self.update_gantt_display()

    def exportCmpResult(self):
        """匯出 CPM 分析結果"""
        if self.cmpResult is None:
            QMessageBox.warning(self, "警告", "請先執行 CPM 分析")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出 CPM 分析結果", "", "CSV Files (*.csv)"
        )
        if path:
            self.cmpResult.to_csv(path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "完成", f"已匯出 CPM 結果：{path}")

    def export_cpm_results(self, fmt="csv"):
        """匯出目前顯示的 CPM 精簡報告"""
        if self.currentDisplayCpmDf is None:
            QMessageBox.warning(self, "警告", "沒有可匯出的 CPM 結果")
            return
        if fmt == "xlsx":
            fileFilter = "Excel 檔案 (*.xlsx)"
            path, _ = QFileDialog.getSaveFileName(
                self, "匯出 CPM 分析結果", "", fileFilter
            )
            if not path:
                return
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.currentDisplayCpmDf.to_excel(path, index=False)
        else:
            fileFilter = "CSV Files (*.csv)"
            path, _ = QFileDialog.getSaveFileName(
                self, "匯出 CPM 分析結果", "", fileFilter
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            self.currentDisplayCpmDf.to_csv(path, index=False, encoding="utf-8-sig")
        QMessageBox.information(self, "完成", f"已匯出 {path}")

    def open_settings_dialog(self):
        """開啟 k 係數參數設定對話框"""
        dialog = SettingsDialog(self.kParams, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            if settings is None:
                QMessageBox.critical(self, "錯誤", "k 係數參數必須為數字！")
                return
            self.kParams = settings

            # 將新設定寫入 config.json
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                config["merge_k_params"] = self.kParams
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            except (OSError, json.JSONDecodeError) as e:
                QMessageBox.warning(self, "警告", f"無法保存設定：{e}")

    def toggle_dark_mode(self, checked):
        """切換深色/淺色模式"""
        try:
            # 檢查是否有蒙地卡羅模擬正在進行
            is_simulation_running = False
            try:
                is_simulation_running = (
                    hasattr(self, "mcThread")
                    and self.mcThread is not None
                    and self.mcThread.isRunning()
                )
            except RuntimeError:
                # QThread 已被刪除，表示模擬已完成
                is_simulation_running = False

            # 如果模擬正在進行，顯示警告並阻止切換
            if is_simulation_running:
                # 恢復原始狀態
                self.dark_mode_action.blockSignals(True)
                self.dark_mode_action.setChecked(self.isDarkMode)
                self.dark_mode_action.blockSignals(False)
                QMessageBox.warning(
                    self,
                    "無法切換主題",
                    "蒙地卡羅模擬進行中，請等待模擬完成後再進行任何操作。",
                )
                return

            # 保存當前窗口狀態
            current_geometry = self.geometry()
            was_maximized = self.isMaximized()

            if checked:
                # 載入深色樣式表，包含標題欄
                dark_style = qdarkstyle.load_stylesheet_pyqt5()
                # 為標題欄添加額外的樣式
                dark_style += """
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar {
                    background-color: #353535;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QMenuBar::item {
                    background-color: transparent;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #4a90e2;
                }
                """
                self.setStyleSheet(dark_style)
                self.isDarkMode = True
                self.dark_mode_action.setText("啟用淺色模式")
            else:
                self.setStyleSheet("")
                self.isDarkMode = False
                self.dark_mode_action.setText("啟用深色模式")

            # 處理窗口幾何問題
            # 等待樣式應用完成
            QApplication.processEvents()

            # 溫和地處理窗口狀態
            if was_maximized:
                # 如果之前是最大化，重新最大化
                self.showMaximized()
            else:
                # 如果不是最大化狀態，只調整最小尺寸避免衝突
                # 暫時放寬最小尺寸限制
                self.setMinimumSize(600, 400)
                QApplication.processEvents()

                # 嘗試恢復原始幾何，如果失敗則使用安全的尺寸
                try:
                    self.setGeometry(current_geometry)
                except (RuntimeError, TypeError, ValueError):
                    # 如果恢復失敗，使用安全的尺寸
                    self.resize(1200, 800)

                # 恢復合適的最小尺寸
                self.setMinimumSize(800, 600)

            # 再次處理事件以確保佈局正確
            QApplication.processEvents()

            # 統一配置圖表主題顏色
            self.configure_chart_theme()

            # --- 清除舊圖表 ---
            if hasattr(self, "ganttFigure") and self.ganttFigure:
                self.ganttFigure.clear()
            if hasattr(self, "graphFigure") and self.graphFigure:
                self.graphFigure.clear()
            if hasattr(self, "mergedGraphFigure") and self.mergedGraphFigure:
                self.mergedGraphFigure.clear()
            if hasattr(self, "mcFigure") and self.mcFigure:
                self.mcFigure.clear()

            # 重繪圖表
            self.redraw_graph()
            if hasattr(self, "ganttResults") and self.ganttResults:
                self.update_gantt_display()

            # 重繪蒙地卡羅圖表
            if hasattr(self, "mcLastResults") and self.mcLastResults:
                self.plot_results(self.mcLastResults)
            else:
                # 如果沒有結果，重新初始化空白圖表
                self.initialize_monte_carlo_chart()

        except (AttributeError, RuntimeError) as e:
            # 如果主題切換過程中出現任何錯誤，顯示錯誤訊息但不崩潰
            QMessageBox.warning(
                self,
                "主題切換警告",
                f"主題切換過程中發生問題：{str(e)}\n程序將繼續正常運行。",
            )

    def redraw_graph(self):
        """重新繪製依賴關係圖"""
        if not hasattr(self, "graph") or self.graph is None:
            return

        if hasattr(self, "sortedWbs") and self.sortedWbs is not None:
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                viz_params = config.get("visualization_params", {})

                # 清除舊的 Canvas
                for i in reversed(range(self.graph_container_layout.count())):
                    oldWidget = self.graph_container_layout.itemAt(i).widget()
                    if oldWidget:
                        oldWidget.setParent(None)

                for i in reversed(range(self.merged_graph_container_layout.count())):
                    oldWidget = self.merged_graph_container_layout.itemAt(i).widget()
                    if oldWidget:
                        oldWidget.setParent(None)

                # 重新建立原始圖
                self.graphFigure = visualizer.create_dependency_graph_figure(
                    self.graph,
                    self.scc_map,
                    self.layer_map,
                    viz_params,
                )
                self.graphCanvas = FigureCanvas(self.graphFigure)
                self.graph_container_layout.addWidget(self.graphCanvas)
                self.graphCanvas.draw()
                canvas_size = self.graphCanvas.get_width_height()
                if canvas_size[0] > 0 and canvas_size[1] > 0:
                    self.graph_container.setMinimumSize(
                        int(canvas_size[0] * 1.1),
                        int(canvas_size[1] * 1.1),
                    )

                # 重新建立合併後圖
                if self.mergedGraph is not None:
                    # 計算關鍵路徑邊線
                    critical_path_edges = None
                    if hasattr(self, "criticalPath") and self.criticalPath:
                        critical_path_edges = self.get_critical_path_edges(
                            self.mergedGraph, self.criticalPath
                        )

                    self.mergedGraphFigure = visualizer.create_dependency_graph_figure(
                        self.mergedGraph,
                        self.merged_scc_map,
                        self.merged_layer_map,
                        viz_params,
                        critical_path_edges,
                    )
                    self.mergedGraphCanvas = FigureCanvas(self.mergedGraphFigure)
                    self.merged_graph_container_layout.addWidget(self.mergedGraphCanvas)
                    self.mergedGraphCanvas.draw()
                    m_size = self.mergedGraphCanvas.get_width_height()
                    if m_size[0] > 0 and m_size[1] > 0:
                        self.merged_graph_container.setMinimumSize(
                            int(m_size[0] * 1.1),
                            int(m_size[1] * 1.1),
                        )
            except Exception as e:  # pylint: disable=broad-except
                QMessageBox.warning(self, "警告", f"圖表重繪失敗：{e}")

    def redraw_merged_graph(self):
        """專門重繪合併後的依賴關係圖（包含關鍵路徑資訊）"""
        if not hasattr(self, "mergedGraph") or self.mergedGraph is None:
            return

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            viz_params = config.get("visualization_params", {})

            # 清除舊的合併圖 Canvas
            for i in reversed(range(self.merged_graph_container_layout.count())):
                oldWidget = self.merged_graph_container_layout.itemAt(i).widget()
                if oldWidget:
                    oldWidget.setParent(None)

            # 計算關鍵路徑邊線
            critical_path_edges = None
            if hasattr(self, "criticalPath") and self.criticalPath:
                critical_path_edges = self.get_critical_path_edges(
                    self.mergedGraph, self.criticalPath
                )

            # 重新建立合併後圖
            self.mergedGraphFigure = visualizer.create_dependency_graph_figure(
                self.mergedGraph,
                self.merged_scc_map,
                self.merged_layer_map,
                viz_params,
                critical_path_edges,
            )
            self.mergedGraphCanvas = FigureCanvas(self.mergedGraphFigure)
            self.merged_graph_container_layout.addWidget(self.mergedGraphCanvas)
            self.mergedGraphCanvas.draw()

            m_size = self.mergedGraphCanvas.get_width_height()
            if m_size[0] > 0 and m_size[1] > 0:
                self.merged_graph_container.setMinimumSize(
                    int(m_size[0] * 1.1),
                    int(m_size[1] * 1.1),
                )

        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.warning(self, "警告", f"合併後依賴圖重繪失敗：{e}")

    def exportGanttChart(self, fmt="png"):
        """匯出甘特圖"""
        if not hasattr(self, "ganttFigure") or self.ganttFigure is None:
            QMessageBox.warning(self, "警告", "請先執行 CPM 分析")
            return

        fileFilter = "PNG 圖片 (*.png)" if fmt == "png" else "SVG 向量圖 (*.svg)"
        path, _ = QFileDialog.getSaveFileName(self, "匯出甘特圖", "", fileFilter)

        if not path:
            return

        try:
            if not path.lower().endswith(f".{fmt}"):
                path += f".{fmt}"
            self.ganttFigure.savefig(
                path, format=fmt, bbox_inches="tight", dpi=300, pad_inches=0.5
            )
            QMessageBox.information(self, "完成", f"已匯出甘特圖至：{path}")
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "錯誤", f"匯出圖檔時發生錯誤：{e}")

    def run_monte_carlo_simulation(self) -> None:
        """執行蒙地卡羅模擬"""
        if self.mergedGraph is None or self.mergedWbs is None:
            QMessageBox.warning(self, "警告", "請先執行完整分析")
            return

        # 清理舊的線程引用（如果存在）
        if hasattr(self, "mcThread") and self.mcThread is not None:
            try:
                if self.mcThread.isRunning():
                    QMessageBox.warning(self, "警告", "已有模擬正在進行中")
                    return
            except RuntimeError:
                # 線程已被刪除，繼續執行
                pass

        # 重置線程引用
        self.mcThread = None
        self.mcWorker = None

        # 禁用深色模式切換
        self.dark_mode_action.setEnabled(False)

        # 禁用分頁切換
        self.tabs_results.setEnabled(False)
        self.main_tabs.setEnabled(False)

        # 禁用菜單欄
        self.menuBar().setEnabled(False)

        self.mc_run_button.setEnabled(False)
        roleKey = (
            "newbie"
            if self.mc_role_select_combo.currentText() == "新手 (Novice)"
            else "expert"
        )
        iterations = self.mc_iterations_spinbox.value()
        self.mc_progress_bar.setMaximum(iterations)
        self.mc_progress_bar.setValue(0)

        self.mcThread = QThread()
        self.mcWorker = MonteCarloWorker(
            self.mergedWbs, self.mergedGraph, roleKey, iterations
        )
        self.mcWorker.moveToThread(self.mcThread)

        # 連接信號
        self.mcThread.started.connect(self.mcWorker.run)
        self.mcWorker.progress.connect(self.mc_progress_bar.setValue)
        self.mcWorker.finished.connect(self.simulation_finished)
        self.mcWorker.finished.connect(self.mcThread.quit)
        self.mcWorker.finished.connect(self.mcWorker.deleteLater)

        # 確保線程完全結束後清理
        self.mcThread.finished.connect(lambda: setattr(self, "mcThread", None))
        self.mcThread.finished.connect(self.mcThread.deleteLater)

        self.mcThread.start()

    def simulation_finished(self, results: list[float]) -> None:
        """模擬完成後處理結果"""
        try:
            self.mc_run_button.setEnabled(True)

            # 重新啟用深色模式切換
            self.dark_mode_action.setEnabled(True)

            # 重新啟用分頁切換
            self.tabs_results.setEnabled(True)
            self.main_tabs.setEnabled(True)

            # 重新啟用菜單欄
            self.menuBar().setEnabled(True)

            # 注意：線程引用將由信號連接自動清理，不要在這裡手動設置為 None
            # 這是因為 lambda: setattr(self, 'mcThread', None) 會在線程完全結束後執行

            if not results:
                QMessageBox.information(self, "模擬完成", "無有效結果")
                return

            # 繪製結果
            self.plot_results(results)

            # 額外確保 UI 更新
            QApplication.processEvents()

            # 強制更新蒙地卡羅分頁
            self.tab_monte_carlo.update()
            self.tab_monte_carlo.repaint()
        except (ValueError, RuntimeError) as e:
            # 即使處理結果時出錯，也要確保重新啟用控制項
            self.mc_run_button.setEnabled(True)
            self.dark_mode_action.setEnabled(True)
            self.tabs_results.setEnabled(True)
            self.main_tabs.setEnabled(True)
            self.menuBar().setEnabled(True)
            QMessageBox.critical(self, "錯誤", f"處理模擬結果時發生錯誤：{e}")

    def on_chart_mode_changed(self):
        """當圖表模式改變時重新繪製圖表"""
        if hasattr(self, "mcLastResults") and self.mcLastResults:
            self.plot_results(self.mcLastResults)

    def plot_results(self, results: list[float]) -> None:
        """顯示模擬結果"""
        # 保存結果以便深色模式切換時重繪
        self.mcLastResults = results

        # 設定中文字體
        plt.rcParams["font.sans-serif"] = [
            "Microsoft JhengHei",
            "SimHei",
            "Arial Unicode MS",
            "sans-serif",
        ]
        plt.rcParams["axes.unicode_minus"] = False

        arr = np.array(results, dtype=float)
        avg = float(arr.mean())
        std = float(arr.std())
        p50 = float(np.percentile(arr, 50))
        p85 = float(np.percentile(arr, 85))
        p95 = float(np.percentile(arr, 95))

        self.mc_mean_label.setText(f"平均總工時：{avg:.2f}")
        self.mc_std_label.setText(f"標準差：{std:.2f}")
        self.mc_p50_label.setText(f"50% 完成機率：{p50:.2f}")
        self.mc_p85_label.setText(f"85% 完成機率：{p85:.2f}")
        self.mc_p95_label.setText(f"95% 完成機率：{p95:.2f}")

        self.mcFigure.clear()
        ax = self.mcFigure.add_subplot(111)

        # 根據深色模式設定顏色
        if self.isDarkMode:
            bar_color = "lightblue"
            edge_color = "white"
            text_color = "white"
            # 設定圖表背景為深色
            self.mcFigure.patch.set_facecolor("#2b2b2b")
            ax.set_facecolor("#2b2b2b")
        else:
            bar_color = "skyblue"
            edge_color = "black"
            text_color = "black"
            # 設定圖表背景為淺色
            self.mcFigure.patch.set_facecolor("white")
            ax.set_facecolor("white")

        # 獲取當前選擇的圖表模式
        chart_mode = self.mc_chart_mode_combo.currentText()
        is_density_mode = chart_mode == "密度模式"

        # 根據模式繪製不同的直方圖
        if is_density_mode:
            # 密度模式：使用密度歸一化，並繪製KDE曲線
            n, bins, patches = ax.hist(
                arr,
                bins=25,
                color=bar_color,
                edgecolor=edge_color,
                alpha=0.8,
                rwidth=0.9,
                density=True,  # 密度歸一化
                label="直方圖",
            )

            # 計算並繪製KDE曲線
            try:
                if len(arr) > 1:  # 確保有足夠的數據點計算KDE
                    kde = gaussian_kde(arr)

                    # 創建平滑的x軸數據點，範圍稍微超出數據範圍
                    x_min, x_max = arr.min(), arr.max()
                    x_range = x_max - x_min
                    x_smooth = np.linspace(
                        x_min - 0.1 * x_range, x_max + 0.1 * x_range, 200
                    )

                    # 計算KDE值
                    kde_values = kde(x_smooth)

                    # 設定KDE曲線顏色
                    if self.isDarkMode:
                        kde_color = "#ff6b6b"  # 紅色系，在深色背景下明顯
                        kde_alpha = 0.9
                    else:
                        kde_color = "#e74c3c"  # 深紅色，在淺色背景下明顯
                        kde_alpha = 0.8

                    # 繪製KDE曲線
                    ax.plot(
                        x_smooth,
                        kde_values,
                        color=kde_color,
                        linewidth=2.5,
                        alpha=kde_alpha,
                        label="KDE 密度曲線",
                    )

                    # 添加圖例
                    legend = ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
                    # 設定圖例文字顏色
                    legend.get_frame().set_facecolor(
                        "white" if not self.isDarkMode else "#404040"
                    )
                    legend.get_frame().set_edgecolor(text_color)
                    for text in legend.get_texts():
                        text.set_color(text_color)

            except (ValueError, np.linalg.LinAlgError) as e:
                # 如果KDE計算失敗，不中斷程序，但記錄錯誤
                print(f"KDE計算失敗: {e}")
                pass
        else:
            # 次數模式：不使用密度歸一化，顯示原始計數
            n, bins, patches = ax.hist(
                arr,
                bins=25,
                color=bar_color,
                edgecolor=edge_color,
                alpha=0.8,
                rwidth=0.9,
                density=False,  # 不使用密度歸一化，顯示次數
            )

        # 獲取模擬條件資訊
        role_text = self.mc_role_select_combo.currentText()
        iterations = self.mc_iterations_spinbox.value()

        # 設定標題，包含模擬條件和圖表模式
        title = (
            f"蒙地卡羅模擬結果 ({chart_mode})\n"
            f"分析對象: {role_text} | 模擬次數: {iterations:,} 次"
        )
        ax.set_title(title, color=text_color, fontsize=12, pad=15)

        ax.set_xlabel("工時 (小時)", color=text_color, fontsize=10)

        # 根據模式設定Y軸標籤
        if is_density_mode:
            ax.set_ylabel("密度", color=text_color, fontsize=10)
        else:
            ax.set_ylabel("次數", color=text_color, fontsize=10)

        # 設定刻度顏色
        ax.tick_params(colors=text_color)

        # 在圖表上添加統計資訊文字
        stats_text = f"平均: {avg:.1f}h\n標準差: {std:.1f}h\n中位數: {p50:.1f}h"
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            fontsize=9,
            bbox=dict(
                boxstyle="round",
                facecolor="white" if not self.isDarkMode else "#404040",
                alpha=0.8,
                edgecolor=text_color,
            ),
            color=text_color,
        )

        # 調整布局
        self.mcFigure.tight_layout()

        # 強制重繪和更新畫布
        self.mcCanvas.draw()
        self.mcCanvas.flush_events()

        # 確保 widget 更新
        self.mcCanvas.update()
        self.mcCanvas.repaint()

        # 處理所有待處理的事件
        QApplication.processEvents()

    def export_monte_carlo_chart(self, fmt="png"):
        """匯出蒙地卡羅模擬圖表"""
        if not hasattr(self, "mcFigure") or self.mcFigure is None:
            QMessageBox.warning(self, "警告", "請先執行蒙地卡羅模擬")
            return

        if not hasattr(self, "mcLastResults") or not self.mcLastResults:
            QMessageBox.warning(self, "警告", "沒有可匯出的模擬結果")
            return

        fileFilter = "PNG 圖片 (*.png)" if fmt == "png" else "SVG 向量圖 (*.svg)"
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出蒙地卡羅模擬圖表", "", fileFilter
        )

        if not path:
            return

        try:
            if not path.lower().endswith(f".{fmt}"):
                path += f".{fmt}"
            self.mcFigure.savefig(
                path, format=fmt, bbox_inches="tight", dpi=300, pad_inches=0.2
            )
            QMessageBox.information(self, "完成", f"已匯出蒙地卡羅圖表至：{path}")
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "錯誤", f"匯出圖檔時發生錯誤：{e}")

    def initialize_monte_carlo_chart(self):
        """初始化蒙地卡羅圖表，設定適當的背景色"""
        self.mcFigure.clear()
        ax = self.mcFigure.add_subplot(111)

        # 設定中文字體
        plt.rcParams["font.sans-serif"] = [
            "Microsoft JhengHei",
            "SimHei",
            "Arial Unicode MS",
            "sans-serif",
        ]
        plt.rcParams["axes.unicode_minus"] = False

        # 根據當前模式設定顏色
        if self.isDarkMode:
            text_color = "white"
            self.mcFigure.patch.set_facecolor("#2b2b2b")
            ax.set_facecolor("#2b2b2b")
        else:
            text_color = "black"
            self.mcFigure.patch.set_facecolor("white")
            ax.set_facecolor("white")

        # 設定空白圖表的標題和標籤
        ax.set_title("蒙地卡羅模擬結果\n(請先執行模擬)", color=text_color, fontsize=12)
        ax.set_xlabel("工時 (小時)", color=text_color, fontsize=10)
        ax.set_ylabel("次數", color=text_color, fontsize=10)  # 預設為次數模式

        # 設定刻度顏色
        ax.tick_params(colors=text_color)

        # 添加提示文字
        ax.text(
            0.5,
            0.5,
            "點擊「開始模擬」按鈕\n進行蒙地卡羅分析",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=14,
            color=text_color,
            alpha=0.6,
        )

        self.mcFigure.tight_layout()
        self.mcCanvas.draw()

    def runRcpspOptimization(self, showDialog: bool = True) -> dict[str, float] | None:
        """執行 RCPSP 資源排程並可選擇是否顯示結果對話框"""
        if self.mergedGraph is None or self.mergedWbs is None:
            QMessageBox.warning(self, "警告", "請先執行完整分析")
            return None
        if not self.resourcePath:
            QMessageBox.warning(self, "警告", "請先匯入 Resources 檔案")
            return None

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            cmpParams = config.get("cmp_params", {})
            durationField = cmpParams.get("default_duration_field", "Te_newbie")

            if durationField not in self.mergedWbs.columns:
                raise ValueError(f"WBS 缺少工期欄位 {durationField}")
            if "Category" not in self.mergedWbs.columns:
                raise ValueError('WBS 缺少 "Category" 欄位')
            if "ResourceDemand" not in self.mergedWbs.columns:
                raise ValueError('WBS 缺少 "ResourceDemand" 欄位')

            resourceCap = readResources(
                self.resourcePath, self.mergedWbs, durationField)
            if self.manualResourceCap:
                resourceCap.update(self.manualResourceCap)
            schedule = solveRcpsp(
                self.mergedGraph,
                self.mergedWbs,
                durationField=durationField,
                resourceField="Category",
                demandField="ResourceDemand",
                resourceCap=resourceCap,
            )

            if showDialog:
                self.showRcpspResult(schedule, durationField)
            return schedule

        except Exception as e:
            QMessageBox.critical(self, "排程失敗", f"執行 RCPSP 排程時發生錯誤：{e}")
            return None

    def showRcpspResult(self, schedule: dict[str, float], durationField: str) -> None:
        """以對話框方式顯示 RCPSP 排程結果"""
        projectEnd = schedule.get("ProjectEnd", 0)
        scheduleDf = self.mergedWbs[["Task ID", durationField]].copy()
        scheduleDf["Start"] = scheduleDf["Task ID"].map(schedule).fillna(0)
        scheduleDf["Finish"] = (
            scheduleDf["Start"] + scheduleDf[durationField].fillna(0)
        )
        resultText = (
            f"<b>RCPSP 排程結果 (總工期: {projectEnd:.2f} 小時):" "</b><br><br>"
        )
        resultText += "<table border='1' style='width:100%'>"
        resultText += "<tr><th>任務 ID</th><th>開始時間 (小時)</th></tr>"
        for task, startTime in sorted(schedule.items()):
            if task == "ProjectEnd":
                continue
            resultText += f"<tr><td>{task}</td><td>{startTime}</td></tr>"
        resultText += "</table>"

        dialog = QDialog(self)
        dialog.setWindowTitle("RCPSP 排程結果")
        layout = QVBoxLayout()
        textEdit = QTextEdit()
        textEdit.setHtml(resultText)
        textEdit.setReadOnly(True)
        layout.addWidget(textEdit)

        fig = self.drawRcpspGanttChart(
            scheduleDf,
            durationField,
            f"RCPSP 排程 (總工期: {projectEnd:.2f} 小時)",
        )
        canvas = FigureCanvas(fig)
        scrollArea = QScrollArea()
        scrollArea.setWidget(canvas)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMinimumHeight(400)
        layout.addWidget(scrollArea)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        buttonBox.accepted.connect(dialog.accept)
        layout.addWidget(buttonBox)
        dialog.setLayout(layout)
        dialog.resize(600, 500)
        dialog.exec_()

    def openResourceConfigDialog(self) -> None:
        """開啟資源容量設定對話框"""
        if self.mergedWbs is None or not self.resourcePath:
            QMessageBox.warning(self, "警告", "請先完成分析並匯入 Resources 檔案")
            return
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
            cmpParams = config.get("cmp_params", {})
            durationField = cmpParams.get("default_duration_field", "Te_newbie")
            resourceCap = readResources(
                self.resourcePath, self.mergedWbs, durationField)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"讀取資源資料失敗：{e}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("設定資源容量")
        form = QFormLayout(dialog)
        spinBoxes: dict[str, QSpinBox] = {}
        for group, cap in resourceCap.items():
            spin = QSpinBox()
            spin.setMinimum(1)
            spin.setValue(self.manualResourceCap.get(group, cap))
            form.addRow(QLabel(group), spin)
            spinBoxes[group] = spin

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttonBox)
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.rejected.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            self.manualResourceCap = {g: s.value() for g, s in spinBoxes.items()}


def main():
    app = QApplication(sys.argv)

    # 設置應用程式退出時清理所有 QThread
    app.setQuitOnLastWindowClosed(True)

    window = BirdmanQtApp()
    window.show()

    try:
        exit_code = app.exec_()
    finally:
        # 確保在應用程式退出時所有線程都被正確清理
        if hasattr(window, "mcThread") and window.mcThread is not None:
            try:
                if window.mcThread.isRunning():
                    window.mcThread.terminate()
                    window.mcThread.wait(2000)  # 等待2秒
            except (RuntimeError, AttributeError):
                pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
