# -*- coding: utf-8 -*-
"""DSM 處理模組"""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class DSMData:
    taskIds: List[str]
    matrix: pd.DataFrame


def readDsm(path: str) -> DSMData:
    """讀取 DSM CSV 並進行基本驗證"""
    df = pd.read_csv(path, index_col=0)
    df.index = df.index.astype(str)
    df.columns = df.columns.astype(str)

    if df.shape[0] != df.shape[1]:
        raise ValueError("DSM 不是方陣")
    if list(df.index) != list(df.columns):
        raise ValueError("DSM 行列 Task_ID 不一致")

    return DSMData(taskIds=list(df.index), matrix=df)


def buildGraph(dsm: DSMData) -> Dict[str, List[str]]:
    """將 DSM 轉換為依賴圖"""
    graph: Dict[str, List[str]] = {task: [] for task in dsm.taskIds}
    for rowTask in dsm.taskIds:
        deps = dsm.matrix.loc[rowTask]
        graph[rowTask] = [col for col, v in deps.items() if v == 1]
    return graph


def topologicalSort(graph: Dict[str, List[str]]) -> Tuple[List[str], bool]:
    """拓撲排序，回傳排序結果與是否有循環依賴"""
    from collections import defaultdict, deque

    indegree = defaultdict(int)
    for node, deps in graph.items():
        indegree.setdefault(node, 0)
        for dep in deps:
            indegree[dep] += 1

    q = deque([n for n in graph if indegree[n] == 0])
    result: List[str] = []
    while q:
        n = q.popleft()
        result.append(n)
        for m in graph[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                q.append(m)

    hasCycle = len(result) != len(graph)
    return result, hasCycle


def tarjanScc(graph: Dict[str, List[str]]) -> Tuple[List[List[str]], Dict[str, int]]:
    """使用 Tarjan 演算法找出強連通分量"""
    index = 0
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    stack: List[str] = []
    onStack: Dict[str, bool] = {}
    sccs: List[List[str]] = []
    sccIdMap: Dict[str, int] = {}

    def strongconnect(node: str):
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        onStack[node] = True

        for neighbor in graph[node]:
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif onStack.get(neighbor, False):
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] == indices[node]:
            scc = []
            while True:
                w = stack.pop()
                onStack[w] = False
                scc.append(w)
                if w == node:
                    break
            sccs.append(scc)
            for n in scc:
                sccIdMap[n] = len(sccs)

    for v in graph:
        if v not in indices:
            strongconnect(v)

    return sccs, sccIdMap


def computeLayers(order: List[str], graph: Dict[str, List[str]]) -> Dict[str, int]:
    """依照拓撲順序計算每個節點的層次"""
    layer: Dict[str, int] = {task: 0 for task in order}
    for task in order:
        for dep in graph[task]:
            layer[dep] = max(layer.get(dep, 0), layer[task] + 1)
    return layer
