import sys
from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_app.advanced_analysis_service import (  # noqa: E402
    buildRacpResultHtml,
    buildRcpspResultHtml,
    buildRcpspScheduleFrame,
    runRacpAnalysis,
)


def _build_sample_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_edge("T1", "T2")
    return graph


def _build_sample_wbs() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Task ID": ["T1", "T2"],
            "Te_newbie": [2, 3],
            "Eligible_Groups": ["R1", "R1"],
            "ResourceDemand": [1, 1],
        }
    )


def test_run_racp_analysis_returns_capacity_result():
    result, durationField = runRacpAnalysis(_build_sample_graph(), _build_sample_wbs(), 10)

    assert durationField == "Te_newbie"
    assert result == {"R1": 1}


def test_run_racp_analysis_requires_complete_analysis():
    with pytest.raises(ValueError, match="請先執行完整分析"):
        runRacpAnalysis(None, _build_sample_wbs(), 10)


def test_build_racp_result_html_contains_summary():
    resultHtml = buildRacpResultHtml({"R2": 2, "R1": 1}, 100)

    assert "RACP 最小人力配置結果" in resultHtml
    assert "截止時間: 100 小時" in resultHtml
    assert "總人力需求: 3 人" in resultHtml
    assert resultHtml.index("R1") < resultHtml.index("R2")


def test_build_rcpsp_schedule_frame_adds_finish_time():
    scheduleDf = buildRcpspScheduleFrame(
        pd.DataFrame({"Task ID": ["T1", "T2"], "Te_newbie": [2, 4]}),
        {"T1": 0, "T2": 3, "ProjectEnd": 7},
        "Te_newbie",
    )

    assert scheduleDf["Start"].tolist() == [0, 3]
    assert scheduleDf["Finish"].tolist() == [2, 7]


def test_build_rcpsp_result_html_ignores_project_end_row():
    resultHtml = buildRcpspResultHtml({"T2": 3, "T1": 0, "ProjectEnd": 7})

    assert "RCPSP 排程結果 (總工期: 7.00 小時)" in resultHtml
    assert "ProjectEnd" not in resultHtml
    assert "T1" in resultHtml
    assert "T2" in resultHtml
