# -*- coding: utf-8 -*-
"""
PyQt5 進階 GUI，支援分頁切換與 DataFrame 表格預覽
"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QTabWidget, QLabel, QTableView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import pandas as pd
from .dsm_processor import readDsm, buildGraph, computeLayersAndScc, reorderDsm
from .wbs_processor import readWbs, mergeByScc, validateIds
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
            # 非第一欄且值為1
            if index.column() > 0:
                try:
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
                return str(self._df.index[section])
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
        self.tabs.addTab(self.tab_raw_dsm, '原始 DSM')
        self.tabs.addTab(self.tab_raw_wbs, '原始 WBS')
        self.tabs.addTab(self.tab_sorted_wbs, '排序 WBS')
        self.tabs.addTab(self.tab_merged_wbs, '合併 WBS')
        self.tabs.addTab(self.tab_sorted_dsm, '排序 DSM')
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

            graph = buildGraph(dsm)
            layers, scc_map = computeLayersAndScc(graph)
            validateIds(wbs, dsm)
            wbs_for_sort = wbs.copy()
            wbs_for_sort["Layer"] = wbs_for_sort["Task ID"].map(layers).fillna(-1).astype(int)
            wbs_for_sort["SCC_ID"] = wbs_for_sort["Task ID"].map(scc_map).fillna(-1).astype(int)
            sorted_wbs = wbs_for_sort.sort_values(by=["Layer", "Task ID"]).reset_index(drop=True)
            self.sorted_wbs = self._add_no_column(sorted_wbs)
            self.sorted_dsm = reorderDsm(dsm, sorted_wbs["Task ID"].tolist())
            # 合併 WBS 並讓 No. 連號從 1 開始
            merged = mergeByScc(sorted_wbs)
            self.merged_wbs = self._add_no_column(merged)
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
