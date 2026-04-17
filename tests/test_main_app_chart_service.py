import sys
from pathlib import Path

import matplotlib
from matplotlib.figure import Figure
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402
matplotlib.use("Agg")  # noqa: E402

from src.ui.main_app.chart_service import (  # noqa: E402
    createGanttFigure,
    createRcpspGanttFigure,
    initializeMonteCarloFigure,
    renderMonteCarloFigure,
)


def test_create_gantt_figure_sets_title_and_task_labels():
    cpm_df = pd.DataFrame(
        {
            "ES": [0, 2],
            "Critical": [True, False],
        },
        index=["A26-001", "A26-002"],
    )
    durations = {"A26-001": 2, "A26-002": 3}
    wbs_df = pd.DataFrame({"Task ID": ["A26-001", "A26-002"]})

    figure = createGanttFigure(cpm_df, durations, "測試甘特圖", wbs_df)

    axis = figure.axes[0]
    labels = [label.get_text() for label in axis.get_yticklabels()]
    assert axis.get_title() == "測試甘特圖"
    assert labels == ["A26-001", "A26-002"]


def test_create_rcpsp_gantt_figure_sets_title():
    schedule_df = pd.DataFrame(
        {
            "Task ID": ["T1", "T2"],
            "Start": [0, 2],
            "Te_newbie": [2, 4],
        }
    )

    figure = createRcpspGanttFigure(schedule_df, "Te_newbie", "RCPSP 圖")

    assert figure.axes[0].get_title() == "RCPSP 圖"


def test_render_monte_carlo_figure_returns_stats_and_density_axis():
    figure = Figure()

    stats = renderMonteCarloFigure(
        figure,
        [10, 12, 14, 16, 18],
        isDarkMode=False,
        chartMode="密度模式",
        selectedRole="expert",
        iterations=5,
    )

    axis = figure.axes[0]
    assert round(stats["average"], 2) == 14.0
    assert axis.get_ylabel() == "密度"
    assert "蒙地卡羅模擬結果" in axis.get_title()
    assert axis.get_legend() is not None


def test_initialize_monte_carlo_figure_sets_placeholder_title():
    figure = Figure()

    initializeMonteCarloFigure(figure, isDarkMode=True)

    axis = figure.axes[0]
    assert axis.get_title() == "蒙地卡羅模擬結果\n(請先執行模擬)"
