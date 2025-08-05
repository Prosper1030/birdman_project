import sys
from pathlib import Path
import networkx as nx
import matplotlib
from matplotlib.figure import Figure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402
matplotlib.use('Agg')  # noqa: E402

from src.visualizer import layered_layout, create_dependency_graph_figure  # noqa: E402


def test_layered_layout_positions():
    """測試分層佈局座標計算是否正確"""
    G = nx.DiGraph()
    G.add_nodes_from(['A', 'B', 'C'])
    layer_map = {'A': 0, 'B': 1, 'C': 1}
    pos = layered_layout(G, layer_map)
    assert pos['A'][0] == 0
    assert pos['A'][1] == 0
    layer1_y = {pos['B'][1], pos['C'][1]}
    assert pos['B'][0] == 1 and pos['C'][0] == 1
    assert layer1_y == {0.75, -0.75}


def test_create_dependency_graph_figure_draws_all_nodes():
    """測試圖形建立後是否包含所有節點"""
    G = nx.DiGraph()
    G.add_edges_from([('A', 'B'), ('A', 'C')])
    scc_map = {'A': 0, 'B': 1, 'C': 1}
    layer_map = {'A': 0, 'B': 1, 'C': 1}
    fig = create_dependency_graph_figure(G, scc_map, layer_map, {})
    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    node_collection = ax.collections[0]
    assert len(node_collection.get_offsets()) == 3
