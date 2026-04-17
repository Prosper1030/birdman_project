import sys
from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_app.analysis_service import (  # noqa: E402
    buildAllCpmScenarioResults,
    buildAnalysisBundle,
    buildCpmScenarioResult,
    loadAnalysisBundle,
)


def _build_sample_wbs() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Task ID": ["A26-001", "A26-002", "A26-003"],
            "Name": ["需求", "設計", "開發"],
            "TRF": [1, 2, 3],
            "O_expert": [1, 2, 3],
            "M_expert": [2, 3, 4],
            "P_expert": [3, 4, 5],
            "Te_expert": [2, 3, 4],
            "O_newbie": [2, 3, 4],
            "M_newbie": [3, 4, 5],
            "P_newbie": [4, 5, 6],
            "Te_newbie": [3, 4, 5],
        }
    )


def _build_sample_dsm() -> pd.DataFrame:
    return pd.DataFrame(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        index=["A26-001", "A26-002", "A26-003"],
        columns=["A26-001", "A26-002", "A26-003"],
    )


def test_build_analysis_bundle_from_frames():
    bundle = buildAnalysisBundle(_build_sample_dsm(), _build_sample_wbs())

    assert list(bundle.sortedWbs["Task ID"]) == ["A26-001", "A26-002", "A26-003"]
    assert list(bundle.sortedDsm.index) == ["A26-001", "A26-002", "A26-003"]
    assert len(set(bundle.sccMap.values())) == 3
    assert bundle.layerMap["A26-001"] == 0
    assert bundle.layerMap["A26-003"] == 2
    assert bundle.mergedWbs["Task ID"].tolist() == ["A26-001", "A26-002", "A26-003"]
    assert bundle.mergedLayerMap["A26-003"] == 2


def test_load_analysis_bundle_from_paths(tmp_path):
    dsm_path = tmp_path / "dsm.csv"
    wbs_path = tmp_path / "wbs.csv"

    _build_sample_dsm().to_csv(dsm_path, encoding="utf-8-sig")
    _build_sample_wbs().to_csv(wbs_path, index=False, encoding="utf-8-sig")

    bundle = loadAnalysisBundle(str(dsm_path), str(wbs_path))

    assert bundle.sourceDsm.shape == (3, 3)
    assert bundle.sourceWbs.shape[0] == 3
    assert bundle.mergedGraph.number_of_nodes() == 3


def test_build_cpm_scenario_result_ignores_no_column():
    merged_wbs = _build_sample_wbs().copy()
    merged_wbs.insert(0, "No.", [1, 2, 3])
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("A26-001", "A26-002"),
            ("A26-002", "A26-003"),
        ]
    )

    result = buildCpmScenarioResult(merged_wbs, graph, "expert", "Te")

    assert result.projectEnd == 9
    assert result.criticalPath == ["A26-001", "A26-002", "A26-003"]
    assert result.wbsWithCpm["ES"].tolist() == [0, 2, 5]


def test_build_cpm_scenario_result_rejects_cycles():
    merged_wbs = _build_sample_wbs().iloc[:2].copy()
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("A26-001", "A26-002"),
            ("A26-002", "A26-001"),
        ]
    )

    with pytest.raises(ValueError, match="發現循環依賴"):
        buildCpmScenarioResult(merged_wbs, graph, "expert", "Te")


def test_build_all_cpm_scenario_results_returns_all_cases():
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("A26-001", "A26-002"),
            ("A26-002", "A26-003"),
        ]
    )

    results = buildAllCpmScenarioResults(_build_sample_wbs(), graph)

    assert set(results.keys()) == {"newbie", "expert"}
    assert set(results["newbie"].keys()) == {"Te", "O", "P", "M"}
    assert results["expert"]["M"].projectEnd == 9
    assert results["newbie"]["P"].projectEnd == 15
