import pandas as pd
import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


def cpmForwardPass(
    G: nx.DiGraph,
    durations: Dict[str, float],
) -> Dict[str, Tuple[float, float]]:
    """CPM 正向計算，回傳最早開始與最早完成時間"""
    es: Dict[str, float] = {}
    ef: Dict[str, float] = {}
    for node in nx.topological_sort(G):
        preds = list(G.predecessors(node))
        if preds:
            es[node] = max(ef[p] for p in preds)
        else:
            es[node] = 0.0
        ef[node] = es[node] + durations.get(node, 0)
    return {n: (es[n], ef[n]) for n in G.nodes}


def cpmBackwardPass(
    G: nx.DiGraph,
    durations: Dict[str, float],
    projectEnd: float,
) -> Dict[str, Tuple[float, float]]:
    """CPM 反向計算，回傳最晚開始與最晚完成時間"""
    ls: Dict[str, float] = {}
    lf: Dict[str, float] = {}
    order = list(nx.topological_sort(G))
    for node in reversed(order):
        succs = list(G.successors(node))
        if succs:
            lf[node] = min(ls[s] for s in succs)
        else:
            lf[node] = projectEnd
        ls[node] = lf[node] - durations.get(node, 0)
    return {n: (ls[n], lf[n]) for n in G.nodes}


def calculateSlack(
    forwardData: Dict[str, Tuple[float, float]],
    backwardData: Dict[str, Tuple[float, float]],
    G: nx.DiGraph,
) -> pd.DataFrame:
    """計算總鬆弛與自由鬆弛時間"""
    records = []
    for node in G.nodes:
        es, ef = forwardData[node]
        ls, lf = backwardData[node]
        tf = ls - es
        if list(G.successors(node)):
            ff = min(forwardData[s][0] for s in G.successors(node)) - ef
        else:
            ff = tf
        records.append({
            "Task ID": node,
            "ES": es,
            "EF": ef,
            "LS": ls,
            "LF": lf,
            "TF": tf,
            "FF": ff,
            # 以容許誤差判定是否為關鍵任務，避免浮點數誤差
            "Critical": abs(tf) < 1e-9,
        })
    df = pd.DataFrame(records).set_index("Task ID")
    return df


def findCriticalPath(slackData: pd.DataFrame) -> List[str]:
    """根據總鬆弛時間為 0 識別關鍵路徑"""
    critical = slackData[slackData["TF"] == 0]
    critical = critical.sort_values("ES")
    return critical.index.tolist()


# 時間相關輔助函式

def convertHoursToDays(
    hours: float,
    workHoursPerDay: float = 8,
) -> float:
    """將工時轉換為工作天數"""
    return hours / workHoursPerDay


def addWorkingDays(startDate: str, days: float) -> str:
    """計算加入工作天數後的日期（排除週末）"""
    date = datetime.strptime(startDate, "%Y-%m-%d")
    full_days = int(days)
    remaining = days - full_days
    while full_days > 0:
        date += timedelta(days=1)
        if date.weekday() < 5:
            full_days -= 1
    if remaining > 0:
        date += timedelta(days=remaining)
    return date.strftime("%Y-%m-%d")


def extractDurationFromWbs(
    wbs: pd.DataFrame,
    durationField: str = "Te_expert",
) -> Dict[str, float]:
    """從 WBS 資料框提取工期資訊"""
    if durationField not in wbs.columns:
        raise KeyError(f"WBS 缺少 {durationField} 欄位")
    return dict(zip(wbs["Task ID"], wbs[durationField].astype(float)))
