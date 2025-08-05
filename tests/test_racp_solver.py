import pandas as pd
import networkx as nx

from src.racp_solver import solve_racp_basic


def test_solve_racp_basic_simple():
    graph = nx.DiGraph()
    graph.add_edge("T1", "T2")
    wbs = pd.DataFrame({
        "Task ID": ["T1", "T2"],
        "Eligible_Groups": ["G1;G2", "G1"],
        "Te_newbie": [2, 2],
        "ResourceDemand": [1, 1],
    })
    result = solve_racp_basic(graph, wbs, deadline=4)
    assert result["G1"] == 1
    assert result.get("G2", 0) == 0
