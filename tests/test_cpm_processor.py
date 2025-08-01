import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx
import pandas as pd
from src.cpm_processor import (
    cpmForwardPass,
    cpmBackwardPass,
    calculateSlack,
    findCriticalPath,
)


def build_sample_graph():
    tasks = {
        'A': {'duration': 3, 'predecessors': []},
        'B': {'duration': 4, 'predecessors': ['A']},
        'C': {'duration': 2, 'predecessors': ['A']},
        'D': {'duration': 3, 'predecessors': ['B', 'C']}
    }
    G = nx.DiGraph()
    for tid, data in tasks.items():
        G.add_node(tid)
        for pre in data['predecessors']:
            G.add_edge(pre, tid)
    durations = {tid: data['duration'] for tid, data in tasks.items()}
    return G, durations


def test_cpm_calculation():
    G, durations = build_sample_graph()
    forward = cpmForwardPass(G, durations)
    project_end = max(v[1] for v in forward.values())
    backward = cpmBackwardPass(G, durations, project_end)
    slack_df = calculateSlack(forward, backward, G)
    critical = findCriticalPath(slack_df)

    assert forward['A'] == (0, 3)
    assert forward['B'] == (3, 7)
    assert forward['C'] == (3, 5)
    assert backward['D'] == (7, 10)
    assert slack_df.at['C', 'TF'] == 2
    assert critical == ['A', 'B', 'D']

