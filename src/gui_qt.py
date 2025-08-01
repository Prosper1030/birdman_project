# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
import json
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
    QGroupBox,
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
from . import visualizer


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

        # CPM 分析相關資料
        self.cmp_result = None
        self.critical_path = None
        self.merged_graph = None
        self.merged_dsm = None
        # 儲存不同情境下的甘特圖資料
        self.gantt_results = {}

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

        # 檔案與按鈕區
        self.load_buttons_layout = QHBoxLayout()

        self.dsm_label = QLabel('DSM 檔案:')
        self.dsm_path_label = QLabel('')
        dsm_btn = QPushButton('選擇')
        dsm_btn.clicked.connect(self.chooseDsm)
        self.load_buttons_layout.addWidget(self.dsm_label)
        self.load_buttons_layout.addWidget(self.dsm_path_label)
        self.load_buttons_layout.addWidget(dsm_btn)

        self.wbs_label = QLabel('WBS 檔案:')
        self.wbs_path_label = QLabel('')
        wbs_btn = QPushButton('選擇')
        wbs_btn.clicked.connect(self.chooseWbs)
        self.load_buttons_layout.addWidget(self.wbs_label)
        self.load_buttons_layout.addWidget(self.wbs_path_label)
        self.load_buttons_layout.addWidget(wbs_btn)

        # 頂端選單列
        menubar = self.menuBar()
        file_menu = menubar.addMenu('檔案')
        settings_menu = menubar.addMenu('設定')
        view_menu = menubar.addMenu('視圖')

        # k 係數參數設定動作
        k_params_action = QAction('k 係數參數設定...', self)
        k_params_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(k_params_action)

        # 深色模式切換動作
        dark_mode_action = QAction('啟用深色模式', self)
        dark_mode_action.setCheckable(True)
        dark_mode_action.toggled.connect(self.toggle_dark_mode)
        view_menu.addAction(dark_mode_action)

        # 檔案選單中的匯出子選單
        export_wbs_menu = file_menu.addMenu('匯出合併後的 WBS')
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

        export_dsm_menu = file_menu.addMenu('匯出合併後的 DSM')
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

        export_gantt_menu = file_menu.addMenu('匯出甘特圖')
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

        export_graph_menu = file_menu.addMenu('匯出原始依賴關係圖')
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

        export_m_graph_menu = file_menu.addMenu('匯出合併後依賴關係圖')
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

        # 建立「步驟 1：載入檔案」區塊
        step1_group = QGroupBox('步驟 1：載入檔案 (Step 1: Load Files)')
        step1_layout = QVBoxLayout()
        step1_layout.addLayout(self.load_buttons_layout)
        step1_group.setLayout(step1_layout)

        # 建立「步驟 2：設定分析參數」區塊
        step2_group = QGroupBox(
            '步驟 2：設定分析參數 (Step 2: Set Analysis Parameters)')
        step2_layout = QHBoxLayout()
        k_params_btn = QPushButton('k 係數設定')
        k_params_btn.clicked.connect(self.open_settings_dialog)
        step2_layout.addWidget(k_params_btn)

        self.time_selection_combo = QComboBox()
        self.time_selection_combo.addItems([
            'Optimistic (O)',
            'Pessimistic (P)',
            'Most Likely (M)',
            'Expected Time (TE)',
            'All Scenarios',
        ])
        step2_layout.addWidget(self.time_selection_combo)
        step2_group.setLayout(step2_layout)

        self.full_analysis_button = QPushButton('執行完整分析 (Run Full Analysis)')
        self.full_analysis_button.clicked.connect(self.run_full_analysis)

        setup_layout.addWidget(step1_group)
        setup_layout.addWidget(step2_group)

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
        # 依賴關係圖畫布及捲動區域
        self.graph_figure = Figure(figsize=(18, 20))  # 使用與 visualizer.py 相同的尺寸
        self.graph_canvas = FigureCanvas(self.graph_figure)

        # 合併後依賴圖畫布
        self.merged_graph_figure = Figure(figsize=(18, 20))
        self.merged_graph_canvas = FigureCanvas(self.merged_graph_figure)

        # 建立外層容器（用於控制大小和捲動）
        self.graph_outer_container = QWidget()
        self.graph_outer_layout = QVBoxLayout(self.graph_outer_container)
        self.graph_outer_layout.setContentsMargins(0, 0, 0, 0)

        # 建立內層容器（實際持有圖表）
        self.graph_container = QWidget()
        self.graph_container_layout = QVBoxLayout(self.graph_container)
        self.graph_container_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_container_layout.addWidget(self.graph_canvas)

        # 合併後圖的容器與捲動區域
        self.merged_graph_outer_container = QWidget()
        self.merged_graph_outer_layout = QVBoxLayout(
            self.merged_graph_outer_container
        )
        self.merged_graph_outer_layout.setContentsMargins(0, 0, 0, 0)

        self.merged_graph_container = QWidget()
        self.merged_graph_container_layout = QVBoxLayout(
            self.merged_graph_container
        )
        self.merged_graph_container_layout.setContentsMargins(0, 0, 0, 0)
        self.merged_graph_container_layout.addWidget(self.merged_graph_canvas)

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
        self.tab_cmp_result.layout().addWidget(self.cmp_result_view)
        self.tab_gantt_chart.setLayout(QVBoxLayout())
        # 甘特圖情境切換下拉選單
        self.gantt_display_combo = QComboBox()
        self.gantt_display_combo.currentIndexChanged.connect(
            self.update_gantt_display
        )
        self.tab_gantt_chart.layout().addWidget(self.gantt_display_combo)
        self.gantt_figure = Figure(figsize=(16, 12), dpi=100)
        self.gantt_canvas = FigureCanvas(self.gantt_figure)
        self.gantt_canvas.setMinimumSize(1000, 800)
        self.tab_gantt_chart.layout().addWidget(self.gantt_canvas)

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

            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)

            viz_params = config.get('visualization_params', {})

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

            merged_scc_map = dict(
                zip(merged_sorted_wbs['Task ID'], merged_sorted_wbs['SCC_ID'])
            )
            merged_layer_map = dict(
                zip(merged_sorted_wbs['Task ID'], merged_sorted_wbs['Layer'])
            )

            scc_map = dict(zip(sorted_wbs['Task ID'], sorted_wbs['SCC_ID']))
            layer_map = dict(zip(sorted_wbs['Task ID'], sorted_wbs['Layer']))
            fig = visualizer.create_dependency_graph_figure(
                graph, scc_map, layer_map, viz_params)
            self.graph_canvas.figure = fig
            self.graph_canvas.draw()

            merged_fig = visualizer.create_dependency_graph_figure(
                self.merged_graph,
                merged_scc_map,
                merged_layer_map,
                viz_params,
            )
            self.merged_graph_canvas.figure = merged_fig
            self.merged_graph_canvas.draw()

            # 更新圖表尺寸
            self.graph_canvas.draw()  # 確保圖表已經繪製完成
            canvas_size = self.graph_canvas.get_width_height()
            if canvas_size[0] > 0 and canvas_size[1] > 0:
                self.graph_container.setMinimumSize(
                    int(canvas_size[0] * 1.1),  # 稍微加大一點，留些邊距
                    int(canvas_size[1] * 1.1),
                )

            self.merged_graph_canvas.draw()
            m_size = self.merged_graph_canvas.get_width_height()
            if m_size[0] > 0 and m_size[1] > 0:
                self.merged_graph_container.setMinimumSize(
                    int(m_size[0] * 1.1),
                    int(m_size[1] * 1.1),
                )

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
            self.gantt_display_combo.blockSignals(True)
            self.gantt_display_combo.clear()
            self.gantt_display_combo.addItems(list(self.gantt_results.keys()))
            self.gantt_display_combo.blockSignals(False)
            self.gantt_display_combo.setCurrentIndex(0)
            self.update_gantt_display()

            QMessageBox.information(self, 'CPM 分析完成', 'CPM 分析已完成')
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, '錯誤', f'CPM 分析失敗：{e}')

    def run_full_analysis(self):
        """依序執行基本分析與 CPM 分析"""
        success = self.runAnalysis()
        if success:
            self.runCmpAnalysis()

    def drawGanttChart(self, cpmData, durations):
        """繪製甘特圖"""
        try:
            self.gantt_figure.clear()

            # 創建子圖，並設定外邊距
            ax = self.gantt_figure.add_subplot(111)

            # 設定更大的外邊距
            self.gantt_figure.subplots_adjust(
                top=0.9,      # 上邊距
                bottom=0.15,  # 下邊距
                left=0.2,     # 左邊距
                right=0.95    # 右邊距
            )

            # 取得任務列表和相關數據
            tasks = cpmData.index.tolist()
            start_times = cpmData['ES'].tolist()
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
            ax.set_yticklabels(tasks, fontsize=10, fontweight='bold')

            # 加強網格線
            ax.grid(
                True,
                axis='x',
                linestyle='--',
                color='gray',
                alpha=0.3,
                zorder=1,
            )
            ax.set_axisbelow(True)

            # 設定標籤和標題
            ax.set_xlabel('時間 (小時)', fontsize=11, fontweight='bold')
            ax.set_title(
                '專案甘特圖 (紅色為關鍵路徑)',
                fontsize=14,
                pad=20,
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
                    )

            # 反轉 Y 軸
            ax.invert_yaxis()

            # 建立新的捲動區域，支援水平和垂直捲動
            scroll_area = QScrollArea()
            scroll_area.setWidget(self.gantt_canvas)
            scroll_area.setWidgetResizable(True)

            # 確保水平和垂直捲動條都可見
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

            # 設定更大的視窗尺寸，增加上下空間
            scroll_area.setMinimumHeight(1000)  # 增加最小高度
            self.gantt_canvas.setMinimumSize(1200, max(1000, len(tasks) * 35))

            # 設定捲動區域的邊距
            container_layout = QVBoxLayout()
            container_layout.setContentsMargins(20, 40, 20, 40)  # 左、上、右、下邊距
            container_layout.addWidget(scroll_area)

            # 更新分頁中的內容，保留最上方的切換下拉選單
            layout = self.tab_gantt_chart.layout()
            if layout.count() > 1:
                old_item = layout.takeAt(1)
                if old_item.widget():
                    old_item.widget().deleteLater()

            # 建立容器來包裝捲動區域
            container = QWidget()
            container.setLayout(container_layout)
            self.tab_gantt_chart.layout().addWidget(container)

            # 重繪圖表
            self.gantt_canvas.draw()

        except Exception as e:
            QMessageBox.warning(self, '警告', f'甘特圖繪製失敗：{e}')

    def update_gantt_display(self):
        """根據下拉選單切換甘特圖與結果顯示"""
        key = self.gantt_display_combo.currentText()
        if key not in self.gantt_results:
            return
        cpm_df, durations, wbs_df, project_end = self.gantt_results[key]
        self.cmp_result = wbs_df
        self.critical_path = findCriticalPath(cpm_df)
        self.cmp_result_view.setModel(PandasModel(wbs_df.head(100)))
        self.drawGanttChart(cpm_df, durations)

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
        else:
            self.setStyleSheet("")
            plt.style.use('default')
            self.is_dark_mode = False

        # 重繪圖表
        self.redraw_graph()

    def redraw_graph(self):
        """重新繪製依賴關係圖"""
        if not hasattr(self, 'graph') or self.graph is None:
            return

        if hasattr(self, 'sorted_wbs') and self.sorted_wbs is not None:
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                viz_params = config.get('visualization_params', {})

                # 取得 SCC_ID 和 Layer 的映射
                scc_map = dict(
                    zip(
                        self.sorted_wbs['Task ID'],
                        self.sorted_wbs['SCC_ID'],
                    )
                )
                layer_map = dict(
                    zip(
                        self.sorted_wbs['Task ID'],
                        self.sorted_wbs['Layer'],
                    )
                )

                # 重新建立圖表
                fig = visualizer.create_dependency_graph_figure(
                    self.graph, scc_map, layer_map, viz_params)
                self.graph_canvas.figure = fig

                # 更新圖表尺寸
                self.graph_canvas.draw()
                canvas_size = self.graph_canvas.get_width_height()
                if canvas_size[0] > 0 and canvas_size[1] > 0:
                    self.graph_container.setMinimumSize(
                        int(canvas_size[0] * 1.1),  # 稍微加大一點，留些邊距
                        int(canvas_size[1] * 1.1)
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


def main():
    app = QApplication(sys.argv)
    window = BirdmanQtApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
