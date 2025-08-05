import pandas as pd
import networkx as nx
import pytest

from src.racp_solver import solve_racp_basic


def test_solve_racp_basic_simple():
    """基本 RACP 求解測試"""
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


def test_solve_racp_single_eligible_group():
    """單一可執行群組測試"""
    graph = nx.DiGraph()
    graph.add_edge("T1", "T2")
    wbs = pd.DataFrame({
        "Task ID": ["T1", "T2"],
        "Eligible_Groups": ["G1", "G1"],
        "Te_newbie": [3, 2],
        "ResourceDemand": [2, 1],
    })
    result = solve_racp_basic(graph, wbs, deadline=5)
    assert result["G1"] == 2  # 需要 2 個人力以滿足 T1 的需求


def test_solve_racp_parallel_tasks():
    """平行任務測試"""
    graph = nx.DiGraph()
    # T1 和 T2 平行執行，無依賴關係
    wbs = pd.DataFrame({
        "Task ID": ["T1", "T2"],
        "Eligible_Groups": ["G1", "G1"],
        "Te_newbie": [3, 3],
        "ResourceDemand": [2, 1],
    })
    result = solve_racp_basic(graph, wbs, deadline=3)
    assert result["G1"] == 3  # 平行執行需要 2+1=3 個人力


def test_solve_racp_impossible_deadline():
    """不可達成截止時間測試"""
    graph = nx.DiGraph()
    graph.add_edge("T1", "T2")
    wbs = pd.DataFrame({
        "Task ID": ["T1", "T2"],
        "Eligible_Groups": ["G1", "G1"],
        "Te_newbie": [3, 3],
        "ResourceDemand": [1, 1],
    })
    with pytest.raises(ValueError, match="無法在截止時間內完工"):
        solve_racp_basic(graph, wbs, deadline=2)  # 總工期至少需要 6 小時


def test_solve_racp_missing_groups():
    """缺少群組資訊測試"""
    graph = nx.DiGraph()
    wbs = pd.DataFrame({
        "Task ID": ["T1"],
        "Eligible_Groups": [None],  # 使用 None 而非空字串
        "Te_newbie": [2],
        "ResourceDemand": [1],
    })
    with pytest.raises((RuntimeError, ValueError)):
        solve_racp_basic(graph, wbs, deadline=5)


def test_solve_racp_multiple_groups():
    """多群組選擇測試"""
    graph = nx.DiGraph()
    wbs = pd.DataFrame({
        "Task ID": ["T1", "T2"],
        "Eligible_Groups": ["G1;G3", "G1;G2"],
        "Te_newbie": [2, 2],
        "ResourceDemand": [1, 1],
    })
    result = solve_racp_basic(graph, wbs, deadline=4)
    # 應該選擇 G1 作為共同群組
    assert result.get("G1", 0) >= 1


def test_solve_racp_high_resource_demand():
    """高資源需求測試"""
    graph = nx.DiGraph()
    wbs = pd.DataFrame({
        "Task ID": ["T1"],
        "Eligible_Groups": ["G1"],
        "Te_newbie": [2],
        "ResourceDemand": [5],  # 需要 5 個人力
    })
    result = solve_racp_basic(graph, wbs, deadline=2)
    assert result["G1"] == 5


def test_solve_racp_zero_duration():
    """零工期任務測試"""
    graph = nx.DiGraph()
    wbs = pd.DataFrame({
        "Task ID": ["T1", "T2"],
        "Eligible_Groups": ["G1", "G1"],
        "Te_newbie": [0, 2],  # T1 工期為 0
        "ResourceDemand": [1, 1],
    })
    result = solve_racp_basic(graph, wbs, deadline=2)
    assert result["G1"] == 1  # 只需要滿足 T2 的需求
