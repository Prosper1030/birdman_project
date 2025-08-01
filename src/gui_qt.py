# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
import json

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
    QAction,
    QDialogButtonBox,
    QScrollArea,
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

from .dsm_processor import readDsm, process_dsm
from .wbs_processor import readWbs, mergeByScc, validateIds
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
        file_layout = QHBoxLayout()

        self.dsm_label = QLabel('DSM 檔案:')
        self.dsm_path_label = QLabel('')
        dsm_btn = QPushButton('選擇')
        dsm_btn.clicked.connect(self.chooseDsm)
        file_layout.addWidget(self.dsm_label)
        file_layout.addWidget(self.dsm_path_label)
        file_layout.addWidget(dsm_btn)

        self.wbs_label = QLabel('WBS 檔案:')
        self.wbs_path_label = QLabel('')
        wbs_btn = QPushButton('選擇')
        wbs_btn.clicked.connect(self.chooseWbs)
        file_layout.addWidget(self.wbs_label)
        file_layout.addWidget(self.wbs_path_label)
        file_layout.addWidget(wbs_btn)

        # 頂端選單列
        menubar = self.menuBar()
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

        run_btn = QPushButton('執行分析')
        run_btn.clicked.connect(self.runAnalysis)
        file_layout.addWidget(run_btn)

        main_layout.addLayout(file_layout)

        # 分頁
        self.tabs = QTabWidget()
        self.tab_raw_dsm = QWidget()
        self.tab_raw_wbs = QWidget()
        self.tab_sorted_wbs = QWidget()
        self.tab_merged_wbs = QWidget()
        self.tab_sorted_dsm = QWidget()
        self.tab_graph = QWidget()
        self.tabs.addTab(self.tab_raw_dsm, '原始 DSM')
        self.tabs.addTab(self.tab_raw_wbs, '原始 WBS')
        self.tabs.addTab(self.tab_sorted_wbs, '排序 WBS')
        self.tabs.addTab(self.tab_merged_wbs, '合併 WBS')
        self.tabs.addTab(self.tab_sorted_dsm, '排序 DSM')
        self.tabs.addTab(self.tab_graph, '依賴關係圖')
        main_layout.addWidget(self.tabs)

        # 匯出按鈕
        export_layout = QHBoxLayout()
        export_sorted_btn = QPushButton('匯出排序 WBS')
        export_sorted_btn.clicked.connect(self.exportSortedWbs)
        export_merged_btn = QPushButton('匯出合併 WBS')
        export_merged_btn.clicked.connect(self.exportMergedWbs)
        export_dsm_btn = QPushButton('匯出排序 DSM')
        export_dsm_btn.clicked.connect(self.exportSortedDsm)
        export_graph_btn = QPushButton('匯出依賴圖')
        export_graph_btn.clicked.connect(self.exportGraph)
        export_layout.addWidget(export_sorted_btn)
        export_layout.addWidget(export_merged_btn)
        export_layout.addWidget(export_dsm_btn)
        export_layout.addWidget(export_graph_btn)
        main_layout.addLayout(export_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 表格
        self.raw_dsm_view = QTableView()
        self.raw_wbs_view = QTableView()
        self.sorted_wbs_view = QTableView()
        self.merged_wbs_view = QTableView()
        self.sorted_dsm_view = QTableView()
        # 依賴關係圖畫布及捲動區域
        self.graph_figure = Figure(figsize=(18, 20))  # 使用與 visualizer.py 相同的尺寸
        self.graph_canvas = FigureCanvas(self.graph_figure)
        
        # 建立外層容器（用於控制大小和捲動）
        self.graph_outer_container = QWidget()
        self.graph_outer_layout = QVBoxLayout(self.graph_outer_container)
        self.graph_outer_layout.setContentsMargins(0, 0, 0, 0)
        
        # 建立內層容器（實際持有圖表）
        self.graph_container = QWidget()
        self.graph_container_layout = QVBoxLayout(self.graph_container)
        self.graph_container_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_container_layout.addWidget(self.graph_canvas)
        
        # 設定固定的參考尺寸
        self.graph_container.setMinimumSize(1000, 800)
        
        # 建立捲動區域
        self.scroll_area = QScrollArea(self.graph_outer_container)
        self.scroll_area.setWidget(self.graph_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.graph_outer_layout.addWidget(self.scroll_area)
        
        # 只在 WBS 相關表格隱藏行號
        for view in [
            self.raw_wbs_view,
            self.sorted_wbs_view,
            self.merged_wbs_view,
        ]:
            view.verticalHeader().setVisible(False)
        # DSM 表格顯示行號 (Task ID)
        self.raw_dsm_view.verticalHeader().setVisible(True)
        self.sorted_dsm_view.verticalHeader().setVisible(True)
        self.tab_raw_dsm.setLayout(QVBoxLayout())
        self.tab_raw_dsm.layout().addWidget(self.raw_dsm_view)
        self.tab_raw_wbs.setLayout(QVBoxLayout())
        self.tab_raw_wbs.layout().addWidget(self.raw_wbs_view)
        self.tab_sorted_wbs.setLayout(QVBoxLayout())
        self.tab_sorted_wbs.layout().addWidget(self.sorted_wbs_view)
        self.tab_merged_wbs.setLayout(QVBoxLayout())
        self.tab_merged_wbs.layout().addWidget(self.merged_wbs_view)
        self.tab_sorted_dsm.setLayout(QVBoxLayout())
        self.tab_sorted_dsm.layout().addWidget(self.sorted_dsm_view)
        self.tab_graph.setLayout(QVBoxLayout())
        self.tab_graph.layout().addWidget(self.graph_outer_container)

    def chooseDsm(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '選擇 DSM 檔案', '', 'CSV Files (*.csv)')
        if path:
            self.dsm_path = path
            self.dsm_path_label.setText(path)
            try:
                dsm = readDsm(path)
                self.raw_dsm_view.setModel(
                    PandasModel(dsm.head(100), dsm_mode=True))
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
                self.raw_wbs_view.setModel(PandasModel(wbs.head(100)))
            except (OSError, pd.errors.ParserError, ValueError) as e:
                QMessageBox.critical(self, '錯誤', f'WBS 載入失敗：{e}')

    def runAnalysis(self):
        try:
            dsm = readDsm(self.dsm_path)
            wbs = readWbs(self.wbs_path)
            # 預覽原始資料
            self.raw_dsm_view.setModel(
                PandasModel(dsm.head(100), dsm_mode=True))
            wbs_with_no = self._add_no_column(wbs)
            self.raw_wbs_view.setModel(PandasModel(wbs_with_no.head(100)))

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

            scc_map = dict(zip(sorted_wbs['Task ID'], sorted_wbs['SCC_ID']))
            layer_map = dict(zip(sorted_wbs['Task ID'], sorted_wbs['Layer']))
            fig = visualizer.create_dependency_graph_figure(
                graph, scc_map, layer_map, viz_params)
            self.graph_canvas.figure = fig
            self.graph_canvas.draw()
            
            # 更新圖表尺寸
            self.graph_canvas.draw()  # 確保圖表已經繪製完成
            canvas_size = self.graph_canvas.get_width_height()
            if canvas_size[0] > 0 and canvas_size[1] > 0:
                self.graph_container.setMinimumSize(
                    int(canvas_size[0] * 1.1),  # 稍微加大一點，留些邊距
                    int(canvas_size[1] * 1.1)
                )
            
            # 預覽
            self.sorted_wbs_view.setModel(
                PandasModel(self.sorted_wbs.head(100)))
            self.merged_wbs_view.setModel(
                PandasModel(self.merged_wbs.head(100)))
            self.sorted_dsm_view.setModel(PandasModel(
                self.sorted_dsm.head(100), dsm_mode=True))
            QMessageBox.information(self, '完成', '分析完成，可切換分頁預覽與匯出')
        except Exception as e:  # pylint: disable=broad-except
            # 執行流程中可能發生多種錯誤，此處統一彙整顯示訊息
            QMessageBox.critical(self, '錯誤', str(e))

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

    def exportMergedWbs(self):
        if self.merged_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出合併 WBS', '', 'CSV Files (*.csv)')
        if path:
            # 匯出時保留 No. 欄位
            self.merged_wbs.to_csv(path, encoding='utf-8-sig')
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

    def exportGraph(self):
        """匯出依賴關係圖"""
        if not hasattr(self, 'graph') or self.graph is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return

        # 設定檔案過濾器
        file_filter = 'SVG 向量圖 (*.svg);;PNG 圖片 (*.png)'
        path, selected_filter = QFileDialog.getSaveFileName(
            self, '匯出依賴關係圖', '', file_filter)
        
        if not path:
            return  # 使用者取消

        try:
            # 根據選擇的過濾器決定檔案格式
            if selected_filter == 'SVG 向量圖 (*.svg)':
                if not path.lower().endswith('.svg'):
                    path += '.svg'
                self.graph_canvas.figure.savefig(path, format='svg', 
                                               bbox_inches='tight',
                                               dpi=300)
            else:  # PNG
                if not path.lower().endswith('.png'):
                    path += '.png'
                self.graph_canvas.figure.savefig(path, format='png',
                                               bbox_inches='tight',
                                               dpi=300)
            
            QMessageBox.information(self, '完成', f'已匯出依賴關係圖至：{path}')
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, '錯誤', f'匯出圖檔時發生錯誤：{e}')

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

        # 重新繪製圖表
        if hasattr(self, 'sorted_wbs') and self.sorted_wbs is not None:
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                viz_params = config.get('visualization_params', {})

                scc_map = dict(
                    zip(self.sorted_wbs['Task ID'], self.sorted_wbs['SCC_ID']))
                layer_map = dict(
                    zip(self.sorted_wbs['Task ID'], self.sorted_wbs['Layer']))
                fig = visualizer.create_dependency_graph_figure(
                    self.graph, scc_map, layer_map, viz_params)
                self.graph_canvas.figure = fig
                self.graph_canvas.draw()
                
                # 更新圖表尺寸
                self.graph_canvas.draw()  # 確保圖表已經繪製完成
                canvas_size = self.graph_canvas.get_width_height()
                if canvas_size[0] > 0 and canvas_size[1] > 0:
                    self.graph_container.setMinimumSize(
                        int(canvas_size[0] * 1.1),  # 稍微加大一點，留些邊距
                        int(canvas_size[1] * 1.1)
                    )
            except Exception as e:  # pylint: disable=broad-except
                # 圖表重繪過程可能因設定檔或數據問題失敗
                QMessageBox.warning(self, '警告', f'圖表重繪失敗：{e}')


def main():
    app = QApplication(sys.argv)
    window = BirdmanQtApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
