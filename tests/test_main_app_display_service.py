import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_app.display_service import (  # noqa: E402
    TIME_MODE_OPTIONS,
    buildRoleStatusMessage,
    buildScenarioDisplayState,
    getRoleLabel,
    resolveTimeKey,
)


def test_time_mode_options_keep_expected_order():
    assert TIME_MODE_OPTIONS == [
        "期望時間 (Te)",
        "樂觀時間 (O)",
        "悲觀時間 (P)",
        "最可能時間 (M)",
    ]


def test_resolve_time_key_defaults_to_te():
    assert resolveTimeKey("樂觀時間 (O)") == "O"
    assert resolveTimeKey("不存在的選項") == "Te"


def test_role_label_and_status_message():
    assert getRoleLabel("newbie") == "新手"
    assert getRoleLabel("expert") == "專家"
    assert buildRoleStatusMessage("expert") == "已切換至 專家 模式"


def test_build_scenario_display_state_formats_title_and_hours():
    displayDf = pd.DataFrame({"Task ID": ["T1"], "ES": [0]})

    state = buildScenarioDisplayState(
        roleKey="newbie",
        timeKey="Te",
        projectEnd=12.345,
        displayDf=displayDf,
    )

    assert state.roleLabel == "新手"
    assert state.modeLabel == "期望時間"
    assert state.totalHoursText == "總工時：12.3 小時"
    assert state.figureTitle == "新手 - 期望時間 (Te_newbie)\n總工時: 12.35 小時"
    assert state.displayDf.equals(displayDf)
