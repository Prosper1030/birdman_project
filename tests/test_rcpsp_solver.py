import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

import pandas as pd  # noqa: E402
import networkx as nx  # noqa: E402
from src.rcpsp_solver import solveRcpsp  # noqa: E402


def test_solve_rcpsp_basic():
    """測試 solveRcpsp 輸出包含各任務開始時間與 ProjectEnd"""
    # 建立簡單的依賴圖 A -> B
    graph = nx.DiGraph()
    graph.add_edge("A", "B")

    # 建立 WBS 資料
    wbs = pd.DataFrame(
        {
            "Task ID": ["A", "B"],
            "Te_newbie": [2, 3],
            "Category": ["R1", "R2"],
            "ResourceDemand": [1, 1],
        }
    )

    schedule = solveRcpsp(graph, wbs)

    assert set(["A", "B", "ProjectEnd"]).issubset(schedule)
    assert schedule["A"] == 0
    assert schedule["B"] == schedule["A"] + 2
    assert schedule["ProjectEnd"] == schedule["B"] + 3


def test_resource_demand_affects_schedule():
    """測試 ResourceDemand 會影響排程，需求量超過容量時不可並行"""
    graph = nx.DiGraph()
    graph.add_nodes_from(["A", "B"])  # 兩任務無依賴

    wbs = pd.DataFrame(
        {
            "Task ID": ["A", "B"],
            "Te_newbie": [2, 3],
            "Category": ["R1", "R1"],
            "ResourceDemand": [2, 1],
        }
    )

    schedule = solveRcpsp(graph, wbs, resourceCap={"R1": 2})

    assert schedule["ProjectEnd"] == 5
    assert schedule["A"] + 2 <= schedule["B"] or schedule["B"] + 3 <= schedule["A"]
