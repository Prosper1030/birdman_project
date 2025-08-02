"""主視窗模組"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QComboBox,
    QLabel,
    QSpinBox,
    QMessageBox,
)
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure

from ..cpm_processor import cpmForwardPass


class MonteCarloWorker(QObject):
    """執行蒙地卡羅模擬的背景工作執行緒"""

    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(
        self,
        wbs_df: pd.DataFrame,
        graph: nx.DiGraph,
        role_key: str,
        iterations: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.wbs_df = wbs_df
        self.graph = graph
        self.role_key = role_key
        self.iterations = iterations
        self.is_running = True

    def run(self) -> None:
        """執行模擬並回報進度"""
        o_col = f"O_{self.role_key}"
        m_col = f"M_{self.role_key}"
        p_col = f"P_{self.role_key}"
        for field in (o_col, m_col, p_col):
            if field not in self.wbs_df.columns:
                self.finished.emit([])
                return
        wbs_df = self.wbs_df.set_index("Task ID")
        simulation_results: list[float] = []
        for i in range(max(1, self.iterations)):
            if not self.is_running:
                break
            sampled: dict[str, float] = {}
            for task_id in wbs_df.index:
                o = wbs_df.loc[task_id, o_col]
                m = wbs_df.loc[task_id, m_col]
                p = wbs_df.loc[task_id, p_col]
                if p == o:
                    simulated_duration = o
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
                    random_beta = np.random.beta(alpha, beta)
                    simulated_duration = o + random_beta * (p - o)
                sampled[task_id] = float(simulated_duration)
            forward = cpmForwardPass(self.graph, sampled)
            project_end = max(v[1] for v in forward.values())
            simulation_results.append(project_end)
            self.progress.emit(i + 1)
            if not self.is_running:
                break
        self.finished.emit(simulation_results)

    def stop(self) -> None:
        """停止模擬"""
        self.is_running = False


class MainWindow(QWidget):
    """主視窗，負責建立各個分頁"""

    def __init__(self) -> None:
        super().__init__()
        self.merged_graph: nx.DiGraph | None = None
        self.merged_wbs: pd.DataFrame | None = None
        self._create_monte_carlo_tab()

    def _create_monte_carlo_tab(self) -> None:
        """建立蒙地卡羅模擬分頁"""
        container = QVBoxLayout()
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel('分析對象:'))
        self.mc_role_select_combo = QComboBox()
        self.mc_role_select_combo.addItems(['新手 (Novice)', '專家 (Expert)'])
        control_layout.addWidget(self.mc_role_select_combo)

        control_layout.addWidget(QLabel('模擬次數:'))
        self.mc_iterations_spinbox = QSpinBox()
        self.mc_iterations_spinbox.setMaximum(100000)
        self.mc_iterations_spinbox.setValue(1000)
        control_layout.addWidget(self.mc_iterations_spinbox)

        self.mc_run_button = QPushButton('開始模擬')
        control_layout.addWidget(self.mc_run_button)

        self.mc_progress_bar = QProgressBar()
        control_layout.addWidget(self.mc_progress_bar)

        control_layout.addStretch()
        container.addLayout(control_layout)

        result_layout = QHBoxLayout()
        self.mc_figure = Figure(figsize=(5, 4))
        self.mc_canvas = FigureCanvas(self.mc_figure)
        result_layout.addWidget(self.mc_canvas)

        stats_layout = QVBoxLayout()
        self.mc_mean_label = QLabel('平均總工時：-')
        self.mc_std_label = QLabel('標準差：-')
        self.mc_p50_label = QLabel('50% 完成機率：-')
        self.mc_p85_label = QLabel('85% 完成機率：-')
        self.mc_p95_label = QLabel('95% 完成機率：-')
        for lbl in (
            self.mc_mean_label,
            self.mc_std_label,
            self.mc_p50_label,
            self.mc_p85_label,
            self.mc_p95_label,
        ):
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()
        result_layout.addLayout(stats_layout)

        container.addLayout(result_layout)
        self.setLayout(container)

        # 連接模擬按鈕的事件，按下後執行蒙地卡羅模擬
        self.mc_run_button.clicked.connect(self.run_monte_carlo_simulation)

    def run_monte_carlo_simulation(self) -> None:
        """執行蒙地卡羅模擬"""
        # 步驟 1: 禁用按鈕、重設進度條，防止重複執行
        self.mc_run_button.setEnabled(False)
        iterations = self.mc_iterations_spinbox.value()
        self.mc_progress_bar.setValue(0)
        self.mc_progress_bar.setMaximum(iterations)

        # 步驟 2: 準備傳遞給背景執行緒的參數
        role_key = (
            'newbie'
            if self.mc_role_select_combo.currentText() == '新手 (Novice)'
            else 'expert'
        )

        # 檢查是否有圖可供分析
        if not self.merged_graph:
            QMessageBox.warning(
                self,
                '錯誤',
                '請先執行一次基礎分析，產生合併後的依賴關係圖。',
            )
            self.mc_run_button.setEnabled(True)
            return

        # 步驟 3: 建立 Worker 和 Thread
        self.mc_thread = QThread()
        self.mc_worker = MonteCarloWorker(
            self.merged_wbs, self.merged_graph, role_key, iterations
        )
        self.mc_worker.moveToThread(self.mc_thread)

        # 步驟 4: 連接信號與槽
        # 將 Worker 的信號連接到主視窗的處理函式上
        self.mc_thread.started.connect(self.mc_worker.run)
        self.mc_worker.progress.connect(self.update_mc_progress)
        self.mc_worker.finished.connect(self.handle_mc_results)

        # 設定執行緒結束後的清理工作
        self.mc_worker.finished.connect(self.mc_thread.quit)
        self.mc_worker.finished.connect(self.mc_worker.deleteLater)
        self.mc_thread.finished.connect(self.mc_thread.deleteLater)

        # 步驟 5: 啟動執行緒
        self.mc_thread.start()

    def update_mc_progress(self, value: int) -> None:
        """更新蒙地卡羅進度條"""
        self.mc_progress_bar.setValue(value)

    def handle_mc_results(self, results: list[float]) -> None:
        """處理模擬完成後的結果，並更新UI"""
        self.plot_mc_results(results)
        self.mc_run_button.setEnabled(True)
        QMessageBox.information(self, '完成', '蒙地卡羅模擬已完成！')

    def plot_mc_results(self, results: list[float]) -> None:
        """將模擬結果繪製成直方圖並顯示統計數據"""
        arr = np.array(results, dtype=float)
        if arr.size == 0:
            return
        avg = float(arr.mean())
        std = float(arr.std())
        p50 = float(np.percentile(arr, 50))
        p85 = float(np.percentile(arr, 85))
        p95 = float(np.percentile(arr, 95))

        self.mc_mean_label.setText(f'平均總工時：{avg:.2f}')
        self.mc_std_label.setText(f'標準差：{std:.2f}')
        self.mc_p50_label.setText(f'50% 完成機率：{p50:.2f}')
        self.mc_p85_label.setText(f'85% 完成機率：{p85:.2f}')
        self.mc_p95_label.setText(f'95% 完成機率：{p95:.2f}')

        self.mc_figure.clear()
        ax = self.mc_figure.add_subplot(111)
        ax.hist(arr, bins=30, color='skyblue', edgecolor='black')
        ax.set_title('完工時間分佈')
        ax.set_xlabel('工時 (小時)')
        ax.set_ylabel('頻率')
        self.mc_canvas.draw()
