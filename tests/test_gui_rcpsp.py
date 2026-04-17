import os
import time
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
            "Property": ["AER", "AER"],
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


def test_rcpsp_prefers_eligible_groups_over_property(tmp_path):
    """GUI RCPSP 應優先使用 Eligible_Groups 對應資源群組。"""
    app = QApplication.instance() or QApplication([])

    gui = BirdmanQtApp()
    wbs = pd.DataFrame(
        {
            "Task ID": ["T1", "T2"],
            "Te_newbie": [3, 3],
            "Property": ["A", "A"],
            "Eligible_Groups": ["R1", "R2"],
            "ResourceDemand": [1, 1],
        }
    )
    resource_path = tmp_path / "Resources.csv"
    pd.DataFrame(
        {
            "Group": ["R1", "R2"],
            "Headcount_Cap": [1, 1],
        }
    ).to_csv(resource_path, index=False, encoding="utf-8-sig")

    gui.mergedWbs = wbs
    graph = nx.DiGraph()
    graph.add_nodes_from(["T1", "T2"])
    gui.mergedGraph = graph
    gui.resourcePath = str(resource_path)

    schedule = gui.runRcpspOptimization(showDialog=False)

    assert schedule is not None
    assert schedule["T1"] == 0
    assert schedule["T2"] == 0
    assert schedule["ProjectEnd"] == 3

    app.quit()


def test_rcpsp_button_click_opens_result_flow(tmp_path):
    """直接按 RCPSP 按鈕時，應啟動結果顯示流程。"""
    app = QApplication.instance() or QApplication([])

    gui = BirdmanQtApp()
    wbs = pd.DataFrame(
        {
            "Task ID": ["T1", "T2"],
            "Te_newbie": [3, 3],
            "Property": ["A", "A"],
            "Eligible_Groups": ["R1", "R2"],
            "ResourceDemand": [1, 1],
        }
    )
    resource_path = tmp_path / "Resources.csv"
    pd.DataFrame(
        {
            "Group": ["R1", "R2"],
            "Headcount_Cap": [1, 1],
        }
    ).to_csv(resource_path, index=False, encoding="utf-8-sig")

    gui.mergedWbs = wbs
    graph = nx.DiGraph()
    graph.add_nodes_from(["T1", "T2"])
    gui.mergedGraph = graph
    gui.resourcePath = str(resource_path)

    captured: dict[str, object] = {}

    def capture_result(schedule, duration_field):
        captured["schedule"] = schedule
        captured["duration_field"] = duration_field

    gui.showRcpspResult = capture_result  # type: ignore[method-assign]

    gui.runRcpspButton.clicked.emit(False)

    deadline = time.time() + 2
    while time.time() < deadline and "schedule" not in captured:
        app.processEvents()
        time.sleep(0.01)

    assert "schedule" in captured
    assert captured["duration_field"] == "Te_newbie"
    assert gui.rcpspLastSchedule is not None
    assert gui.rcpspStatusLabel.text().startswith("RCPSP 完成")

    gui.close()
    app.processEvents()
    app.quit()
