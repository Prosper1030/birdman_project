"""主 GUI 操作流程狀態服務。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WorkflowState:
    """描述目前畫面可執行的流程狀態。"""

    statusHtml: str
    canRunFullAnalysis: bool
    canOpenDsmEditor: bool
    canRunRacp: bool
    canConfigResources: bool
    canRunRcpsp: bool


def _buildStatusLine(label: str, isReady: bool, detail: str) -> str:
    """建立單行狀態描述。"""
    color = "#1b5e20" if isReady else "#b71c1c"
    stateText = "已就緒" if isReady else "未就緒"
    return f"<span style='color:{color};'><b>{label}</b>：{stateText}</span> {detail}"


def buildWorkflowState(
    *,
    hasWbs: bool,
    hasDsm: bool,
    hasResources: bool,
    hasAnalysisResult: bool,
) -> WorkflowState:
    """依目前輸入與分析狀態建立畫面指引。"""
    canRunFullAnalysis = hasWbs and hasDsm
    canOpenDsmEditor = True
    canRunRacp = hasAnalysisResult
    canConfigResources = hasAnalysisResult and hasResources
    canRunRcpsp = hasAnalysisResult and hasResources

    lines = [
        "<b>目前操作狀態</b>",
        _buildStatusLine(
            "WBS",
            hasWbs,
            "完整分析需要 WBS；若只想先建立依賴圖，仍可直接開 DSM 編輯器。",
        ),
        _buildStatusLine("DSM", hasDsm, "完整分析需要 DSM。"),
        _buildStatusLine("Resources", hasResources, "RCPSP 需要 Resources；RACP 不需要。"),
        _buildStatusLine("完整分析結果", hasAnalysisResult, "完成後才會啟用 RACP / RCPSP / 蒙地卡羅等進階結果。"),
    ]

    if canRunFullAnalysis and not hasAnalysisResult:
        nextStep = "下一步：可以直接按「執行完整分析」。"
    elif hasAnalysisResult and hasResources:
        nextStep = "下一步：可執行 RACP、RCPSP、蒙地卡羅與各類匯出。"
    elif hasAnalysisResult:
        nextStep = "下一步：可先做 RACP 與 CPM；若要跑 RCPSP，請再匯入 Resources。"
    elif hasWbs:
        nextStep = "下一步：可先開 DSM 編輯器，或繼續匯入 DSM 後執行完整分析。"
    else:
        nextStep = "下一步：可先開 DSM 編輯器建立空白依賴圖，或匯入 WBS 與 DSM。"

    lines.append(f"<br><b>{nextStep}</b>")

    return WorkflowState(
        statusHtml="<br>".join(lines),
        canRunFullAnalysis=canRunFullAnalysis,
        canOpenDsmEditor=canOpenDsmEditor,
        canRunRacp=canRunRacp,
        canConfigResources=canConfigResources,
        canRunRcpsp=canRunRcpsp,
    )
