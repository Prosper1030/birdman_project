from pathlib import Path
import sys

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from src.ui.main_app.graph_service import renderDependencyGraph  # noqa: E402


def test_render_dependency_graph_replaces_existing_widgets(qapp):
    """重繪依賴圖時應先清掉舊 widget，再放入新 canvas。"""
    container = QWidget()
    layout = QVBoxLayout(container)
    old_label = QLabel("old")
    layout.addWidget(old_label)

    graph = nx.DiGraph()
    graph.add_edge("A", "B")

    figure, canvas = renderDependencyGraph(
        graph=graph,
        sccMap={"A": 0, "B": 1},
        layerMap={"A": 0, "B": 1},
        vizParams={},
        layout=layout,
        container=container,
    )

    assert figure is not None
    assert canvas is not None
    assert layout.count() == 1
    assert layout.itemAt(0).widget() is canvas


def test_render_dependency_graph_supports_critical_path_edges(qapp):
    """依賴圖服務應支援傳入關鍵路徑邊線。"""
    container = QWidget()
    layout = QVBoxLayout(container)

    graph = nx.DiGraph()
    graph.add_edge("A", "B")
    graph.add_edge("B", "C")

    figure, canvas = renderDependencyGraph(
        graph=graph,
        sccMap={"A": 0, "B": 1, "C": 2},
        layerMap={"A": 0, "B": 1, "C": 2},
        vizParams={},
        layout=layout,
        container=container,
        criticalPathEdges={("A", "B"), ("B", "C")},
    )

    assert figure is not None
    assert canvas is not None
    assert layout.count() == 1
