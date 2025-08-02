# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
import json
import os
import networkx as nx
from functools import partial

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
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import qdarkstyle
import pandas as pd
from pandas import DataFrame
from PyQt5.QtCore import QAbstractTableModel

from .dsm_processor import (
    readDsm,
    process_dsm,
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
from . import visualizer
from .core import run_monte_carlo_simulation


class PandasModel(QAbstractTableModel):
    def __init__(self, df: DataFrame, dsm_mode=False):
        super().__init__()
        self._df = df
        self._dsm_mode = dsm_mode

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
        if self._dsm_mode and role == Qt.BackgroundRole:
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
                if self._dsm_mode:
                    return str(self._df.index[section])
                # 其他情況維持 1 起始的列號
                return str(section + 1)
        return None


class SettingsDialog(QDialog):
    def __init__(self, current_params, parent=None):
        super().__init__(parent)
        self.setWindowTitle('k 係數參數設定')
        self.setModal(True)

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # 建立輸入框
        self.trf_scale_input = QLineEdit(
            str(current_params.get('trf_scale', 1.0)))
        self.trf_divisor_input = QLineEdit(
            str(current_params.get('trf_divisor', 10.0)))
        self.n_coef_input = QLineEdit(str(current_params.get('n_coef', 0.05)))

        # Override 相關元件
        self.override_check = QCheckBox('直接覆蓋 k 值 (Override)')
        self.override_input = QLineEdit(
            str(current_params.get('override', '')))
        self.override_input.setEnabled(False)

        # 加入到表單佈局
        form_layout.addRow('轉換比例 (trf_scale):', self.trf_scale_input)
        form_layout.addRow('轉換除數 (trf_divisor):', self.trf_divisor_input)
        form_layout.addRow('數量係數 (n_coef):', self.n_coef_input)
        form_layout.addRow(self.override_check)
        form_layout.addRow('覆寫值:', self.override_input)

        layout.addLayout(form_layout)

        # 按鈕
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # 連接 override checkbox 的信號
        self.override_check.stateChanged.connect(
            lambda state: self.override_input.setEnabled(state == Qt.Checked)
        )

        # 初始化 override 狀態
        if current_params.get('override') is not None:
            self.override_check.setChecked(True)
            self.override_input.setEnabled(True)
            self.override_input.setText(str(current_params['override']))

    def get_settings(self):
        """獲取使用者輸入的設定值"""
        try:
            settings = {
                'base': 1.0,  # 固定值
                'trf_scale': float(self.trf_scale_input.text()),
                'trf_divisor': float(self.trf_divisor_input.text()),
                'n_coef': float(self.n_coef_input.text()),
                'override': None
            }

            if self.override_check.isChecked():
                override_value = self.override_input.text().strip()
                if override_value:
                    settings['override'] = float(override_value)

            return settings
        except ValueError:
            return None


class BirdmanQtApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Birdman Project 進階 GUI')
        self.resize(1000, 600)
        self.dsm_path = ''
        self.wbs_path = ''
        self.sorted_wbs = None
        self.merged_wbs = None
        self.sorted_dsm = None
        self.is_dark_mode = False
        self.graph = None

        # 圖表相關物件初始化
        self.graph_figure = None
        self.graph_canvas = None
        self.merged_graph_figure = None
        self.merged_graph_canvas = None
        self.gantt_figure = None
        self.gantt_canvas = None

        # CPM 分析相關資料
        self.cmp_result = None
        self.critical_path = None
        self.merged_graph = None
        self.merged_dsm = None
        # 儲存不同情境下的甘特圖資料
        self.gantt_results = {}
        # 儲存目前顯示的 CPM 報告 DataFrame
        self.current_display_cpm_df = None

        # 儲存分群與分層對應表
        self.scc_map = {}
        self.layer_map = {}
        self.merged_scc_map = {}
        self.merged_layer_map = {}

        # 預設的 k 參數值
        self.default_k_params = {
            'base': 1.0,  # 固定值
            'trf_scale': 1.0,
            'trf_divisor': 10.0,
            'n_coef': 0.05,
            'override': None
        }

        # 嘗試從 config.json 讀取設定
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.k_params = config.get(
                    'merge_k_params', self.default_k_params)
        except (OSError, json.JSONDecodeError):
            # 檔案不存在或解析失敗時以預設值處理
            self.k_params = self.default_k_params

        self.initUI()

    def initUI(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 建立主分頁容器
        self.main_tabs = QTabWidget()
        self.tab_setup = QWidget()
        self.tab_results_main = QWidget()
        self.main_tabs.addTab(self.tab_setup, '1. 設定與輸入 (Setup & Input)')
        self.main_tabs.addTab(
            self.tab_results_main, '2. 分析結果 (Analysis Results)')
        main_layout.addWidget(self.main_tabs)

        setup_layout = QVBoxLayout()
        self.tab_setup.setLayout(setup_layout)

        results_layout = QVBoxLayout()
        self.tab_results_main.setLayout(results_layout)

        # 初始將結果分頁禁用
        self.main_tabs.setTabEnabled(1, False)

        results_layout.addWidget(
            QLabel('點擊「開始分析」後，結果將會顯示於此'))

        # 檔案路徑顯示區
        self.path_layout = QHBoxLayout()

        self.dsm_label = QLabel('DSM 檔案:')
        self.dsm_path_label = QLabel('')
        self.path_layout.addWidget(self.dsm_label)
        self.path_layout.addWidget(self.dsm_path_label)

        self.wbs_label = QLabel('WBS 檔案:')
        self.wbs_path_label = QLabel('')
        self.path_layout.addWidget(self.wbs_label)
        self.path_layout.addWidget(self.wbs_path_label)

        # 頂端選單列
        menubar = self.menuBar()
        file_menu = menubar.addMenu('檔案')
        settings_menu = menubar.addMenu('設定')
        theme_menu = menubar.addMenu('主題')

        # k 係數參數設定動作
        k_params_action = QAction('k 係數參數設定...', self)
        k_params_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(k_params_action)

        # 深色模式切換動作
        self.dark_mode_action = QAction('啟用深色模式', self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.toggled.connect(self.toggle_dark_mode)
        theme_menu.addAction(self.dark_mode_action)

        # 檔案選單 - 匯入與匯出
        import_menu = file_menu.addMenu('匯入')
        import_wbs_action = QAction('匯入 WBS 檔案...', self)
        import_wbs_action.triggered.connect(self.chooseWbs)
        import_menu.addAction(import_wbs_action)
        import_dsm_action = QAction('匯入 DSM 檔案...', self)
        import_dsm_action.triggered.connect(self.chooseDsm)
        import_menu.addAction(import_dsm_action)
        import_folder_action = QAction('匯入資料夾...', self)
        import_folder_action.triggered.connect(self.import_from_folder)
        import_menu.addAction(import_folder_action)

        export_menu = file_menu.addMenu('匯出')
        export_wbs_menu = export_menu.addMenu('匯出合併後的 WBS')
        export_wbs_csv = QAction('存成 CSV 檔案... (.csv)', self)
        export_wbs_csv.triggered.connect(
            partial(self.exportMergedWbs, 'csv')
        )
        export_wbs_menu.addAction(export_wbs_csv)
        export_wbs_xlsx = QAction('存成 Excel 檔案... (.xlsx)', self)
        export_wbs_xlsx.triggered.connect(
            partial(self.exportMergedWbs, 'xlsx')
        )
        export_wbs_menu.addAction(export_wbs_xlsx)

        export_dsm_menu = export_menu.addMenu('匯出合併後的 DSM')
        export_dsm_csv = QAction('存成 CSV 檔案... (.csv)', self)
        export_dsm_csv.triggered.connect(
            partial(self.exportMergedDsm, 'csv')
        )
        export_dsm_menu.addAction(export_dsm_csv)
        export_dsm_xlsx = QAction('存成 Excel 檔案... (.xlsx)', self)
        export_dsm_xlsx.triggered.connect(
            partial(self.exportMergedDsm, 'xlsx')
        )
        export_dsm_menu.addAction(export_dsm_xlsx)

        export_gantt_menu = export_menu.addMenu('匯出甘特圖')
        export_gantt_png = QAction('存成 PNG 圖片... (.png)', self)
        export_gantt_png.triggered.connect(
            partial(self.exportGanttChart, 'png')
        )
        export_gantt_menu.addAction(export_gantt_png)
        export_gantt_svg = QAction('存成 SVG 圖片... (.svg)', self)
        export_gantt_svg.triggered.connect(
            partial(self.exportGanttChart, 'svg')
        )
        export_gantt_menu.addAction(export_gantt_svg)

        export_graph_menu = export_menu.addMenu('匯出原始依賴關係圖')
        export_graph_png = QAction('存成 PNG 圖片... (.png)', self)
        export_graph_png.triggered.connect(
            partial(self.exportGraph, 'png')
        )
        export_graph_menu.addAction(export_graph_png)
        export_graph_svg = QAction('存成 SVG 圖片... (.svg)', self)
        export_graph_svg.triggered.connect(
            partial(self.exportGraph, 'svg')
        )
        export_graph_menu.addAction(export_graph_svg)

        export_m_graph_menu = export_menu.addMenu('匯出合併後依賴關係圖')
        export_m_graph_png = QAction('存成 PNG 圖片... (.png)', self)
        export_m_graph_png.triggered.connect(
            partial(self.exportMergedGraph, 'png')
        )
        export_m_graph_menu.addAction(export_m_graph_png)
        export_m_graph_svg = QAction('存成 SVG 圖片... (.svg)', self)
        export_m_graph_svg.triggered.connect(
            partial(self.exportMergedGraph, 'svg')
        )
        export_m_graph_menu.addAction(export_m_graph_svg)

        export_cpm_menu = export_menu.addMenu('匯出 CPM 分析結果')
        export_cpm_csv = QAction('存成 CSV 檔案... (.csv)', self)
        export_cpm_csv.triggered.connect(
            partial(self.export_cpm_results, 'csv')
        )
        export_cpm_menu.addAction(export_cpm_csv)
        export_cpm_xlsx = QAction('存成 Excel 檔案... (.xlsx)', self)
        export_cpm_xlsx.triggered.connect(
            partial(self.export_cpm_results, 'xlsx')
        )
        export_cpm_menu.addAction(export_cpm_xlsx)

        # 執行分析按鈕
        self.full_analysis_button = QPushButton('執行完整分析 (Run Full Analysis)')
        self.full_analysis_button.clicked.connect(self.run_full_analysis)

        setup_layout.addLayout(self.path_layout)
        setup_layout.addWidget(self.full_analysis_button)

        # 分析結果分頁集合
        self.tabs_results = QTabWidget()
        self.tab_raw_dsm = QWidget()
        self.tab_raw_wbs = QWidget()
        self.tab_sorted_wbs = QWidget()
        self.tab_merged_wbs = QWidget()
        self.tab_merged_dsm = QWidget()
        self.tab_sorted_dsm = QWidget()
        self.tab_graph = QWidget()
        self.tab_merged_graph = QWidget()
        self.tab_cmp_result = QWidget()
        self.tab_gantt_chart = QWidget()
        self.tab_advanced_analysis = QWidget()  # 新增進階分析分頁
        self.tabs_results.addTab(self.tab_raw_dsm, '原始 DSM')
        self.tabs_results.addTab(self.tab_raw_wbs, '原始 WBS')
        self.tabs_results.addTab(self.tab_sorted_wbs, '排序 WBS')
        self.tabs_results.addTab(self.tab_merged_wbs, '合併 WBS')
        self.tabs_results.addTab(self.tab_merged_dsm, '合併 DSM')
        self.tabs_results.addTab(self.tab_sorted_dsm, '排序 DSM')
        self.tabs_results.addTab(self.tab_graph, '依賴關係圖')
        self.tabs_results.addTab(self.tab_merged_graph, '合併後依賴圖')
        self.tabs_results.addTab(self.tab_cmp_result, 'CPM 分析結果')
        self.tabs_results.addTab(self.tab_gantt_chart, '甘特圖')
        self.tabs_results.addTab(self.tab_advanced_analysis, '進階分析')
        results_layout.addWidget(self.tabs_results)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 表格
        self.raw_dsm_view = QTableView()
        self.raw_wbs_view = QTableView()
        self.sorted_wbs_view = QTableView()
        self.merged_wbs_view = QTableView()
        self.sorted_dsm_view = QTableView()
        self.merged_dsm_view = QTableView()
        self.cmp_result_view = QTableView()
        # 預覽用表格
        self.dsm_preview = QTableView()
        self.wbs_preview = QTableView()

        # 預覽分頁
        self.preview_tabs = QTabWidget()
        self.wbs_preview_tab = QWidget()
        self.dsm_preview_tab = QWidget()
        self.preview_tabs.addTab(self.wbs_preview_tab, 'WBS Preview')
        self.preview_tabs.addTab(self.dsm_preview_tab, 'DSM Preview')
        self.wbs_preview_tab.setLayout(QVBoxLayout())
        self.wbs_preview_tab.layout().addWidget(self.wbs_preview)
        self.dsm_preview_tab.setLayout(QVBoxLayout())
        self.dsm_preview_tab.layout().addWidget(self.dsm_preview)

        setup_layout.addWidget(self.preview_tabs)
        setup_layout.addWidget(self.full_analysis_button)
        # 依賴關係圖容器（Canvas 之後動態加入）
        self.graph_container = QWidget()
        self.graph_container_layout = QVBoxLayout(self.graph_container)
        self.graph_container_layout.setContentsMargins(0, 0, 0, 0)

        # 合併後依賴圖容器
        self.merged_graph_container = QWidget()
        self.merged_graph_container_layout = QVBoxLayout(
            self.merged_graph_container
        )
        self.merged_graph_container_layout.setContentsMargins(0, 0, 0, 0)

        # 建立外層容器（用於控制大小和捲動）
        self.graph_outer_container = QWidget()
        self.graph_outer_layout = QVBoxLayout(self.graph_outer_container)
        self.graph_outer_layout.setContentsMargins(0, 0, 0, 0)

        # 合併後圖的容器與捲動區域
        self.merged_graph_outer_container = QWidget()
        self.merged_graph_outer_layout = QVBoxLayout(
            self.merged_graph_outer_container
        )
        self.merged_graph_outer_layout.setContentsMargins(0, 0, 0, 0)

        # 設定固定的參考尺寸
        self.graph_container.setMinimumSize(1000, 800)
        self.merged_graph_container.setMinimumSize(1000, 800)

        # 建立捲動區域
        self.scroll_area = QScrollArea(self.graph_outer_container)
        self.scroll_area.setWidget(self.graph_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.merged_scroll_area = QScrollArea(
            self.merged_graph_outer_container
        )
        self.merged_scroll_area.setWidget(self.merged_graph_container)
        self.merged_scroll_area.setWidgetResizable(True)
        self.merged_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        self.merged_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        self.graph_outer_layout.addWidget(self.scroll_area)
        self.merged_graph_outer_layout.addWidget(self.merged_scroll_area)

        # 只在 WBS 相關表格隱藏行號
        for view in [
            self.raw_wbs_view,
            self.sorted_wbs_view,
            self.merged_wbs_view,
            self.cmp_result_view,
        ]:
            view.verticalHeader().setVisible(False)
        # DSM 表格顯示行號 (Task ID)
        self.raw_dsm_view.verticalHeader().setVisible(True)
        self.sorted_dsm_view.verticalHeader().setVisible(True)
        self.merged_dsm_view.verticalHeader().setVisible(True)
        self.tab_raw_dsm.setLayout(QVBoxLayout())
        self.tab_raw_dsm.layout().addWidget(self.raw_dsm_view)
        self.tab_raw_wbs.setLayout(QVBoxLayout())
        self.tab_raw_wbs.layout().addWidget(self.raw_wbs_view)
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
        self.tab_merged_graph.layout().addWidget(
            self.merged_graph_outer_container
        )
        self.tab_cmp_result.setLayout(QVBoxLayout())
        cpm_top_layout = QHBoxLayout()
        cpm_top_layout.addStretch()
        self.cpm_display_combo = QComboBox()
        self.cpm_display_combo.currentIndexChanged.connect(
            self.update_cpm_display
        )
        cpm_top_layout.addWidget(self.cpm_display_combo)
        self.tab_cmp_result.layout().addLayout(cpm_top_layout)
        self.tab_cmp_result.layout().addWidget(self.cmp_result_view)
        self.tab_gantt_chart.setLayout(QVBoxLayout())
        self.tab_advanced_analysis.setLayout(QVBoxLayout())

        # --- 蒙地卡羅模擬區塊 ---
        mc_group = QWidget()
        mc_layout = QVBoxLayout()
        mc_group.setLayout(mc_layout)

        mc_title = QLabel("<h3>蒙地卡羅模擬 (Monte Carlo Simulation)</h3>")
        mc_layout.addWidget(mc_title)

        mc_form_layout = QFormLayout()
        self.mc_role_select = QComboBox()
        self.mc_role_select.addItems(["新手 (Novice)", "專家 (Expert)"])
        self.mc_iterations_input = QLineEdit("1000")
        self.mc_confidence_input = QLineEdit("0.95")
        mc_form_layout.addRow("模擬角色 (Role):", self.mc_role_select)
        mc_form_layout.addRow("模擬次數 (Iterations):", self.mc_iterations_input)
        mc_form_layout.addRow("信心水準 (Confidence):", self.mc_confidence_input)
        mc_layout.addLayout(mc_form_layout)

        self.run_mc_button = QPushButton("執行蒙地卡羅模擬")
        mc_layout.addWidget(self.run_mc_button)

        self.mc_results_label = QLabel("模擬結果將顯示於此")
        self.mc_results_label.setWordWrap(True)
        mc_layout.addWidget(self.mc_results_label)

        mc_layout.addStretch()
        self.tab_advanced_analysis.layout().addWidget(mc_group)

        # --- RCPSP 排程區塊 ---
        rcpsp_group = QWidget()
        rcpsp_layout = QVBoxLayout()
        rcpsp_group.setLayout(rcpsp_layout)

        rcpsp_title = QLabel("<h3>RCPSP 資源排程 (RCPSP Resource Scheduling)</h3>")
        rcpsp_layout.addWidget(rcpsp_title)

        self.run_rcpsp_button = QPushButton("執行 RCPSP 資源排程")
        rcpsp_layout.addWidget(self.run_rcpsp_button)

        rcpsp_layout.addStretch()
        self.tab_advanced_analysis.layout().addWidget(rcpsp_group)

        # --- 按鈕連接 ---
        self.run_mc_button.clicked.connect(self.run_monte_carlo_simulation)
        self.run_rcpsp_button.clicked.connect(self.run_rcpsp_optimization)

        # 甘特圖情境切換下拉選單
        self.gantt_display_combo = QComboBox()
        self.gantt_display_combo.currentIndexChanged.connect(
            self.update_gantt_display
        )
        gantt_top_layout = QHBoxLayout()
        gantt_top_layout.addWidget(self.gantt_display_combo)
        self.total_hours_label = QLabel('總工時：0 小時')
        gantt_top_layout.addWidget(self.total_hours_label)
        gantt_top_layout.addStretch()
        self.tab_gantt_chart.layout().addLayout(gantt_top_layout)

        # 甘特圖容器
        self.gantt_container = QWidget()
        self.gantt_container.setLayout(QVBoxLayout())
        self.tab_gantt_chart.layout().addWidget(self.gantt_container)

    def chooseDsm(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '選擇 DSM 檔案', '', 'CSV Files (*.csv)')
        if path:
            self.dsm_path = path
            self.dsm_path_label.setText(path)
            try:
                dsm = readDsm(path)
                model = PandasModel(dsm.head(100), dsm_mode=True)
                self.raw_dsm_view.setModel(model)
                self.dsm_preview.setModel(model)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, '錯誤', f'DSM 載入失敗：{e}')

    def chooseWbs(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '選擇 WBS 檔案', '', 'CSV Files (*.csv)')
        if path:
            self.wbs_path = path
            self.wbs_path_label.setText(path)
            try:
                wbs = readWbs(path)
                wbs = self._add_no_column(wbs)
                model = PandasModel(wbs.head(100))
                self.raw_wbs_view.setModel(model)
                self.wbs_preview.setModel(model)
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, '錯誤', f'WBS 載入失敗：{e}')

    def import_from_folder(self):
        """從資料夾匯入 WBS 與 DSM"""
        folder = QFileDialog.getExistingDirectory(self, '選擇資料夾', '')
        if not folder:
            return
        files = os.listdir(folder)
        wbs_files = [f for f in files if 'wbs' in f.lower()]
        dsm_files = [f for f in files if 'dsm' in f.lower()]
        if len(wbs_files) != 1 or len(dsm_files) != 1:
            QMessageBox.warning(
                self,
                '錯誤',
                '請選擇一個剛好包含一份 WBS 和一份 DSM 檔案的資料夾。'
            )
            return
        wbs_path = os.path.join(folder, wbs_files[0])
        dsm_path = os.path.join(folder, dsm_files[0])
        try:
            wbs = readWbs(wbs_path)
            wbs_display = self._add_no_column(wbs)
            dsm = readDsm(dsm_path)
        except (OSError, pd.errors.ParserError, ValueError):
            QMessageBox.critical(
                self,
                '錯誤',
                '資料夾中的 WBS 或 DSM 檔案格式不正確，請檢查檔案內容。'
            )
            return
        self.wbs_path = wbs_path
        self.dsm_path = dsm_path
        self.wbs_path_label.setText(wbs_path)
        self.dsm_path_label.setText(dsm_path)
        model_wbs = PandasModel(wbs_display.head(100))
        self.raw_wbs_view.setModel(model_wbs)
        self.wbs_preview.setModel(model_wbs)
        model_dsm = PandasModel(dsm.head(100), dsm_mode=True)
        self.raw_dsm_view.setModel(model_dsm)
        self.dsm_preview.setModel(model_dsm)

    def runAnalysis(self):
        try:
            dsm = readDsm(self.dsm_path)
            wbs = readWbs(self.wbs_path)
            # 預覽原始資料
            model_dsm = PandasModel(dsm.head(100), dsm_mode=True)
            self.raw_dsm_view.setModel(model_dsm)
            self.dsm_preview.setModel(model_dsm)
            wbs_with_no = self._add_no_column(wbs)
            model_wbs = PandasModel(wbs_with_no.head(100))
            self.raw_wbs_view.setModel(model_wbs)
            self.wbs_preview.setModel(model_wbs)

            validateIds(wbs, dsm)

            # 設定正確的圖表主題
            plt.style.use(
                'dark_background' if self.is_dark_mode else 'default')

            sorted_dsm, sorted_wbs, graph = process_dsm(dsm, wbs)
            self.sorted_wbs = self._add_no_column(sorted_wbs)
            self.sorted_dsm = sorted_dsm
            self.graph = graph  # 儲存圖形物件供後續使用

            merged = mergeByScc(sorted_wbs, self.k_params)
            self.merged_wbs = self._add_no_column(merged)

            # 建立原始 Task ID 到合併後 Task ID 的對應
            task_mapping = buildTaskMapping(sorted_wbs, merged)
            # 依映射產生合併後的 DSM
            merged_dsm = buildMergedDsm(self.graph, task_mapping)
            # 根據合併後的 DSM 重新計算層次與圖形
            (
                self.merged_dsm,
                merged_sorted_wbs,
                self.merged_graph,
            ) = process_dsm(
                merged_dsm,
                merged,
            )

            # 儲存原始圖的映射
            self.scc_map = dict(
                zip(sorted_wbs['Task ID'], sorted_wbs['SCC_ID'])
            )
            self.layer_map = dict(
                zip(sorted_wbs['Task ID'], sorted_wbs['Layer'])
            )

            # 計算並儲存合併後圖形的映射
            try:
                source_nodes = [
                    node for node, deg in self.merged_graph.in_degree()
                    if deg == 0
                ]
                self.merged_layer_map = {}
                for node in self.merged_graph.nodes():
                    max_dist = 0
                    for src in source_nodes:
                        try:
                            paths = nx.all_simple_paths(
                                self.merged_graph, src, node
                            )
                            dist = max((len(p) - 1 for p in paths), default=-1)
                            if dist > max_dist:
                                max_dist = dist
                        except nx.NetworkXNoPath:
                            continue
                    self.merged_layer_map[node] = max_dist
            except Exception:  # pylint: disable=broad-except
                self.merged_layer_map = {
                    node: i for i, node in enumerate(self.merged_graph.nodes())
                }

            self.merged_scc_map = {
                node: i for i, node in enumerate(self.merged_graph.nodes())
            }

            # 重新繪製依賴關係圖
            self.redraw_graph()
            # 預覽
            self.sorted_wbs_view.setModel(
                PandasModel(self.sorted_wbs.head(100)))
            self.merged_wbs_view.setModel(
                PandasModel(self.merged_wbs.head(100)))
            self.sorted_dsm_view.setModel(PandasModel(
                self.sorted_dsm.head(100), dsm_mode=True))
            self.merged_dsm_view.setModel(PandasModel(
                self.merged_dsm.head(100), dsm_mode=True))
            # 啟用結果分頁並自動切換
            self.main_tabs.setTabEnabled(1, True)
            self.main_tabs.setCurrentIndex(1)
            QMessageBox.information(self, '完成', '分析完成，可切換分頁預覽與匯出')
            return True
        except Exception as e:  # pylint: disable=broad-except
            # 執行流程中可能發生多種錯誤，此處統一彙整顯示訊息
            QMessageBox.critical(self, '錯誤', str(e))
            return False

    def _add_no_column(self, df):
        # 僅針對 WBS 及其衍生表格加 No. 欄，且不覆蓋 Task ID
        df = df.copy()
        # 若最左欄是純數字且不是 Task ID，移除
        first_col = df.columns[0]
        if first_col != 'Task ID' and first_col != 'No.':
            try:
                as_num = pd.to_numeric(df[first_col], errors='coerce')
                if as_num.notnull().all():
                    df = df.drop(columns=[first_col])
            except (ValueError, TypeError):
                # 轉型失敗時直接忽略
                pass
        df.insert(0, 'No.', range(1, len(df) + 1))
        return df

    def _create_cpm_display_df(self, full_results_df, role_key, time_key):
        """產生精簡版 CPM 結果表"""
        core_display_cols = [
            'Task ID',
            'Name',
            'ES', 'EF', 'LS', 'LF',
            'TF', 'FF', 'Critical'
        ]

        role_map = {
            'novice': 'newbie',
            'expert': 'expert'
        }
        role_suffix = role_map.get(role_key.lower(), role_key.lower())
        time_column = f'{time_key}_{role_suffix}'

        columns = core_display_cols.copy()
        if time_column in full_results_df.columns:
            insert_index = columns.index('Name') + 1
            columns.insert(insert_index, time_column)

        existing_cols = [c for c in columns if c in full_results_df.columns]
        display_df = full_results_df[existing_cols].copy()
        return display_df

    def exportSortedWbs(self):
        if self.sorted_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出排序 WBS', '', 'CSV Files (*.csv)')
        if path:
            self.sorted_wbs.to_csv(path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, '完成', f'已匯出 {path}')

    def exportMergedWbs(self, fmt='csv'):
        """匯出合併後的 WBS"""
        if self.merged_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        if fmt == 'xlsx':
            file_filter = 'Excel 檔案 (*.xlsx)'
            path, _ = QFileDialog.getSaveFileName(
                self, '匯出合併 WBS', '', file_filter)
            if not path:
                return
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.merged_wbs.to_excel(path, index=False)
        else:
            file_filter = 'CSV Files (*.csv)'
            path, _ = QFileDialog.getSaveFileName(
                self, '匯出合併 WBS', '', file_filter)
            if not path:
                return
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self.merged_wbs.to_csv(path, encoding='utf-8-sig', index=False)
        QMessageBox.information(self, '完成', f'已匯出 {path}')

    def exportSortedDsm(self):
        if self.sorted_dsm is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出排序 DSM', '', 'CSV Files (*.csv)')
        if path:
            self.sorted_dsm.to_csv(path, encoding='utf-8-sig')
            QMessageBox.information(self, '完成', f'已匯出 {path}')

    def exportMergedDsm(self, fmt='csv'):
        """匯出合併後的 DSM"""
        if self.merged_dsm is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        if fmt == 'xlsx':
            file_filter = 'Excel 檔案 (*.xlsx)'
            path, _ = QFileDialog.getSaveFileName(
                self, '匯出合併 DSM', '', file_filter)
            if not path:
                return
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.merged_dsm.to_excel(path, index=False)
        else:
            file_filter = 'CSV Files (*.csv)'
            path, _ = QFileDialog.getSaveFileName(
                self, '匯出合併 DSM', '', file_filter)
            if not path:
                return
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self.merged_dsm.to_csv(path, encoding='utf-8-sig', index=False)
        QMessageBox.information(self, '完成', f'已匯出 {path}')

    def exportGraph(self, fmt='png'):
        """匯出原始依賴關係圖"""
        if not hasattr(self, 'graph') or self.graph is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return

        file_filter = 'PNG 圖片 (*.png)' if fmt == 'png' else 'SVG 向量圖 (*.svg)'
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出依賴關係圖', '', file_filter)
        if not path:
            return

        try:
            if not path.lower().endswith(f'.{fmt}'):
                path += f'.{fmt}'
            self.graph_canvas.figure.savefig(
                path,
                format=fmt,
                bbox_inches='tight',
                dpi=300,
            )
            QMessageBox.information(self, '完成', f'已匯出依賴關係圖至：{path}')
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, '錯誤', f'匯出圖檔時發生錯誤：{e}')

    def exportMergedGraph(self, fmt='png'):
        """匯出合併後依賴關係圖"""
        if not hasattr(self, 'merged_graph') or self.merged_graph is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return

        file_filter = 'PNG 圖片 (*.png)' if fmt == 'png' else 'SVG 向量圖 (*.svg)'
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出合併後依賴關係圖', '', file_filter)
        if not path:
            return

        try:
            if not path.lower().endswith(f'.{fmt}'):
                path += f'.{fmt}'
            self.merged_graph_canvas.figure.savefig(
                path,
                format=fmt,
                bbox_inches='tight',
                dpi=300,
            )
            QMessageBox.information(self, '完成', f'已匯出合併後依賴圖至：{path}')
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, '錯誤', f'匯出圖檔時發生錯誤：{e}')

    def runCmpAnalysis(self):
        """執行 CPM 分析"""
        if not (
            hasattr(self, 'merged_graph') and hasattr(self, 'merged_wbs')
        ):
            QMessageBox.warning(self, '警告', '請先執行基本分析')
            return

        try:
            # 檢查合併後的圖是否存在循環
            cycles = list(nx.simple_cycles(self.merged_graph))
            if cycles:
                cycle_str = " -> ".join(cycles[0] + [cycles[0][0]])
                raise ValueError(
                    f"發現循環依賴：{cycle_str}\n"
                    "請先解決循環依賴問題再進行 CPM 分析"
                )

            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            cmp_params = config.get('cmp_params', {})
            base_field = cmp_params.get('default_duration_field', 'Te_newbie')

            role_choice = self.role_selection_combo.currentText()
            role_suffix = 'newbie' if '新手' in role_choice else 'expert'
            parts_role = base_field.split('_', 1)
            if len(parts_role) == 2:
                base_field = f"{parts_role[0]}_{role_suffix}"
            else:
                base_field = f"{base_field}_{role_suffix}"

            # 解析使用者選擇的情境
            choice = self.time_selection_combo.currentText()
            if choice == 'All Scenarios':
                scenarios = ['O', 'P', 'M', 'Te']
            else:
                key = choice.split('(')[-1].split(')')[0]
                scenarios = ['Te' if key.upper() == 'TE' else key]

            self.gantt_results = {}

            for sc in scenarios:
                parts = base_field.split('_', 1)
                if len(parts) == 2:
                    duration_field = f"{sc}_{parts[1]}"
                else:
                    duration_field = sc

                durations_hours = extractDurationFromWbs(
                    self.merged_wbs.drop(columns=['No.']), duration_field
                )

                forward_data = cpmForwardPass(
                    self.merged_graph,
                    durations_hours,
                )
                project_end = max(ef for _, ef in forward_data.values())
                backward_data = cpmBackwardPass(
                    self.merged_graph,
                    durations_hours,
                    project_end,
                )
                cpm_result = calculateSlack(
                    forward_data,
                    backward_data,
                    self.merged_graph,
                )
                wbs_with_cpm = self.merged_wbs.copy()
                for col in ['ES', 'EF', 'LS', 'LF', 'TF', 'FF', 'Critical']:
                    wbs_with_cpm[col] = wbs_with_cpm['Task ID'].map(
                        cpm_result[col].to_dict()
                    ).fillna(0)

                self.gantt_results[sc] = (
                    cpm_result,
                    durations_hours,
                    wbs_with_cpm,
                    project_end,
                )

            # 更新情境下拉選單並顯示第一個結果
            keys = list(self.gantt_results.keys())
            self.gantt_display_combo.blockSignals(True)
            self.cpm_display_combo.blockSignals(True)
            self.gantt_display_combo.clear()
            self.cpm_display_combo.clear()
            self.gantt_display_combo.addItems(keys)
            self.cpm_display_combo.addItems(keys)
            self.gantt_display_combo.blockSignals(False)
            self.cpm_display_combo.blockSignals(False)
            self.gantt_display_combo.setCurrentIndex(0)
            self.cpm_display_combo.setCurrentIndex(0)
            self.update_gantt_display()

            QMessageBox.information(self, 'CPM 分析完成', 'CPM 分析已完成')
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, '錯誤', f'CPM 分析失敗：{e}')

    def run_full_analysis(self):
        """執行所有情境的 CPM 分析"""
        success = self.runAnalysis()
        if not success:
            return

        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            cmp_params = config.get('cmp_params', {})
            base_field = cmp_params.get('default_duration_field', 'Te_newbie')
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, '錯誤', f'設定檔讀取失敗：{e}')
            return

        roles = {
            '新手': 'newbie',
            '專家': 'expert',
        }
        time_types = {
            '樂觀時間': 'O',
            '悲觀時間': 'P',
            '最可能時間': 'M',
            '期望時間': 'Te',
        }

        self.gantt_results = {}

        for role_text, role_key in roles.items():
            # 依角色調整基準欄位名稱
            parts_role = base_field.split('_', 1)
            if len(parts_role) == 2:
                _ = f"{parts_role[0]}_{role_key}"
            else:
                _ = f"{base_field}_{role_key}"

            for time_text, time_key in time_types.items():
                duration_field = f"{time_key}_{role_key}"

                durations_hours = extractDurationFromWbs(
                    self.merged_wbs.drop(columns=['No.']), duration_field
                )
                forward_data = cpmForwardPass(
                    self.merged_graph,
                    durations_hours,
                )
                project_end = max(ef for _, ef in forward_data.values())
                backward_data = cpmBackwardPass(
                    self.merged_graph,
                    durations_hours,
                    project_end,
                )
                cpm_result = calculateSlack(
                    forward_data,
                    backward_data,
                    self.merged_graph,
                )

                wbs_with_cpm = self.merged_wbs.copy()
                for col in ['ES', 'EF', 'LS', 'LF', 'TF', 'FF', 'Critical']:
                    wbs_with_cpm[col] = wbs_with_cpm['Task ID'].map(
                        cpm_result[col].to_dict()
                    ).fillna(0)

                key = f"{role_text} - {time_text} ({duration_field})"
                self.gantt_results[key] = (
                    cpm_result,
                    durations_hours,
                    wbs_with_cpm,
                    project_end,
                )

        keys = list(self.gantt_results.keys())
        self.gantt_display_combo.blockSignals(True)
        self.cpm_display_combo.blockSignals(True)
        self.gantt_display_combo.clear()
        self.cpm_display_combo.clear()
        self.gantt_display_combo.addItems(keys)
        self.cpm_display_combo.addItems(keys)
        self.gantt_display_combo.blockSignals(False)
        self.cpm_display_combo.blockSignals(False)

        default_key = '新手 - 期望時間 (Te_newbie)'
        default_index = keys.index(default_key) if default_key in keys else 0
        self.gantt_display_combo.setCurrentIndex(default_index)
        self.cpm_display_combo.setCurrentIndex(default_index)
        self.update_gantt_display()

        QMessageBox.information(self, 'CPM 分析完成', 'CPM 分析已完成')

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

            fig.patch.set_facecolor(plt.rcParams['figure.facecolor'])
            ax.set_facecolor(plt.rcParams['axes.facecolor'])

            fig.subplots_adjust(
                top=0.9,
                bottom=0.15,
                left=0.2,
                right=0.95,
            )

            # 取得任務列表和相關數據
            tasks = wbsDf['Task ID'].tolist()
            start_times = [cpmData.at[t, 'ES'] for t in tasks]
            task_durations = [durations.get(t, 0) for t in tasks]

            # 設定任務條的位置和顏色
            y_positions = range(len(tasks))
            colors = [
                'red' if cpmData.at[t, 'Critical'] else 'skyblue'
                for t in tasks
            ]

            # 繪製任務條
            ax.barh(
                y_positions,
                task_durations,
                left=start_times,
                color=colors,
                alpha=0.8,
                height=0.6,
                edgecolor='black',
                linewidth=1,
                zorder=2,
            )

            # 設定 Y 軸標籤
            ax.set_yticks(y_positions)
            ax.set_yticklabels(
                tasks,
                fontsize=10,
                fontweight='bold',
                color=plt.rcParams['axes.labelcolor'],
            )

            ax.tick_params(axis='x', colors=plt.rcParams['xtick.color'])
            ax.tick_params(axis='y', colors=plt.rcParams['ytick.color'])

            for spine in ax.spines.values():
                spine.set_edgecolor(plt.rcParams['axes.edgecolor'])

            # 加強網格線
            ax.grid(
                True,
                axis='x',
                linestyle='--',
                color=plt.rcParams['grid.color'],
                alpha=0.3,
                zorder=1,
            )
            ax.set_axisbelow(True)

            # 設定標籤和標題
            ax.set_xlabel(
                '時間 (小時)',
                fontsize=11,
                fontweight='bold',
                color=plt.rcParams['axes.labelcolor'],
            )
            ax.set_title(
                title,
                fontsize=14,
                pad=20,
                color=plt.rcParams['axes.labelcolor'],
            )
            # 在每個任務條上添加持續時間標籤
            for i, (duration, start) in enumerate(
                zip(task_durations, start_times)
            ):
                if duration > 0:
                    ax.text(
                        start + duration + 2,
                        i,
                        f'{duration:.1f}h',
                        va='center',
                        fontsize=9,
                        alpha=0.7,
                        color=plt.rcParams['text.color'],
                    )

            # 反轉 Y 軸
            ax.invert_yaxis()

            return fig
        except Exception as e:
            QMessageBox.warning(self, '警告', f'甘特圖繪製失敗：{e}')
            return Figure()

    def update_gantt_display(self):
        """根據下拉選單切換甘特圖與結果顯示"""
        key = self.gantt_display_combo.currentText()
        if hasattr(self, 'cpm_display_combo'):
            self.cpm_display_combo.blockSignals(True)
            if self.cpm_display_combo.currentText() != key:
                self.cpm_display_combo.setCurrentText(key)
            self.cpm_display_combo.blockSignals(False)
        if key not in self.gantt_results:
            return
        cpm_df, durations, wbs_df, project_end = self.gantt_results[key]
        self.cmp_result = wbs_df

        role_key = 'novice' if '新手' in key else 'expert'
        if '(O_' in key:
            time_key = 'O'
        elif '(P_' in key:
            time_key = 'P'
        elif '(M_' in key:
            time_key = 'M'
        else:
            time_key = 'Te'

        self.current_display_cpm_df = self._create_cpm_display_df(
            wbs_df, role_key, time_key
        )
        self.critical_path = findCriticalPath(cpm_df)
        self.cmp_result_view.setModel(
            PandasModel(self.current_display_cpm_df.head(100))
        )
        self.total_hours_label.setText(f'總工時：{project_end:.1f} 小時')
        new_title = f"{key}\n總工時: {project_end:.2f} 小時"

        # 先清除舊的圖表
        layout = self.gantt_container.layout()
        for i in reversed(range(layout.count())):
            old_widget = layout.itemAt(i).widget()
            if old_widget:
                old_widget.setParent(None)

        # 重新產生甘特圖並加入佈局
        self.gantt_figure = self.drawGanttChart(
            cpm_df,
            durations,
            new_title,
            wbs_df,
        )
        self.gantt_canvas = FigureCanvas(self.gantt_figure)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.gantt_canvas)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setMinimumHeight(1000)
        self.gantt_canvas.setMinimumSize(
            1200,
            max(1000, len(wbs_df) * 35)
        )

        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(20, 40, 20, 40)
        container_layout.addWidget(scroll_area)
        container = QWidget()
        container.setLayout(container_layout)
        self.gantt_container.layout().addWidget(container)
        self.gantt_canvas.draw()

    def update_cpm_display(self):
        """切換 CPM 結果顯示並同步甘特圖"""
        index = self.cpm_display_combo.currentIndex()
        if index != self.gantt_display_combo.currentIndex():
            self.gantt_display_combo.setCurrentIndex(index)
        else:
            self.update_gantt_display()

    def exportCmpResult(self):
        """匯出 CPM 分析結果"""
        if self.cmp_result is None:
            QMessageBox.warning(self, '警告', '請先執行 CPM 分析')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出 CPM 分析結果', '', 'CSV Files (*.csv)')
        if path:
            self.cmp_result.to_csv(path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, '完成', f'已匯出 CPM 結果：{path}')

    def export_cpm_results(self, fmt='csv'):
        """匯出目前顯示的 CPM 精簡報告"""
        if self.current_display_cpm_df is None:
            QMessageBox.warning(self, '警告', '沒有可匯出的 CPM 結果')
            return
        if fmt == 'xlsx':
            file_filter = 'Excel 檔案 (*.xlsx)'
            path, _ = QFileDialog.getSaveFileName(
                self, '匯出 CPM 分析結果', '', file_filter)
            if not path:
                return
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.current_display_cpm_df.to_excel(path, index=False)
        else:
            file_filter = 'CSV Files (*.csv)'
            path, _ = QFileDialog.getSaveFileName(
                self, '匯出 CPM 分析結果', '', file_filter)
            if not path:
                return
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self.current_display_cpm_df.to_csv(
                path, index=False, encoding='utf-8-sig')
        QMessageBox.information(self, '完成', f'已匯出 {path}')

    def open_settings_dialog(self):
        """開啟 k 係數參數設定對話框"""
        dialog = SettingsDialog(self.k_params, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            if settings is None:
                QMessageBox.critical(self, '錯誤', 'k 係數參數必須為數字！')
                return
            self.k_params = settings

            # 將新設定寫入 config.json
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config['merge_k_params'] = self.k_params
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            except (OSError, json.JSONDecodeError) as e:
                QMessageBox.warning(self, '警告', f'無法保存設定：{e}')

    def toggle_dark_mode(self, checked):
        """切換深色/淺色模式"""
        if checked:
            self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
            plt.style.use('dark_background')
            self.is_dark_mode = True
            self.dark_mode_action.setText('啟用淺色模式')
        else:
            self.setStyleSheet("")
            plt.style.use('default')
            self.is_dark_mode = False
            self.dark_mode_action.setText('啟用深色模式')

        # --- 清除舊圖表 ---
        if self.gantt_figure:
            self.gantt_figure.clear()
        if self.graph_figure:
            self.graph_figure.clear()
        if self.merged_graph_figure:
            self.merged_graph_figure.clear()

        # 重繪圖表
        self.redraw_graph()
        if self.gantt_results:
            self.update_gantt_display()

    def redraw_graph(self):
        """重新繪製依賴關係圖"""
        if not hasattr(self, 'graph') or self.graph is None:
            return

        if hasattr(self, 'sorted_wbs') and self.sorted_wbs is not None:
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                viz_params = config.get('visualization_params', {})

                # 清除舊的 Canvas
                for i in reversed(range(self.graph_container_layout.count())):
                    old_widget = self.graph_container_layout.itemAt(i).widget()
                    if old_widget:
                        old_widget.setParent(None)

                for i in reversed(
                    range(self.merged_graph_container_layout.count())
                ):
                    old_widget = (
                        self.merged_graph_container_layout.itemAt(i).widget()
                    )
                    if old_widget:
                        old_widget.setParent(None)

                # 重新建立原始圖
                self.graph_figure = visualizer.create_dependency_graph_figure(
                    self.graph,
                    self.scc_map,
                    self.layer_map,
                    viz_params,
                )
                self.graph_canvas = FigureCanvas(self.graph_figure)
                self.graph_container_layout.addWidget(self.graph_canvas)
                self.graph_canvas.draw()
                canvas_size = self.graph_canvas.get_width_height()
                if canvas_size[0] > 0 and canvas_size[1] > 0:
                    self.graph_container.setMinimumSize(
                        int(canvas_size[0] * 1.1),
                        int(canvas_size[1] * 1.1),
                    )

                # 重新建立合併後圖
                if self.merged_graph is not None:
                    self.merged_graph_figure = (
                        visualizer.create_dependency_graph_figure(
                            self.merged_graph,
                            self.merged_scc_map,
                            self.merged_layer_map,
                            viz_params,
                        )
                    )
                    self.merged_graph_canvas = FigureCanvas(
                        self.merged_graph_figure
                    )
                    self.merged_graph_container_layout.addWidget(
                        self.merged_graph_canvas
                    )
                    self.merged_graph_canvas.draw()
                    m_size = self.merged_graph_canvas.get_width_height()
                    if m_size[0] > 0 and m_size[1] > 0:
                        self.merged_graph_container.setMinimumSize(
                            int(m_size[0] * 1.1),
                            int(m_size[1] * 1.1),
                        )
            except Exception as e:  # pylint: disable=broad-except
                QMessageBox.warning(self, '警告', f'圖表重繪失敗：{e}')

    def exportGanttChart(self, fmt='png'):
        """匯出甘特圖"""
        if not hasattr(self, 'gantt_figure') or self.gantt_figure is None:
            QMessageBox.warning(self, '警告', '請先執行 CPM 分析')
            return

        file_filter = 'PNG 圖片 (*.png)' if fmt == 'png' else 'SVG 向量圖 (*.svg)'
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出甘特圖', '', file_filter)

        if not path:
            return

        try:
            if not path.lower().endswith(f'.{fmt}'):
                path += f'.{fmt}'
            self.gantt_figure.savefig(
                path,
                format=fmt,
                bbox_inches='tight',
                dpi=300,
                pad_inches=0.5
            )
            QMessageBox.information(self, '完成', f'已匯出甘特圖至：{path}')
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, '錯誤', f'匯出圖檔時發生錯誤：{e}')

    def run_monte_carlo_simulation(self):
        """執行蒙地卡羅模擬"""
        if self.merged_graph is None or self.merged_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行完整分析')
            return

        try:
            iterations = int(self.mc_iterations_input.text())
            confidence = float(self.mc_confidence_input.text())
            if not (0 < confidence < 1):
                raise ValueError("信心水準必須介於 0 和 1 之間")
        except ValueError as e:
            QMessageBox.critical(self, '輸入錯誤', f'參數無效：{e}')
            return

        role_text = self.mc_role_select.currentText()
        role_key = 'newbie' if '新手' in role_text else 'expert'
        base_fields = [f"O_{role_key}", f"M_{role_key}", f"P_{role_key}"]
        if not all(f in self.merged_wbs.columns for f in base_fields):
            QMessageBox.critical(
                self,
                '錯誤',
                f'合併後的 WBS 缺少 {"/".join(base_fields)} 欄位，無法執行模擬'
            )
            return

        try:
            result = run_monte_carlo_simulation(
                self.merged_graph,
                self.merged_wbs,
                iterations=iterations,
                confidence=confidence,
                role_key=role_key,
            )

            conf_pct = int(confidence * 100)
            result_text = (
                f"<b>蒙地卡羅模擬結果 (基於 O/M/P_{role_key}):</b><br>"
                f"平均完工時間: {result['average']:.2f} 小時<br>"
                f"標準差: {result['std']:.2f} 小時<br>"
                f"最短完工時間: {result['min']:.2f} 小時<br>"
                f"最長完工時間: {result['max']:.2f} 小時<br>"
                f"<b>{conf_pct}% 信心水準下，專案可在 "
                f"{result['confidence_value']:.2f} 小時內完成。</b>"
            )
            self.mc_results_label.setText(result_text)

        except Exception as e:
            QMessageBox.critical(self, '模擬失敗', f'執行蒙地卡羅模擬時發生錯誤：{e}')

    def run_rcpsp_optimization(self):
        """執行 RCPSP 資源排程"""
        if self.merged_graph is None or self.merged_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行完整分析')
            return

        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            cmp_params = config.get('cmp_params', {})
            duration_field = cmp_params.get(
                'default_duration_field', 'Te_newbie'
            )

            if duration_field not in self.merged_wbs.columns:
                raise ValueError(f"WBS 缺少工期欄位 {duration_field}")
            if "Category" not in self.merged_wbs.columns:
                QMessageBox.warning(
                    self, '警告', 'WBS 缺少 "Category" 欄位，將不考慮資源限制'
                )

            schedule = solveRcpsp(
                self.merged_graph,
                self.merged_wbs,
                durationField=duration_field,
                resourceField="Category",
            )

            project_end = schedule.pop("ProjectEnd", 0)
            result_text = (
                f"<b>RCPSP 排程結果 (總工期: {project_end:.2f} 小時):"
                "</b><br><br>"
            )
            result_text += "<table border='1' style='width:100%'>"
            result_text += "<tr><th>任務 ID</th><th>開始時間 (小時)</th></tr>"
            for task, start_time in sorted(schedule.items()):
                result_text += f"<tr><td>{task}</td><td>{start_time}</td></tr>"
            result_text += "</table>"

            # 使用一個可捲動的對話框來顯示結果
            dialog = QDialog(self)
            dialog.setWindowTitle("RCPSP 排程結果")
            layout = QVBoxLayout()
            text_edit = QTextEdit()
            text_edit.setHtml(result_text)
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)
            button_box = QDialogButtonBox(QDialogButtonBox.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)
            dialog.setLayout(layout)
            dialog.resize(400, 300)
            dialog.exec_()

        except Exception as e:
            QMessageBox.critical(self, '排程失敗', f'執行 RCPSP 排程時發生錯誤：{e}')


def main():
    app = QApplication(sys.argv)
    window = BirdmanQtApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
