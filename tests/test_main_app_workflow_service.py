import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_app.workflow_service import buildWorkflowState  # noqa: E402


def test_workflow_state_before_inputs_guides_user_to_import_files():
    state = buildWorkflowState(
        hasWbs=False,
        hasDsm=False,
        hasResources=False,
        hasAnalysisResult=False,
    )

    assert state.canRunFullAnalysis is False
    assert state.canOpenDsmEditor is True
    assert "可先開 DSM 編輯器建立空白依賴圖" in state.statusHtml


def test_workflow_state_after_analysis_without_resources_guides_rcpsp_step():
    state = buildWorkflowState(
        hasWbs=True,
        hasDsm=True,
        hasResources=False,
        hasAnalysisResult=True,
    )

    assert state.canRunFullAnalysis is True
    assert state.canRunRacp is True
    assert state.canRunRcpsp is False
    assert "若要跑 RCPSP，請再匯入 Resources" in state.statusHtml


def test_workflow_state_with_all_inputs_enables_advanced_actions():
    state = buildWorkflowState(
        hasWbs=True,
        hasDsm=True,
        hasResources=True,
        hasAnalysisResult=True,
    )

    assert state.canRunFullAnalysis is True
    assert state.canOpenDsmEditor is True
    assert state.canRunRacp is True
    assert state.canConfigResources is True
    assert state.canRunRcpsp is True
