# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QTabWidget, QLabel, QTableView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
from .dsm_processor import readDsm, reorderDsm, buildGraph, computeLayersAndScc, process_dsm
from .wbs_processor import readWbs, mergeByScc, validateIds
from . import visualizer
from pandas import DataFrame
from PyQt5.QtCore import QAbstractTableModel

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
            except Exception:
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
        export_layout.addWidget(export_sorted_btn)
        export_layout.addWidget(export_merged_btn)
        export_layout.addWidget(export_dsm_btn)
        main_layout.addLayout(export_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 表格
        self.raw_dsm_view = QTableView()
        self.raw_wbs_view = QTableView()
        self.sorted_wbs_view = QTableView()
        self.merged_wbs_view = QTableView()
        self.sorted_dsm_view = QTableView()
        # 依賴關係圖畫布
        self.graph_figure = Figure(figsize=(6, 4))
        self.graph_canvas = FigureCanvas(self.graph_figure)
        # 只在 WBS 相關表格隱藏行號
        for view in [self.raw_wbs_view, self.sorted_wbs_view, self.merged_wbs_view]:
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
        self.tab_graph.layout().addWidget(self.graph_canvas)

    def chooseDsm(self):
        path, _ = QFileDialog.getOpenFileName(self, '選擇 DSM 檔案', '', 'CSV Files (*.csv)')
        if path:
            self.dsm_path = path
            self.dsm_path_label.setText(path)
            try:
                dsm = readDsm(path)
                self.raw_dsm_view.setModel(PandasModel(dsm.head(100), dsm_mode=True))
            except Exception as e:
                QMessageBox.critical(self, '錯誤', f'DSM 載入失敗：{e}')

    def chooseWbs(self):
        path, _ = QFileDialog.getOpenFileName(self, '選擇 WBS 檔案', '', 'CSV Files (*.csv)')
        if path:
            self.wbs_path = path
            self.wbs_path_label.setText(path)
            try:
                wbs = readWbs(path)
                wbs = self._add_no_column(wbs)
                self.raw_wbs_view.setModel(PandasModel(wbs.head(100)))
            except Exception as e:
                QMessageBox.critical(self, '錯誤', f'WBS 載入失敗：{e}')

    def runAnalysis(self):
        try:
            dsm = readDsm(self.dsm_path)
            wbs = readWbs(self.wbs_path)
            # 預覽原始資料
            self.raw_dsm_view.setModel(PandasModel(dsm.head(100), dsm_mode=True))
            wbs_with_no = self._add_no_column(wbs)
            self.raw_wbs_view.setModel(PandasModel(wbs_with_no.head(100)))

            validateIds(wbs, dsm)

            sorted_dsm, sorted_wbs, graph = process_dsm(dsm, wbs)
            self.sorted_wbs = self._add_no_column(sorted_wbs)
            self.sorted_dsm = sorted_dsm

            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            k_params = config.get('merge_k_params', {})
            viz_params = config.get('visualization_params', {})

            merged = mergeByScc(sorted_wbs, k_params)
            self.merged_wbs = self._add_no_column(merged)

            scc_map = dict(zip(sorted_wbs['Task ID'], sorted_wbs['SCC_ID']))
            fig = visualizer.create_dependency_graph_figure(graph, scc_map, viz_params)
            self.graph_canvas.figure = fig
            self.graph_canvas.draw()
            # 預覽
            self.sorted_wbs_view.setModel(PandasModel(self.sorted_wbs.head(100)))
            self.merged_wbs_view.setModel(PandasModel(self.merged_wbs.head(100)))
            self.sorted_dsm_view.setModel(PandasModel(self.sorted_dsm.head(100), dsm_mode=True))
            QMessageBox.information(self, '完成', '分析完成，可切換分頁預覽與匯出')
        except Exception as e:
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
            except Exception:
                pass
        df.insert(0, 'No.', range(1, len(df) + 1))
        return df

    def exportSortedWbs(self):
        if self.sorted_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        path, _ = QFileDialog.getSaveFileName(self, '匯出排序 WBS', '', 'CSV Files (*.csv)')
        if path:
            self.sorted_wbs.to_csv(path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, '完成', f'已匯出 {path}')

    def exportMergedWbs(self):
        if self.merged_wbs is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        path, _ = QFileDialog.getSaveFileName(self, '匯出合併 WBS', '', 'CSV Files (*.csv)')
        if path:
            # 匯出時保留 No. 欄位
            self.merged_wbs.to_csv(path, encoding='utf-8-sig')
            QMessageBox.information(self, '完成', f'已匯出 {path}')

    def exportSortedDsm(self):
        if self.sorted_dsm is None:
            QMessageBox.warning(self, '警告', '請先執行分析')
            return
        path, _ = QFileDialog.getSaveFileName(self, '匯出排序 DSM', '', 'CSV Files (*.csv)')
        if path:
            self.sorted_dsm.to_csv(path, encoding='utf-8-sig')
            QMessageBox.information(self, '完成', f'已匯出 {path}')

def main():
    app = QApplication(sys.argv)
    window = BirdmanQtApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
