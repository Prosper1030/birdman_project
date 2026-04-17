"""主 GUI 進階分析服務。"""

from __future__ import annotations

from typing import Any

import networkx as nx
import pandas as pd

from ...app_paths import loadProjectConfig
from ...racp_solver import solve_racp_basic


def getDefaultDurationField() -> str:
    """讀取專案預設的工期欄位。"""
    config = loadProjectConfig()
    cmpParams = config.get("cmp_params", {})
    return cmpParams.get("default_duration_field", "Te_newbie")


def buildRacpContext(
    mergedGraph: nx.DiGraph | None,
    mergedWbs: pd.DataFrame | None,
    deadline: int,
) -> dict[str, Any]:
    """整理 RACP 執行所需參數並完成驗證。"""
    if mergedGraph is None or mergedWbs is None:
        raise ValueError("請先執行完整分析")
    if "Eligible_Groups" not in mergedWbs.columns:
        raise ValueError('WBS 缺少 "Eligible_Groups" 欄位')
    if "ResourceDemand" not in mergedWbs.columns:
        raise ValueError('WBS 缺少 "ResourceDemand" 欄位')

    durationField = getDefaultDurationField()
    if durationField not in mergedWbs.columns:
        raise ValueError(f"WBS 缺少工期欄位 {durationField}")

    return {
        "graph": mergedGraph,
        "wbs": mergedWbs,
        "deadline": int(deadline),
        "durationField": durationField,
    }


def runRacpAnalysis(
    mergedGraph: nx.DiGraph | None,
    mergedWbs: pd.DataFrame | None,
    deadline: int,
) -> tuple[dict[str, int], str]:
    """執行 RACP 分析並回傳結果與工期欄位。"""
    context = buildRacpContext(mergedGraph, mergedWbs, deadline)
    result = solve_racp_basic(
        context["graph"],
        context["wbs"],
        deadline=context["deadline"],
        durationField=context["durationField"],
        demandField="ResourceDemand",
    )
    return result, context["durationField"]


def buildRacpResultHtml(result: dict[str, int], deadline: int) -> str:
    """格式化 RACP 結果 HTML。"""
    totalWorkforce = sum(result.values())
    resultText = "<b>RACP 最小人力配置結果</b><br>"
    resultText += f"截止時間: {deadline} 小時<br>"
    resultText += f"總人力需求: {totalWorkforce} 人<br><br>"
    resultText += "<b>各群組人力配置:</b><br>"

    for group, count in sorted(result.items()):
        resultText += f"• {group}: {count} 人<br>"

    return resultText


def buildRcpspScheduleFrame(
    mergedWbs: pd.DataFrame,
    schedule: dict[str, float],
    durationField: str,
) -> pd.DataFrame:
    """將 RCPSP 結果整理成排程資料表。"""
    scheduleDf = mergedWbs[["Task ID", durationField]].copy()
    scheduleDf["Start"] = scheduleDf["Task ID"].map(schedule).fillna(0)
    scheduleDf["Finish"] = scheduleDf["Start"] + scheduleDf[durationField].fillna(0)
    return scheduleDf


def buildRcpspResultHtml(schedule: dict[str, float]) -> str:
    """格式化 RCPSP 結果 HTML。"""
    projectEnd = schedule.get("ProjectEnd", 0)
    resultText = f"<b>RCPSP 排程結果 (總工期: {projectEnd:.2f} 小時):</b><br><br>"
    resultText += "<table border='1' style='width:100%'>"
    resultText += "<tr><th>任務 ID</th><th>開始時間 (小時)</th></tr>"
    for task, startTime in sorted(schedule.items()):
        if task == "ProjectEnd":
            continue
        resultText += f"<tr><td>{task}</td><td>{startTime}</td></tr>"
    resultText += "</table>"
    return resultText
