import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_app.summary_service import (  # noqa: E402
    buildAnalysisSummaryHtml,
    countDependencies,
)


def test_count_dependencies_counts_non_zero_cells():
    dsm = pd.DataFrame([[0, 1], [1, 0]])

    assert countDependencies(dsm) == 2


def test_build_analysis_summary_html_includes_counts_and_current_scenario():
    summary = buildAnalysisSummaryHtml(
        sortedWbs=pd.DataFrame({"Task ID": ["T1", "T2", "T3"]}),
        mergedWbs=pd.DataFrame({"Task ID": ["M1", "M2"]}),
        sortedDsm=pd.DataFrame([[0, 1], [0, 0]]),
        sccMap={"T1": 1, "T2": 2, "T3": 2},
        hasResources=True,
        roleKey="expert",
        timeKey="Te",
        projectEnd=12.5,
    )

    assert "原始任務數：3" in summary
    assert "合併後任務數：2" in summary
    assert "依賴數：1" in summary
    assert "SCC 數量：2" in summary
    assert "Resources：已匯入" in summary
    assert "專家 / Te / 總工時 12.50 小時" in summary
