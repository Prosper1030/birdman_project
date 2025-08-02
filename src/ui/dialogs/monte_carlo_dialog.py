"""蒙地卡羅模擬對話框"""

from typing import List

import networkx as nx
import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
)

from ...cpm_processor import cpmForwardPass


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
        simulation_results: List[float] = []
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


class MonteCarloDialog(QDialog):
    """蒙地卡羅模擬對話框"""

    def __init__(
        self,
        wbs_df: pd.DataFrame,
        graph: nx.DiGraph,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self.wbs_df = wbs_df
        self.merged_graph = graph
        self.thread: QThread | None = None
        self.worker: MonteCarloWorker | None = None
        self.initUI()

    def initUI(self) -> None:
        """初始化介面"""
        self.setWindowTitle("蒙地卡羅模擬")
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.role_select_combo = QComboBox(self)
        self.role_select_combo.addItems(["新手 (Novice)", "專家 (Expert)"])
        form_layout.addRow(QLabel("模擬角色"), self.role_select_combo)

        self.iterations_spinbox = QSpinBox(self)
        self.iterations_spinbox.setMaximum(100000)
        self.iterations_spinbox.setValue(1000)
        form_layout.addRow(QLabel("模擬次數"), self.iterations_spinbox)

        layout.addLayout(form_layout)

        self.progress_bar = QProgressBar(self)
        layout.addWidget(self.progress_bar)

        self.run_button = QPushButton("開始模擬", self)
        self.run_button.clicked.connect(self.run_simulation)
        layout.addWidget(self.run_button)

    def run_simulation(self) -> None:
        """執行模擬"""
        self.run_button.setEnabled(False)
        role_key = (
            "newbie"
            if self.role_select_combo.currentText() == "新手 (Novice)"
            else "expert"
        )
        iterations = self.iterations_spinbox.value()
        self.progress_bar.setMaximum(iterations)
        self.thread = QThread()
        self.worker = MonteCarloWorker(
            self.wbs_df, self.merged_graph, role_key, iterations
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.simulation_finished)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def simulation_finished(self, results: List[float]) -> None:
        """模擬完成後處理結果"""
        self.plot_results(results)
        self.run_button.setEnabled(True)

    def plot_results(self, results: List[float]) -> None:
        """顯示模擬結果"""
        if not results:
            QMessageBox.information(self, "模擬完成", "無有效結果")
            return
        arr = np.array(results, dtype=float)
        avg = float(arr.mean())
        QMessageBox.information(
            self,
            "模擬完成",
            f"平均完工時間：{avg:.2f} 小時",
        )
