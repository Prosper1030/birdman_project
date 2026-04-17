"""主 GUI 分析服務。

將原本散落在 GUI 事件處理中的 DSM / WBS / CPM 分析流程集中，
讓介面層只負責資料綁定與訊息顯示。
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import pandas as pd

from ...cpm_processor import (
    calculateSlack,
    cpmBackwardPass,
    cpmForwardPass,
    extractDurationFromWbs,
    findCriticalPath,
)
from ...dsm_processor import buildMergedDsm, buildTaskMapping, processDsm, readDsm
from ...wbs_processor import mergeByScc, readWbs, validateIds


@dataclass(slots=True)
class AnalysisBundle:
    """封裝一次基礎分析所需的全部結果。"""

    sourceDsm: pd.DataFrame
    sourceWbs: pd.DataFrame
    sortedDsm: pd.DataFrame
    sortedWbs: pd.DataFrame
    mergedWbs: pd.DataFrame
    graph: nx.DiGraph
    mergedDsm: pd.DataFrame
    mergedGraph: nx.DiGraph
    sccMap: dict[str, int]
    layerMap: dict[str, int]
    mergedSccMap: dict[str, int]
    mergedLayerMap: dict[str, int]


@dataclass(slots=True)
class CpmScenarioResult:
    """封裝單一角色與時間模式的 CPM 結果。"""

    roleKey: str
    timeKey: str
    cpmDf: pd.DataFrame
    durations: dict[str, float]
    wbsWithCpm: pd.DataFrame
    projectEnd: float
    criticalPath: list[str]


def calculateMergedLayerMap(graph: nx.DiGraph) -> dict[str, int]:
    """計算合併後圖形的層次對應表。"""
    try:
        sourceNodes = [node for node, degree in graph.in_degree() if degree == 0]
        mergedLayerMap: dict[str, int] = {}
        for node in graph.nodes():
            maxDistance = 0
            for sourceNode in sourceNodes:
                try:
                    paths = nx.all_simple_paths(graph, sourceNode, node)
                    distance = max((len(path) - 1 for path in paths), default=-1)
                    if distance > maxDistance:
                        maxDistance = distance
                except nx.NetworkXNoPath:
                    continue
            mergedLayerMap[node] = maxDistance
        return mergedLayerMap
    except (ValueError, nx.NetworkXError):
        return {node: index for index, node in enumerate(graph.nodes())}


def buildAnalysisBundle(
    dsmDf: pd.DataFrame,
    wbsDf: pd.DataFrame,
    kParams: dict | None = None,
) -> AnalysisBundle:
    """依據 DSM 與 WBS 資料建立基礎分析結果。"""
    validateIds(wbsDf, dsmDf)

    sortedDsm, sortedWbs, graph = processDsm(dsmDf, wbsDf)
    mergedWbs = mergeByScc(sortedWbs, kParams)

    taskMapping = buildTaskMapping(sortedWbs, mergedWbs)
    mergedDsm = buildMergedDsm(graph, taskMapping)
    mergedSortedDsm, mergedSortedWbs, mergedGraph = processDsm(mergedDsm, mergedWbs)

    return AnalysisBundle(
        sourceDsm=dsmDf.copy(),
        sourceWbs=wbsDf.copy(),
        sortedDsm=sortedDsm,
        sortedWbs=sortedWbs,
        mergedWbs=mergedSortedWbs,
        graph=graph,
        mergedDsm=mergedSortedDsm,
        mergedGraph=mergedGraph,
        sccMap=dict(zip(sortedWbs["Task ID"], sortedWbs["SCC_ID"])),
        layerMap=dict(zip(sortedWbs["Task ID"], sortedWbs["Layer"])),
        mergedSccMap={
            node: index for index, node in enumerate(mergedGraph.nodes())
        },
        mergedLayerMap=calculateMergedLayerMap(mergedGraph),
    )


def loadAnalysisBundle(
    dsmPath: str,
    wbsPath: str,
    kParams: dict | None = None,
) -> AnalysisBundle:
    """從檔案載入資料並建立基礎分析結果。"""
    dsmDf = readDsm(dsmPath)
    wbsDf = readWbs(wbsPath)
    return buildAnalysisBundle(dsmDf, wbsDf, kParams)


def _getDurationWbs(mergedWbs: pd.DataFrame) -> pd.DataFrame:
    """取得可供工期計算的 WBS。

    GUI 顯示時可能會額外加入 ``No.`` 欄位，CPM 計算前需移除。
    """
    if "No." not in mergedWbs.columns:
        return mergedWbs
    return mergedWbs.drop(columns=["No."])


def _raiseIfGraphHasCycles(graph: nx.DiGraph) -> None:
    """若圖中存在循環，拋出繁中錯誤訊息。"""
    cycles = list(nx.simple_cycles(graph))
    if not cycles:
        return

    cycleText = " -> ".join(cycles[0] + [cycles[0][0]])
    raise ValueError(
        f"發現循環依賴：{cycleText}\n請先解決循環依賴問題再進行 CPM 分析"
    )


def buildCpmScenarioResult(
    mergedWbs: pd.DataFrame,
    mergedGraph: nx.DiGraph,
    roleKey: str,
    timeKey: str,
) -> CpmScenarioResult:
    """計算單一情境的 CPM 結果。"""
    _raiseIfGraphHasCycles(mergedGraph)

    durationField = f"{timeKey}_{roleKey}"
    durationWbs = _getDurationWbs(mergedWbs)
    durations = extractDurationFromWbs(durationWbs, durationField)
    forwardData = cpmForwardPass(mergedGraph, durations)
    projectEnd = max(ef for _, ef in forwardData.values())
    backwardData = cpmBackwardPass(mergedGraph, durations, projectEnd)
    cpmDf = calculateSlack(forwardData, backwardData, mergedGraph)

    wbsWithCpm = mergedWbs.copy()
    for column in ["ES", "EF", "LS", "LF", "TF", "FF", "Critical"]:
        wbsWithCpm[column] = (
            wbsWithCpm["Task ID"].map(cpmDf[column].to_dict()).fillna(0)
        )

    return CpmScenarioResult(
        roleKey=roleKey,
        timeKey=timeKey,
        cpmDf=cpmDf,
        durations=durations,
        wbsWithCpm=wbsWithCpm,
        projectEnd=projectEnd,
        criticalPath=findCriticalPath(cpmDf),
    )


def buildAllCpmScenarioResults(
    mergedWbs: pd.DataFrame,
    mergedGraph: nx.DiGraph,
) -> dict[str, dict[str, CpmScenarioResult]]:
    """建立所有角色與時間模式的 CPM 結果。"""
    results = {"newbie": {}, "expert": {}}
    for roleKey in ["newbie", "expert"]:
        for timeKey in ["Te", "O", "P", "M"]:
            results[roleKey][timeKey] = buildCpmScenarioResult(
                mergedWbs,
                mergedGraph,
                roleKey,
                timeKey,
            )
    return results


__all__ = [
    "AnalysisBundle",
    "CpmScenarioResult",
    "buildAllCpmScenarioResults",
    "buildAnalysisBundle",
    "buildCpmScenarioResult",
    "calculateMergedLayerMap",
    "loadAnalysisBundle",
]
