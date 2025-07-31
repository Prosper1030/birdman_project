import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import networkx as nx  # noqa: E402
from src.dsm_processor import (  # noqa: E402
    buildGraph,
    assignLayer,
    computeLayersAndScc,
)  # noqa: E402


def test_build_graph_edges_and_nodes():
    dsm = pd.DataFrame([[0, 1], [0, 0]], index=["A", "B"], columns=["A", "B"])
    G = buildGraph(dsm)
    assert set(G.nodes) == {"A", "B"}
    assert ("B", "A") in G.edges


def test_assign_layer_multi_level():
    G = nx.DiGraph()
    G.add_edges_from([
        ("A", "B"),
        ("B", "C"),
    ])
    layers = assignLayer(G)
    assert layers == {"A": 0, "B": 1, "C": 2}


def test_compute_layers_and_scc_cycle():
    G = nx.DiGraph()
    G.add_edges_from([
        ("A", "B"),
        ("B", "A"),
        ("B", "C"),
    ])
    layers, scc_map = computeLayersAndScc(G)
    assert scc_map["A"] == scc_map["B"]
    assert layers["A"] == layers["B"] == 0
    assert layers["C"] == 1
