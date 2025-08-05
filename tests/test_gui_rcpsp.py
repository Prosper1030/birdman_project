import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from src.gui_qt import BirdmanQtApp  # noqa: E402


def test_rcpsp_schedule_with_custom_capacity():
    """測試 GUI 可使用自訂資源容量並取得 RCPSP 結果"""
    app = QApplication.instance() or QApplication([])

    gui = BirdmanQtApp()
    wbs = pd.DataFrame(
        {
            "Task ID": ["T1", "T2"],
            "Te_newbie": [3, 3],
            "Category": ["AER", "AER"],
            "ResourceDemand": [1, 1],
        }
    )
    gui.mergedWbs = wbs
    graph = nx.DiGraph()
    graph.add_nodes_from(["T1", "T2"])
    gui.mergedGraph = graph
    gui.resourcePath = "sample_data/Resources.csv"
    gui.manualResourceCap = {"AER": 2}

    schedule = gui.runRcpspOptimization(showDialog=False)
    assert schedule is not None
    assert schedule["T1"] == 0
    assert schedule["T2"] == 0
    assert schedule["ProjectEnd"] == 3

    app.quit()
