"""RCPSP 求解模組"""

from typing import Dict, Any

import pandas as pd
import networkx as nx
from ortools.sat.python import cp_model


def solveRcpsp(
    graph: nx.DiGraph,
    wbs: pd.DataFrame,
    durationField: str = "Te_newbie",
    resourceField: str = "Category",
    resourceCap: Dict[str, int] | None = None,
    timeLimit: int = 10,
) -> Dict[str, Any]:
    """使用 OR-Tools 求解 RCPSP

    參數:
        graph: 任務依賴圖
        wbs:   任務資料表，需包含工期與資源欄位
        durationField: 工期欄位名稱
        resourceField: 資源分類欄位名稱
        resourceCap:   各資源可同時執行的數量，預設為 1
        timeLimit:     求解時間上限 (秒)

    回傳字典包含各任務開始時間與 ProjectEnd
    """
    if resourceCap is None:
        resourceCap = {}

    model = cp_model.CpModel()
    horizon = int(wbs[durationField].fillna(0).astype(float).sum())

    startVars: Dict[str, cp_model.IntVar] = {}
    endVars: Dict[str, cp_model.IntVar] = {}
    intervalMap: Dict[str, cp_model.IntervalVar] = {}
    resourceMap: Dict[str, list[cp_model.IntervalVar]] = {}

    for _, row in wbs.iterrows():
        taskId = row["Task ID"]
        duration = int(float(row.get(durationField, 0)))
        start = model.NewIntVar(0, horizon, f"start_{taskId}")
        end = model.NewIntVar(0, horizon, f"end_{taskId}")
        model.Add(end == start + duration)
        interval = model.NewIntervalVar(
            start, duration, end, f"interval_{taskId}"
        )

        startVars[taskId] = start
        endVars[taskId] = end
        intervalMap[taskId] = interval

        res = str(row.get(resourceField, "default"))
        resourceMap.setdefault(res, []).append(interval)

    for u, v in graph.edges():
        if u in endVars and v in startVars:
            model.Add(startVars[v] >= endVars[u])

    for res, intervals in resourceMap.items():
        cap = int(resourceCap.get(res, 1))
        demands = [1] * len(intervals)
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
