# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
import json
import networkx as nx
from functools import partial

from .matplotlib_runtime import prepareMatplotlibForQt

prepareMatplotlibForQt()

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
    QDialog,
    QComboBox,
    QAction,
    QActionGroup,
    QDialogButtonBox,
    QScrollArea,
    QTextEdit,
    QProgressBar,
    QSpinBox,
)
from PyQt5.QtCore import Qt, QThread
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure
import pandas as pd

from .resource_processor import readResources
from .app_paths import loadProjectConfig, prepareQtApplication, saveProjectConfig
from .ui.dsm_editor import DsmEditor
from .ui.main_app.analysis_service import (
    buildAllCpmScenarioResults,
    buildCpmScenarioResult,
    loadAnalysisBundle,
)
from .ui.main_app.advanced_analysis_dialogs import (
    promptResourceCapacities,
    showFigureResultDialog,
)
from .ui.main_app.advanced_analysis_service import (
    buildRacpResultHtml,
    buildRcpspResultHtml,
    buildRcpspScheduleFrame,
    runRacpAnalysis,
)
from .ui.main_app.display_service import (
    TIME_MODE_OPTIONS,
    buildRoleStatusMessage,
    buildScenarioDisplayState,
    resolveTimeKey,
)
from .ui.main_app.chart_service import (
    createGanttFigure,
    createRacpBarChartFigure,
    createRcpspGanttFigure,
    initializeMonteCarloFigure,
    renderMonteCarloFigure,
)
from .ui.main_app.export_service import (
    exportDataFrameWithDialog,
    exportFigureWithDialog,
)
from .ui.main_app.graph_service import renderDependencyGraph
from .ui.main_app.helpers import (
    addNoColumn,
    buildDarkModeStylesheet,
    configureChartTheme,
    createCpmDisplayDf,
    getCriticalPathEdges,
)
from .ui.main_app.input_service import (
    FolderImportSelectionError,
    loadDsmPreview,
    loadFolderImportBundle,
    loadOptionalDsmForEditor,
    loadResourcesPreview,
    loadWbsPreview,
)
from .ui.main_app.settings_dialog import SettingsDialog
from .ui.main_app.workers import MonteCarloWorker, RcpspWorker
from .ui.shared import PandasModel


class BirdmanQtApp(QMainWindow):
    """Birdman 專案的 Qt 應用程式。"""

    def __init__(self) -> None:
        """初始化主視窗。"""
        super().__init__()
        self.setWindowTitle("Birdman Project 進階 GUI")
        # 設定更合適的初始窗口尺寸和最小尺寸
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.dsmPath = ""
        self.wbsPath = ""
        self.resourcePath = ""
        self.wbsDf: pd.DataFrame | None = None
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
        self.rcpspThread = None
        self.rcpspWorker = None
        self.rcpspLastSchedule = None
        self.rcpspLastDurationField = None
        self.rcpspResultDialog = None

        # CPM 分析相關資料
        self.cmpResult = None
        self.criticalPath = None
        self.mergedGraph = None
        self.mergedDsm = None
        # 儲存不同情境下的甘特圖資料
        self.ganttResults = {"newbie": {}, "expert": {}}
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
            config = loadProjectConfig()
            self.kParams = config.get("merge_k_params", self.defaultKParams)
        except (OSError, json.JSONDecodeError):
            # 檔案不存在或解析失敗時以預設值處理
            self.kParams = self.defaultKParams

        self.initUI()

    def configure_chart_theme(self):
        """統一設定所有圖表的顏色主題。"""
        configureChartTheme(self.isDarkMode)

    def buildDarkModeStylesheet(self) -> str:
        """建立深色模式樣式表。"""
        return buildDarkModeStylesheet()

    def get_critical_path_edges(self, graph, critical_path_nodes):
        """將關鍵路徑節點轉換為關鍵路徑邊線集合。"""
        return getCriticalPathEdges(graph, critical_path_nodes)

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

        if hasattr(self, "rcpspThread") and self.rcpspThread is not None:
            try:
                if self.rcpspThread.isRunning():
                    self.rcpspThread.quit()
                    self.rcpspThread.wait(2000)
            except RuntimeError:
                pass

        # 接受關閉事件
        event.accept()

    def initUI(self) -> None:
        """建立介面佈局與控制項。"""
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
        role_menu = menubar.addMenu("角色(R)")

        # 全域角色設定
        self.selected_role = 'newbie'  # 預設為新手

        # 建立角色選擇動作
        self.novice_action = QAction("新手 (Novice)", self)
        self.novice_action.setCheckable(True)
        self.novice_action.setChecked(True)  # 預設選中
        self.novice_action.triggered.connect(lambda: self.setGlobalRole('newbie'))

        self.expert_action = QAction("專家 (Expert)", self)
        self.expert_action.setCheckable(True)
        self.expert_action.triggered.connect(lambda: self.setGlobalRole('expert'))

        # 依賴關係編輯器
        dsm_editor_action = QAction("依賴關係編輯器", self)
        dsm_editor_action.triggered.connect(self.openDsmEditor)
        file_menu.addAction(dsm_editor_action)
        file_menu.addSeparator()

        # 建立動作群組確保單選
        self.role_action_group = QActionGroup(self)
        self.role_action_group.addAction(self.novice_action)
        self.role_action_group.addAction(self.expert_action)

        role_menu.addAction(self.novice_action)
        role_menu.addAction(self.expert_action)

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
        self.cpmDisplayCombo.addItems(TIME_MODE_OPTIONS)
        self.cpmDisplayCombo.currentIndexChanged.connect(self.update_cpm_display)
        cpm_top_layout.addWidget(self.cpmDisplayCombo)

        cpm_top_layout.addStretch()
        self.tab_cmp_result.layout().addLayout(cpm_top_layout)
        self.tab_cmp_result.layout().addWidget(self.cmp_result_view)
        self.tab_gantt_chart.setLayout(QVBoxLayout())
        self.tab_advanced_analysis.setLayout(QVBoxLayout())

        # --- RACP 人力配置區塊 ---
        racp_group = QWidget()
        racp_layout = QVBoxLayout()
        racp_group.setLayout(racp_layout)

        racp_title = QLabel("<h3>RACP 最小人力配置 (RACP Minimum Workforce)</h3>")
        racp_layout.addWidget(racp_title)

        # 截止時間輸入
        deadline_layout = QHBoxLayout()
        deadline_layout.addWidget(QLabel("專案截止時間 (小時):"))
        self.racpDeadlineSpinBox = QSpinBox()
        self.racpDeadlineSpinBox.setMinimum(1)
        self.racpDeadlineSpinBox.setMaximum(9999)
        self.racpDeadlineSpinBox.setValue(100)
        deadline_layout.addWidget(self.racpDeadlineSpinBox)
        deadline_layout.addStretch()
        racp_layout.addLayout(deadline_layout)

        self.runRacpButton = QPushButton("執行 RACP 人力分析")
        racp_layout.addWidget(self.runRacpButton)

        # RACP 結果顯示區域
        self.racpResultLabel = QLabel("尚未執行 RACP 分析")
        self.racpResultLabel.setStyleSheet("padding: 10px; border: 1px solid gray; background-color: #f0f0f0;")
        racp_layout.addWidget(self.racpResultLabel)

        racp_layout.addStretch()
        self.tab_advanced_analysis.layout().addWidget(racp_group)

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

        self.rcpspProgressBar = QProgressBar()
        self.rcpspProgressBar.setVisible(False)
        self.rcpspProgressBar.setTextVisible(False)
        rcpsp_layout.addWidget(self.rcpspProgressBar)

        self.rcpspStatusLabel = QLabel("尚未執行 RCPSP 排程")
        self.rcpspStatusLabel.setStyleSheet(
            "padding: 10px; border: 1px solid gray; background-color: #f0f0f0;"
        )
        rcpsp_layout.addWidget(self.rcpspStatusLabel)

        rcpsp_layout.addStretch()
        self.tab_advanced_analysis.layout().addWidget(rcpsp_group)

        # --- 蒙地卡羅模擬分頁 ---
        mc_main_layout = QVBoxLayout()
        self.tab_monte_carlo.setLayout(mc_main_layout)

        mc_top_layout = QHBoxLayout()
        mc_main_layout.addLayout(mc_top_layout)

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
        self.runRcpspButton.clicked.connect(
            lambda checked=False: self.runRcpspOptimization(
                checked=checked, showDialog=True
            )
        )
        self.configResourcesButton.clicked.connect(self.openResourceConfigDialog)
        self.runRacpButton.clicked.connect(self.runRacpOptimization)

        # 甘特圖情境切換下拉選單
        gantt_top_layout = QHBoxLayout()

        # 顯示模式選擇
        self.ganttDisplayCombo = QComboBox()
        self.ganttDisplayCombo.addItems(TIME_MODE_OPTIONS)
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

    def chooseDsm(self) -> None:
        """選擇 DSM 檔案並預覽。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 DSM 檔案", "", "CSV Files (*.csv)"
        )
        if path:
            self.dsmPath = path
            self.dsm_path_label.setText(path)
            try:
                dsm = loadDsmPreview(path)
                model = PandasModel(dsm.head(100), dsmMode=True)
                self.dsm_preview.setModel(model)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, "錯誤", f"DSM 載入失敗：{e}")

    def chooseWbs(self) -> None:
        """選擇 WBS 檔案並預覽。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 WBS 檔案", "", "CSV Files (*.csv)"
        )
        if path:
            self.wbsPath = path
            self.wbs_path_label.setText(path)
            try:
                wbs, wbs_display = loadWbsPreview(path)
                self.wbsDf = wbs.copy()
                model = PandasModel(wbs_display.head(100))
                self.wbs_preview.setModel(model)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, "錯誤", f"WBS 載入失敗：{e}")

    def chooseResources(self) -> None:
        """選擇 Resources 檔案並預覽。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 Resources 檔案", "", "CSV Files (*.csv)"
        )
        if path:
            try:
                resources = loadResourcesPreview(path)
                model = PandasModel(resources.head(100))
                self.resources_preview.setModel(model)
                self.resourcePath = path
                self.resources_path_label.setText(path)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, "錯誤", f"Resources 載入失敗：{e}")

    def openDsmEditor(self) -> None:
        """開啟視覺化依賴關係編輯器"""
        if self.wbsDf is None:
            QMessageBox.warning(self, "警告", "請先匯入 WBS 檔案")
            return
        try:
            dsm_df = loadOptionalDsmForEditor(getattr(self, "dsmPath", ""))
        except (OSError, pd.errors.ParserError, ValueError) as e:
            QMessageBox.critical(self, "錯誤", f"DSM 載入失敗：{e}")
            return

        editor = DsmEditor(
            self.wbsDf.copy(),
            self,
            dsmDf=dsm_df,
            wbsPath=getattr(self, "wbsPath", None),
            dsmPath=getattr(self, "dsmPath", None) or None,
        )
        editor.exec_()

    def import_from_folder(self):
        """從資料夾匯入 WBS、DSM，若有 Resources 亦一併匯入"""
        folder = QFileDialog.getExistingDirectory(self, "選擇資料夾", "")
        if not folder:
            return
        try:
            bundle = loadFolderImportBundle(folder)
        except FolderImportSelectionError as e:
            QMessageBox.warning(self, "錯誤", str(e))
            return
        except (OSError, pd.errors.ParserError, ValueError):
            QMessageBox.critical(
                self, "錯誤", "資料夾中的 WBS 或 DSM 檔案格式不正確，請檢查檔案內容。"
            )
            return

        self.wbsDf = bundle.wbs.copy()
        self.wbsPath = bundle.wbsPath
        self.dsmPath = bundle.dsmPath
        self.wbs_path_label.setText(bundle.wbsPath)
        self.dsm_path_label.setText(bundle.dsmPath)
        model_wbs = PandasModel(bundle.wbsDisplay.head(100))
        self.wbs_preview.setModel(model_wbs)
        model_dsm = PandasModel(bundle.dsm.head(100), dsmMode=True)
        self.dsm_preview.setModel(model_dsm)
        self.resourcePath = bundle.resourcePath
        self.resources_path_label.setText(bundle.resourcePath)
        self.resources_preview.setModel(PandasModel(bundle.resources.head(100)))

        for warningMessage in bundle.warnings:
            QMessageBox.warning(self, "錯誤", warningMessage)

    def runAnalysis(self, show_notification: bool = True) -> bool:
        """執行資料分析並更新各分頁。

        Args:
            show_notification: 是否顯示完成通知。

        Returns:
            bool: 分析成功則為 ``True``，失敗為 ``False``。
        """
        self.notify = show_notification
        try:
            analysisBundle = loadAnalysisBundle(
                self.dsmPath,
                self.wbsPath,
                self.kParams,
            )
            dsm = analysisBundle.sourceDsm
            wbs = analysisBundle.sourceWbs
            self.wbsDf = wbs.copy()
            # 預覽原始資料 (保留在預覽區，但不在分析結果顯示)
            model_dsm = PandasModel(dsm.head(100), dsmMode=True)
            self.dsm_preview.setModel(model_dsm)
            wbs_with_no = self._add_no_column(wbs)
            model_wbs = PandasModel(wbs_with_no.head(100))
            self.wbs_preview.setModel(model_wbs)

            # 統一設定圖表主題顏色
            self.configure_chart_theme()

            self.sortedWbs = self._add_no_column(analysisBundle.sortedWbs)
            self.sortedDsm = analysisBundle.sortedDsm
            self.graph = analysisBundle.graph
            self.mergedWbs = self._add_no_column(analysisBundle.mergedWbs)
            self.mergedDsm = analysisBundle.mergedDsm
            self.mergedGraph = analysisBundle.mergedGraph
            self.scc_map = analysisBundle.sccMap
            self.layer_map = analysisBundle.layerMap
            self.merged_scc_map = analysisBundle.mergedSccMap
            self.merged_layer_map = analysisBundle.mergedLayerMap

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
            return False

    def _add_no_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """若無 ``No.`` 欄位則新增連續編號。"""
        return addNoColumn(df)

    def _create_cpm_display_df(self, full_results_df, roleKey, time_key):
        """產生精簡版 CPM 結果表"""
        return createCpmDisplayDf(full_results_df, roleKey, time_key)

    def exportSortedWbs(self) -> None:
        """匯出排序後的 WBS。"""
        exportDataFrameWithDialog(
            self,
            self.sortedWbs,
            title="匯出排序後 WBS",
            defaultName="sorted_wbs.csv",
            emptyMessage="請先執行分析產生排序後的 WBS",
            successMessage="排序後 WBS 已匯出",
        )

    def exportMergedWbs(self, fmt="csv"):
        """匯出合併後的 WBS"""
        exportDataFrameWithDialog(
            self,
            self.mergedWbs,
            title="匯出合併 WBS",
            fmt=fmt,
            emptyMessage="請先執行分析",
        )

    def exportSortedDsm(self) -> None:
        """匯出排序後的 DSM。"""
        exportDataFrameWithDialog(
            self,
            self.sortedDsm,
            title="匯出排序後 DSM",
            defaultName="sorted_dsm.csv",
            emptyMessage="請先執行分析產生排序後的 DSM",
            includeIndex=True,
            successMessage="排序後 DSM 已匯出",
        )

    def exportMergedDsm(self, fmt="csv"):
        """匯出合併後的 DSM"""
        exportDataFrameWithDialog(
            self,
            self.mergedDsm,
            title="匯出合併 DSM",
            fmt=fmt,
            emptyMessage="請先執行分析",
        )

    def exportGraph(self, fmt="png"):
        """匯出原始依賴關係圖"""
        exportFigureWithDialog(
            self,
            self.graphCanvas.figure if self.graph is not None and self.graphCanvas is not None else None,
            title="匯出依賴關係圖",
            fmt=fmt,
            emptyMessage="請先執行分析",
            successMessage="已匯出依賴關係圖至：{path}",
        )

    def exportMergedGraph(self, fmt="png"):
        """匯出合併後依賴關係圖"""
        exportFigureWithDialog(
            self,
            (
                self.mergedGraphCanvas.figure
                if self.mergedGraph is not None and self.mergedGraphCanvas is not None
                else None
            ),
            title="匯出合併後依賴關係圖",
            fmt=fmt,
            emptyMessage="請先執行分析",
            successMessage="已匯出合併後依賴圖至：{path}",
        )

    def runCmpAnalysis(self):
        """執行 CPM 分析"""
        if not (hasattr(self, "mergedGraph") and hasattr(self, "mergedWbs")):
            QMessageBox.warning(self, "警告", "請先執行基本分析")
            return

        try:
            timeKey = resolveTimeKey(self.ganttDisplayCombo.currentText())
            wbsWithCpm = self.mergedWbs.copy()
            self.ganttResults = {"newbie": {}, "expert": {}}
            self.ganttResults[self.selected_role][timeKey] = buildCpmScenarioResult(
                wbsWithCpm,
                self.mergedGraph,
                self.selected_role,
                timeKey,
            )

            self.update_gantt_display()
            if self.notify:
                QMessageBox.information(self, 'CPM 分析完成', 'CPM 分析已完成')
        except (ValueError, KeyError, nx.NetworkXError) as e:
            QMessageBox.critical(self, '錯誤', f'CPM 分析失敗：{e}')

    def run_full_analysis(self):
        """執行所有情境的 CPM 分析"""
        success = self.runAnalysis(show_notification=False)  # 不顯示基本分析通知
        if not success:
            return

        self.ganttResults = buildAllCpmScenarioResults(
            self.mergedWbs.copy(),
            self.mergedGraph,
        )

        self.ganttDisplayCombo.setCurrentIndex(0)
        self.cpmDisplayCombo.setCurrentIndex(0)
        self.update_gantt_display()

        total = sum(len(v) for v in self.ganttResults.values())
        QMessageBox.information(
            self,
            "完整分析完成",
            f"已完成所有情境的 CPM 分析，共生成 {total} 種情境結果",
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
            return createGanttFigure(cpmData, durations, title, wbsDf)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"甘特圖繪製失敗：{e}")
            return Figure()

    def drawRcpspGanttChart(self, scheduleDf, durationField, title):
        """繪製 RCPSP 甘特圖並回傳 Figure"""
        try:
            return createRcpspGanttFigure(scheduleDf, durationField, title)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"RCPSP 甘特圖繪製失敗：{e}")
            return Figure()

    def update_gantt_display(self):
        """根據選擇的角色與時間模式更新顯示"""
        mode_text = self.ganttDisplayCombo.currentText()
        time_key = resolveTimeKey(mode_text)

        if hasattr(self, "cpmDisplayCombo"):
            self.cpmDisplayCombo.blockSignals(True)
            if self.cpmDisplayCombo.currentText() != mode_text:
                self.cpmDisplayCombo.setCurrentText(mode_text)
            self.cpmDisplayCombo.blockSignals(False)

        roleKey = self.selected_role
        if roleKey not in self.ganttResults or time_key not in self.ganttResults[roleKey]:
            return

        scenarioResult = self.ganttResults[roleKey][time_key]
        self.cmpResult = scenarioResult.wbsWithCpm

        displayDf = self._create_cpm_display_df(
            scenarioResult.wbsWithCpm,
            roleKey,
            time_key,
        )
        displayState = buildScenarioDisplayState(
            roleKey=roleKey,
            timeKey=time_key,
            projectEnd=scenarioResult.projectEnd,
            displayDf=displayDf,
        )
        self.currentDisplayCpmDf = displayState.displayDf
        self.criticalPath = scenarioResult.criticalPath

        # 更新關鍵路徑後，重繪合併後的依賴圖以顯示關鍵路徑
        self.redraw_merged_graph()

        self.cmp_result_view.setModel(PandasModel(self.currentDisplayCpmDf.head(100)))
        self.total_hours_label.setText(displayState.totalHoursText)

        # 先清除舊的圖表
        layout = self.gantt_container.layout()
        for i in reversed(range(layout.count())):
            oldWidget = layout.itemAt(i).widget()
            if oldWidget:
                oldWidget.setParent(None)

        # 重新產生甘特圖並加入佈局
        self.ganttFigure = self.drawGanttChart(
            scenarioResult.cpmDf,
            scenarioResult.durations,
            displayState.figureTitle,
            scenarioResult.wbsWithCpm,
        )
        self.ganttCanvas = FigureCanvas(self.ganttFigure)
        scrollArea = QScrollArea()
        scrollArea.setWidget(self.ganttCanvas)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setMinimumHeight(1000)
        self.ganttCanvas.setMinimumSize(
            1200,
            max(1000, len(scenarioResult.wbsWithCpm) * 35),
        )

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
        exportDataFrameWithDialog(
            self,
            self.cmpResult,
            title="匯出 CPM 分析結果",
            emptyMessage="請先執行 CPM 分析",
            successMessage="已匯出 CPM 結果：{path}",
        )

    def export_cpm_results(self, fmt="csv"):
        """匯出目前顯示的 CPM 精簡報告"""
        exportDataFrameWithDialog(
            self,
            self.currentDisplayCpmDf,
            title="匯出 CPM 分析結果",
            fmt=fmt,
            emptyMessage="沒有可匯出的 CPM 結果",
        )

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
                config = loadProjectConfig()
                config["merge_k_params"] = self.kParams
                saveProjectConfig(config)
            except (OSError, json.JSONDecodeError) as e:
                QMessageBox.warning(self, "警告", f"無法保存設定：{e}")

    def setGlobalRole(self, role):
        """設定全域角色並更新相關顯示"""
        self.selected_role = role
        self.statusBar().showMessage(buildRoleStatusMessage(role), 3000)
        self.update_gantt_display()

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
                self.setStyleSheet(self.buildDarkModeStylesheet())
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
                config = loadProjectConfig()
                viz_params = config.get("visualization_params", {})

                # 重新建立原始圖
                self.graphFigure, self.graphCanvas = renderDependencyGraph(
                    graph=self.graph,
                    sccMap=self.scc_map,
                    layerMap=self.layer_map,
                    vizParams=viz_params,
                    layout=self.graph_container_layout,
                    container=self.graph_container,
                )

                # 重新建立合併後圖
                if self.mergedGraph is not None:
                    # 計算關鍵路徑邊線
                    critical_path_edges = None
                    if hasattr(self, "criticalPath") and self.criticalPath:
                        critical_path_edges = self.get_critical_path_edges(
                            self.mergedGraph, self.criticalPath
                        )

                    self.mergedGraphFigure, self.mergedGraphCanvas = renderDependencyGraph(
                        graph=self.mergedGraph,
                        sccMap=self.merged_scc_map,
                        layerMap=self.merged_layer_map,
                        vizParams=viz_params,
                        layout=self.merged_graph_container_layout,
                        container=self.merged_graph_container,
                        criticalPathEdges=critical_path_edges,
                    )
            except Exception as e:  # pylint: disable=broad-except
                QMessageBox.warning(self, "警告", f"圖表重繪失敗：{e}")

    def redraw_merged_graph(self):
        """專門重繪合併後的依賴關係圖（包含關鍵路徑資訊）"""
        if not hasattr(self, "mergedGraph") or self.mergedGraph is None:
            return

        try:
            config = loadProjectConfig()
            viz_params = config.get("visualization_params", {})

            # 計算關鍵路徑邊線
            critical_path_edges = None
            if hasattr(self, "criticalPath") and self.criticalPath:
                critical_path_edges = self.get_critical_path_edges(
                    self.mergedGraph, self.criticalPath
                )

            # 重新建立合併後圖
            self.mergedGraphFigure, self.mergedGraphCanvas = renderDependencyGraph(
                graph=self.mergedGraph,
                sccMap=self.merged_scc_map,
                layerMap=self.merged_layer_map,
                vizParams=viz_params,
                layout=self.merged_graph_container_layout,
                container=self.merged_graph_container,
                criticalPathEdges=critical_path_edges,
            )

        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.warning(self, "警告", f"合併後依賴圖重繪失敗：{e}")

    def exportGanttChart(self, fmt="png"):
        """匯出甘特圖"""
        exportFigureWithDialog(
            self,
            self.ganttFigure,
            title="匯出甘特圖",
            fmt=fmt,
            emptyMessage="請先執行 CPM 分析",
            successMessage="已匯出甘特圖至：{path}",
            savefigKwargs={"pad_inches": 0.5},
        )

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
        roleKey = self.selected_role
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

        stats = renderMonteCarloFigure(
            self.mcFigure,
            results,
            isDarkMode=self.isDarkMode,
            chartMode=self.mc_chart_mode_combo.currentText(),
            selectedRole=self.selected_role,
            iterations=self.mc_iterations_spinbox.value(),
        )

        self.mc_mean_label.setText(f"平均總工時：{stats['average']:.2f}")
        self.mc_std_label.setText(f"標準差：{stats['std']:.2f}")
        self.mc_p50_label.setText(f"50% 完成機率：{stats['p50']:.2f}")
        self.mc_p85_label.setText(f"85% 完成機率：{stats['p85']:.2f}")
        self.mc_p95_label.setText(f"95% 完成機率：{stats['p95']:.2f}")

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
        if not hasattr(self, "mcLastResults") or not self.mcLastResults:
            QMessageBox.warning(self, "警告", "沒有可匯出的模擬結果")
            return

        exportFigureWithDialog(
            self,
            self.mcFigure,
            title="匯出蒙地卡羅模擬圖表",
            fmt=fmt,
            emptyMessage="請先執行蒙地卡羅模擬",
            successMessage="已匯出蒙地卡羅圖表至：{path}",
            savefigKwargs={"pad_inches": 0.2},
        )

    def initialize_monte_carlo_chart(self):
        """初始化蒙地卡羅圖表，設定適當的背景色"""
        initializeMonteCarloFigure(self.mcFigure, isDarkMode=self.isDarkMode)
        self.mcCanvas.draw()

    def runRcpspOptimization(
        self,
        checked: bool = False,
        *,
        showDialog: bool = True,
    ) -> dict[str, float] | None:
        """執行 RCPSP 資源排程並可選擇是否顯示結果對話框。

        Args:
            checked: 保留給 Qt ``clicked`` 訊號的布林參數，不參與排程邏輯。
            showDialog: 是否在完成後顯示結果視窗。
        """
        _ = checked
        try:
            rcpspContext = self._buildRcpspContext()
        except Exception as e:
            self._setRcpspStatus(f"RCPSP 失敗：{e}", isError=True)
            QMessageBox.critical(self, "排程失敗", f"執行 RCPSP 排程時發生錯誤：{e}")
            return None

        if not showDialog:
            try:
                from .rcpsp_solver import solveRcpsp

                schedule = solveRcpsp(
                    self.mergedGraph,
                    self.mergedWbs,
                    durationField=rcpspContext["durationField"],
                    resourceField=rcpspContext["resourceField"],
                    demandField="ResourceDemand",
                    resourceCap=rcpspContext["resourceCap"],
                )
            except Exception as e:
                self._setRcpspStatus(f"RCPSP 失敗：{e}", isError=True)
                QMessageBox.critical(self, "排程失敗", f"執行 RCPSP 排程時發生錯誤：{e}")
                return None

            self.rcpspLastSchedule = schedule
            self.rcpspLastDurationField = rcpspContext["durationField"]
            self._setRcpspStatus(
                f"RCPSP 完成，總工期：{schedule.get('ProjectEnd', 0):.2f} 小時",
                isSuccess=True,
            )
            return schedule

        if self.rcpspThread is not None:
            try:
                if self.rcpspThread.isRunning():
                    QMessageBox.warning(self, "警告", "RCPSP 排程正在計算中")
                    return None
            except RuntimeError:
                pass

        self._setRcpspBusy(True)
        self._setRcpspStatus("RCPSP 計算中，請稍候（最多約 10 秒）...", isBusy=True)
        self.rcpspLastDurationField = rcpspContext["durationField"]

        self.rcpspThread = QThread()
        self.rcpspWorker = RcpspWorker(
            self.mergedGraph,
            self.mergedWbs,
            rcpspContext["durationField"],
            rcpspContext["resourceField"],
            "ResourceDemand",
            rcpspContext["resourceCap"],
        )
        self.rcpspWorker.moveToThread(self.rcpspThread)
        self.rcpspThread.started.connect(self.rcpspWorker.run)
        self.rcpspWorker.finished.connect(self._handleRcpspFinished)
        self.rcpspWorker.failed.connect(self._handleRcpspFailed)
        self.rcpspWorker.finished.connect(self.rcpspThread.quit)
        self.rcpspWorker.failed.connect(self.rcpspThread.quit)
        self.rcpspWorker.finished.connect(self.rcpspWorker.deleteLater)
        self.rcpspWorker.failed.connect(self.rcpspWorker.deleteLater)
        self.rcpspThread.finished.connect(self.rcpspThread.deleteLater)
        self.rcpspThread.finished.connect(lambda: setattr(self, "rcpspThread", None))
        self.rcpspThread.finished.connect(lambda: setattr(self, "rcpspWorker", None))
        self.rcpspThread.start()
        return None

    def _buildRcpspContext(self) -> dict[str, object]:
        """整理 RCPSP 執行所需參數。"""
        if self.mergedGraph is None or self.mergedWbs is None:
            raise ValueError("請先執行完整分析")
        if not self.resourcePath:
            raise ValueError("請先匯入 Resources 檔案")

        config = loadProjectConfig()
        cmpParams = config.get("cmp_params", {})
        durationField = cmpParams.get("default_duration_field", "Te_newbie")
        eligibleField = "Eligible_Groups"
        resourceField = (
            eligibleField
            if eligibleField in self.mergedWbs.columns
            and self.mergedWbs[eligibleField].fillna("").astype(str).str.strip().ne("").any()
            else "Property"
        )

        if durationField not in self.mergedWbs.columns:
            raise ValueError(f"WBS 缺少工期欄位 {durationField}")
        if resourceField not in self.mergedWbs.columns:
            raise ValueError('WBS 缺少 "Eligible_Groups" 或 "Property" 欄位')
        if "ResourceDemand" not in self.mergedWbs.columns:
            raise ValueError('WBS 缺少 "ResourceDemand" 欄位')

        resourceCap = readResources(self.resourcePath, self.mergedWbs, durationField)
        if self.manualResourceCap:
            resourceCap.update(self.manualResourceCap)

        return {
            "durationField": durationField,
            "resourceField": resourceField,
            "resourceCap": resourceCap,
        }

    def _setRcpspBusy(self, isBusy: bool) -> None:
        """更新 RCPSP 執行中的 UI 狀態。"""
        self.runRcpspButton.setEnabled(not isBusy)
        self.configResourcesButton.setEnabled(not isBusy)
        self.rcpspProgressBar.setVisible(isBusy)
        if isBusy:
            self.rcpspProgressBar.setRange(0, 0)
        else:
            self.rcpspProgressBar.setRange(0, 1)
            self.rcpspProgressBar.setValue(0)

    def _setRcpspStatus(
        self,
        message: str,
        *,
        isSuccess: bool = False,
        isError: bool = False,
        isBusy: bool = False,
    ) -> None:
        """更新 RCPSP 狀態文字與樣式。"""
        if isError:
            style = "padding: 10px; border: 1px solid #c62828; background-color: #fdecea;"
        elif isSuccess:
            style = "padding: 10px; border: 1px solid green; background-color: #e8f5e8;"
        elif isBusy:
            style = "padding: 10px; border: 1px solid #1565c0; background-color: #e3f2fd;"
        else:
            style = "padding: 10px; border: 1px solid gray; background-color: #f0f0f0;"
        self.rcpspStatusLabel.setText(message)
        self.rcpspStatusLabel.setStyleSheet(style)

    def _handleRcpspFinished(self, schedule: dict[str, float]) -> None:
        """處理 RCPSP 成功結果。"""
        self._setRcpspBusy(False)
        self.rcpspLastSchedule = schedule
        self._setRcpspStatus(
            f"RCPSP 完成，總工期：{schedule.get('ProjectEnd', 0):.2f} 小時，結果視窗已開啟",
            isSuccess=True,
        )
        durationField = self.rcpspLastDurationField or "Te_newbie"
        self.showRcpspResult(schedule, durationField)

    def _handleRcpspFailed(self, errorMessage: str) -> None:
        """處理 RCPSP 失敗結果。"""
        self._setRcpspBusy(False)
        self._setRcpspStatus(f"RCPSP 失敗：{errorMessage}", isError=True)
        QMessageBox.critical(self, "排程失敗", f"執行 RCPSP 排程時發生錯誤：{errorMessage}")

    def runRacpOptimization(self) -> None:
        """執行 RACP 最小人力配置分析"""
        try:
            deadline = self.racpDeadlineSpinBox.value()
            result, _durationField = runRacpAnalysis(
                self.mergedGraph,
                self.mergedWbs,
                deadline,
            )
            self.showRacpResult(result, deadline)
        except Exception as e:
            QMessageBox.critical(self, "RACP 分析失敗", f"執行 RACP 分析時發生錯誤：{e}")

    def showRacpResult(self, result: dict[str, int], deadline: int) -> None:
        """顯示 RACP 分析結果"""
        result_text = buildRacpResultHtml(result, deadline)
        self.racpResultLabel.setText(result_text)
        self.racpResultLabel.setStyleSheet("padding: 10px; border: 1px solid green; background-color: #e8f5e8;")
        showFigureResultDialog(
            self,
            "RACP 人力配置結果",
            result_text,
            createRacpBarChartFigure(result, deadline),
            textMaximumHeight=150,
        )

    def showRcpspResult(self, schedule: dict[str, float], durationField: str) -> None:
        """以對話框方式顯示 RCPSP 排程結果"""
        if self.mergedWbs is None:
            raise ValueError("目前沒有可顯示的 RCPSP 資料")
        projectEnd = schedule.get("ProjectEnd", 0)
        scheduleDf = buildRcpspScheduleFrame(self.mergedWbs, schedule, durationField)
        fig = self.drawRcpspGanttChart(
            scheduleDf,
            durationField,
            f"RCPSP 排程 (總工期: {projectEnd:.2f} 小時)",
        )
        self.rcpspResultDialog = showFigureResultDialog(
            self,
            "RCPSP 排程結果",
            buildRcpspResultHtml(schedule),
            fig,
            figureScrollable=True,
            existingDialog=self.rcpspResultDialog,
            onDialogClosed=lambda: setattr(self, "rcpspResultDialog", None),
            floating=True,
        )

    def openResourceConfigDialog(self) -> None:
        """開啟資源容量設定對話框"""
        if self.mergedWbs is None or not self.resourcePath:
            QMessageBox.warning(self, "警告", "請先完成分析並匯入 Resources 檔案")
            return
        try:
            config = loadProjectConfig()
            cmpParams = config.get("cmp_params", {})
            durationField = cmpParams.get("default_duration_field", "Te_newbie")
            resourceCap = readResources(
                self.resourcePath, self.mergedWbs, durationField)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"讀取資源資料失敗：{e}")
            return

        updatedCap = promptResourceCapacities(self, resourceCap, self.manualResourceCap)
        if updatedCap is not None:
            self.manualResourceCap = updatedCap


def main():
    """啟動 Birdman Qt 應用程式。"""
    prepareQtApplication()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = BirdmanQtApp()
    window.show()

    try:
        exit_code = app.exec_()
    finally:
        if hasattr(window, "mcThread") and window.mcThread is not None:
            try:
                if window.mcThread.isRunning():
                    window.mcThread.terminate()
                    window.mcThread.wait(2000)
            except (RuntimeError, AttributeError):
                pass

    sys.exit(exit_code)


def launch_editor(
    wbs_df=None,
    dsm_df=None,
    wbs_path: str | None = None,
    dsm_path: str | None = None,
    autosave_root=None,
):
    """啟動 DSM 編輯器。
    
    Args:
        wbs_df: WBS 資料表，如果為 None 則使用空資料表
        dsm_df: DSM 資料表，可為 None
        wbs_path: WBS 檔案路徑，可為 None
        dsm_path: DSM 檔案路徑，可為 None
        autosave_root: 自動存檔根目錄，可為 None
        
    Returns:
        tuple: (QApplication, DsmEditor) 應用程式物件和編輯器實例
    """
    from .ui.dsm_editor import DsmEditor

    prepareQtApplication()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)
    
    # 如果沒有提供 wbs_df，建立空的 DataFrame
    if wbs_df is None:
        wbs_df = pd.DataFrame()
    
    editor = DsmEditor(
        wbs_df,
        dsmDf=dsm_df,
        wbsPath=wbs_path,
        dsmPath=dsm_path,
        autosaveRoot=autosave_root,
    )
    editor.show()
    
    return app, editor


if __name__ == "__main__":
    main()
