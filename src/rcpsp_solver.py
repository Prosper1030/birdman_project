"""RCPSP 求解模組"""

from __future__ import annotations

from typing import Dict, Any

import pandas as pd
import networkx as nx
from ortools.sat.python import cp_model


def _splitResourceGroups(value: Any) -> list[str]:
    """將資源欄位拆解成群組清單。"""
    if pd.isna(value):
        return []

    text = str(value).strip()
    if not text:
        return []

    return [group.strip() for group in text.split(";") if group.strip()]


def _inferAllGroups(
    wbs: pd.DataFrame,
    resourceField: str,
    resourceCap: Dict[str, int],
) -> list[str]:
    """推導全部可用的資源群組名稱。"""
    if resourceCap:
        return [str(group).strip() for group in resourceCap.keys()]

    groups: set[str] = set()
    for rawValue in wbs.get(resourceField, []):
        for group in _splitResourceGroups(rawValue):
            if group.upper() == "ALL":
                continue
            groups.add(group)
    return sorted(groups)


def _resolveEligibleGroups(
    row: pd.Series,
    resourceField: str,
    allGroups: list[str],
) -> list[str]:
    """解析任務可使用的資源群組。"""
    groups = _splitResourceGroups(row.get(resourceField, ""))
    if len(groups) == 1 and groups[0].upper() == "ALL":
        return list(allGroups)
    return groups


def solveRcpsp(
    graph: nx.DiGraph,
    wbs: pd.DataFrame,
    durationField: str = "Te_newbie",
    resourceField: str = "Property",
    demandField: str = "ResourceDemand",
    resourceCap: Dict[str, int] | None = None,
    timeLimit: int = 10,
) -> Dict[str, Any]:
    """使用 OR-Tools 求解 RCPSP。

    Args:
        graph: 任務依賴圖。
        wbs: 任務資料表，需包含工期與資源欄位。
        durationField: 工期欄位名稱。
        resourceField: 資源分類欄位名稱。
        demandField: 資源需求量欄位名稱。
        resourceCap: 各資源可同時執行的數量，預設為 1。
        timeLimit: 求解時間上限 (秒)。

    Returns:
        Dict[str, Any]: 各任務開始時間與 ProjectEnd。
    """
    if resourceCap is None:
        resourceCap = {}

    model = cp_model.CpModel()
    horizon = int(wbs[durationField].fillna(0).astype(float).sum())
    allGroups = _inferAllGroups(wbs, resourceField, resourceCap)

    startVars: Dict[str, cp_model.IntVar] = {}
    endVars: Dict[str, cp_model.IntVar] = {}
    resourceMap: Dict[str, tuple[list[cp_model.IntervalVar], list[int]]] = {}

    for _, row in wbs.iterrows():
        taskId = row["Task ID"]
        duration = int(float(row.get(durationField, 0)))
        start = model.NewIntVar(0, horizon, f"start_{taskId}")
        end = model.NewIntVar(0, horizon, f"end_{taskId}")
        model.Add(end == start + duration)
        startVars[taskId] = start
        endVars[taskId] = end
        demand = int(float(row.get(demandField, 1)))

        eligibleGroups = _resolveEligibleGroups(row, resourceField, allGroups)
        if not eligibleGroups and resourceField != "Property":
            eligibleGroups = _resolveEligibleGroups(row, "Property", allGroups)
        if not eligibleGroups:
            raise ValueError(f"任務 {taskId} 缺少可用資源群組")

        assignmentVars: list[cp_model.BoolVar] = []
        for group in eligibleGroups:
            capacity = int(resourceCap.get(group, 1 if not resourceCap else 0))
            if capacity <= 0:
                continue
            useGroup = model.NewBoolVar(f"use_{taskId}_{group}")
            interval = model.NewOptionalIntervalVar(
                start,
                duration,
                end,
                useGroup,
                f"interval_{taskId}_{group}",
            )
            intervals, demands = resourceMap.setdefault(group, ([], []))
            intervals.append(interval)
            demands.append(demand)
            assignmentVars.append(useGroup)

        if not assignmentVars:
            raise ValueError(f"任務 {taskId} 沒有可用的資源容量設定")
        model.Add(sum(assignmentVars) == 1)

    for u, v in graph.edges():
        if u in endVars and v in startVars:
            model.Add(startVars[v] >= endVars[u])

    for res, (intervals, demands) in resourceMap.items():
        cap = int(resourceCap.get(res, 1))
        model.AddCumulative(intervals, demands, cap)

    makespan = model.NewIntVar(0, horizon, "makespan")
    for end in endVars.values():
        model.Add(makespan >= end)
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeLimit

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("RCPSP 求解失敗")

    schedule = {tid: solver.Value(start) for tid, start in startVars.items()}
    schedule["ProjectEnd"] = solver.Value(makespan)
    return schedule
