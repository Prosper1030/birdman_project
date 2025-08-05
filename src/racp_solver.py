"""RACP 求解模組"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
import networkx as nx
from ortools.sat.python import cp_model


def _parseEligibleGroups(value: str, allGroups: List[str]) -> List[str]:
    """解析 Eligible_Groups 欄位為群組列表。"""
    if not value:
        return []
    value = value.strip()
    if value.upper() == "ALL":
        return allGroups
    return [g.strip() for g in value.split(";") if g.strip()]


def _solveRcpspWithAlt(
    graph: nx.DiGraph,
    wbs: pd.DataFrame,
    resourceCap: Dict[str, int],
    durationField: str,
    demandField: str,
    timeLimit: int,
    allGroups: List[str],
) -> int:
    """在給定資源上限下求解最短完工時間。"""
    model = cp_model.CpModel()
    horizon = int(wbs[durationField].fillna(0).astype(float).sum())
    startVars: Dict[str, cp_model.IntVar] = {}
    endVars: Dict[str, cp_model.IntVar] = {}
    resourceMap: Dict[str, tuple[list[cp_model.IntervalVar], list[int]]] = {
        g: ([], []) for g in resourceCap
    }

    for _, row in wbs.iterrows():
        tid = row["Task ID"]
        duration = int(float(row.get(durationField, 0)))
        start = model.NewIntVar(0, horizon, f"start_{tid}")
        end = model.NewIntVar(0, horizon, f"end_{tid}")
        model.Add(end == start + duration)
        startVars[tid] = start
        endVars[tid] = end

        elig = _parseEligibleGroups(str(row.get("Eligible_Groups", "")), allGroups)
        demand = int(float(row.get(demandField, 1)))
        assigns = []
        for g in elig:
            if resourceCap.get(g, 0) <= 0:
                continue
            if g not in resourceMap:
                resourceMap[g] = ([], [])
            boolVar = model.NewBoolVar(f"use_{tid}_{g}")
            interval = model.NewOptionalIntervalVar(
                start, duration, end, boolVar, f"int_{tid}_{g}"
            )
            resourceMap[g][0].append(interval)
            resourceMap[g][1].append(demand)
            assigns.append(boolVar)
        if assigns:
            model.Add(sum(assigns) == 1)
        else:
            raise ValueError("缺少 Eligible_Groups")

    for u, v in graph.edges():
        if u in endVars and v in startVars:
            model.Add(startVars[v] >= endVars[u])

    for g, (intervals, demands) in resourceMap.items():
        cap = int(resourceCap.get(g, 0))
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
    return solver.Value(makespan)


def solve_racp_basic(
    graph: nx.DiGraph,
    wbs: pd.DataFrame,
    deadline: int,
    durationField: str = "Te_newbie",
    demandField: str = "ResourceDemand",
    timeLimit: int = 5,
) -> Dict[str, int]:
    """使用改良最小界限演算法求解小型專案 RACP。"""
    groups = set()
    for val in wbs.get("Eligible_Groups", []):
        if pd.isna(val):
            continue
        val = str(val)
        if val.upper() == "ALL":
            continue
        groups.update(g.strip() for g in val.split(";") if g.strip())
    allGroups = sorted(groups)

    lower: Dict[str, int] = {g: 0 for g in allGroups}
    for _, row in wbs.iterrows():
        raw = row.get("Eligible_Groups", "")
        if pd.isna(raw) or not str(raw).strip():
            raise ValueError("缺少 Eligible_Groups")
        elig = _parseEligibleGroups(str(raw), allGroups)
        demand = int(float(row.get(demandField, 1)))
        if len(elig) == 1:
            g = elig[0]
            lower[g] = max(lower.get(g, 0), demand)

    capacity = lower.copy()
    for _, row in wbs.iterrows():
        elig = _parseEligibleGroups(str(row.get("Eligible_Groups", "")), allGroups)
        demand = int(float(row.get(demandField, 1)))
        if all(capacity.get(g, 0) < demand for g in elig):
            capacity[elig[0]] = max(capacity.get(elig[0], 0), demand)

    try:
        makespan = _solveRcpspWithAlt(
            graph, wbs, capacity, durationField, demandField, timeLimit, allGroups
        )
    except (RuntimeError, ValueError):
        makespan = deadline + 1

    maxIter = 20
    iterCount = 0
    while makespan > deadline and iterCount < maxIter:
        for g in capacity:
            capacity[g] += 1
        makespan = _solveRcpspWithAlt(
            graph, wbs, capacity, durationField, demandField, timeLimit, allGroups
        )
        iterCount += 1
    if makespan > deadline:
        raise ValueError("無法在截止時間內完工")

    for g in capacity:
        low = lower.get(g, 0)
        high = capacity[g]
        while low < high:
            mid = (low + high) // 2
            capacity[g] = mid
            try:
                m = _solveRcpspWithAlt(
                    graph, wbs, capacity, durationField, demandField, timeLimit, allGroups
                )
            except (RuntimeError, ValueError):
                m = deadline + 1
            if m <= deadline:
                high = mid
            else:
                low = mid + 1
            capacity[g] = high
    return capacity


# camelCase 別名以符合一般命名習慣
solveRacpBasic = solve_racp_basic
