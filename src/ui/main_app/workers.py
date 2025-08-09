"""背景工作模組"""

from __future__ import annotations

import networkx as nx
import numpy as np
from pandas import DataFrame

from PyQt5.QtCore import QObject, pyqtSignal

from ...cpm_processor import cpmForwardPass


class MonteCarloWorker(QObject):
    """執行蒙地卡羅模擬的背景工作執行緒"""

    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(
        self,
        wbs_df: DataFrame,
        graph: nx.DiGraph,
        role_key: str,
        iterations: int,
        parent: QObject | None = None,
    ) -> None:
        """初始化背景工作者。

        Args:
            wbs_df: 任務資料表。
            graph: 依賴關係圖。
            role_key: 角色鍵值（newbie 或 expert）。
            iterations: 模擬次數。
            parent: 父物件，預設為 ``None``。
        """
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


__all__ = ["MonteCarloWorker"]
