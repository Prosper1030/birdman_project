import pandas as pd
import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import numpy as np


def cpmForwardPass(
    G: nx.DiGraph,
    durations: Dict[str, float],
) -> Dict[str, Tuple[float, float]]:
    """執行 CPM 正向計算，回傳最早開始與最早完成時間。

    Args:
        G: 任務依賴圖。
        durations: 各任務工期的字典。

    Returns:
        Dict[str, Tuple[float, float]]: 每個任務的最早開始與最早完成時間。
    """
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
    """執行 CPM 反向計算，回傳最晚開始與最晚完成時間。

    Args:
        G: 任務依賴圖。
        durations: 各任務工期的字典。
        projectEnd: 專案預期完工時間。

    Returns:
        Dict[str, Tuple[float, float]]: 每個任務的最晚開始與最晚完成時間。
    """
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
    """計算總鬆弛與自由鬆弛時間。

    Args:
        forwardData: 正向計算結果。
        backwardData: 反向計算結果。
        G: 任務依賴圖。

    Returns:
        pd.DataFrame: 各任務的時間參數與鬆弛時間。
    """
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
    """根據總鬆弛時間為 0 識別關鍵路徑。

    Args:
        slackData: 各任務鬆弛時間資料。

    Returns:
        List[str]: 關鍵路徑上的 Task ID。
    """
    critical = slackData[slackData["TF"] == 0]
    critical = critical.sort_values("ES")
    return critical.index.tolist()


# 時間相關輔助函式

def convertHoursToDays(
    hours: float,
    workHoursPerDay: float = 8,
) -> float:
    """將工時轉換為工作天數。

    Args:
        hours: 工時數。
        workHoursPerDay: 每日工作時數。

    Returns:
        float: 對應的工作天數。
    """
    return hours / workHoursPerDay


def addWorkingDays(startDate: str, days: float) -> str:
    """計算加入工作天數後的日期，排除週末。

    Args:
        startDate: 起始日期字串（YYYY-MM-DD）。
        days: 需加入的工作天數。

    Returns:
        str: 計算後的日期字串。
    """
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
    """從 WBS 資料框提取工期資訊。

    Args:
        wbs: 任務資料表。
        durationField: 工期欄位名稱。

    Returns:
        Dict[str, float]: Task ID 與工期的對應字典。
    """
    if durationField not in wbs.columns:
        raise KeyError(f"WBS 缺少 {durationField} 欄位")
    return dict(zip(wbs["Task ID"], wbs[durationField].astype(float)))


def monteCarloSchedule(
    G: nx.DiGraph,
    oDurations: Dict[str, float],
    mDurations: Dict[str, float],
    pDurations: Dict[str, float],
    nIterations: int = 100,
    confidence: float = 0.9,
) -> Dict[str, Any]:
    """蒙地卡羅模擬計算專案完工時間。

    以三點估算法的 O、M、P 值為基礎，使用 Beta-PERT 分佈進行隨機抽樣後
    執行 CPM，取得專案完工時間的統計資料。

    Args:
        G: 依賴關係圖。
        oDurations: 樂觀工期。
        mDurations: 最可能工期。
        pDurations: 悲觀工期。
        nIterations: 模擬次數。
        confidence: 信心水準 (0~1)。

    Returns:
        Dict[str, Any]: 包含平均工期、標準差、最短與最長工期，
            以及對應信心水準的工期等統計資訊。
    """

    results: List[float] = []
    for _ in range(max(1, nIterations)):
        sampled: Dict[str, float] = {}
        for task in G.nodes:
            o = float(oDurations.get(task, 0))
            m = float(mDurations.get(task, 0))
            p = float(pDurations.get(task, 0))

            # 依 Beta-PERT 分佈產生模擬工期
            if p == o:
                simulatedDuration = o
            else:
                meanMu = (o + 4 * m + p) / 6
                meanMu = max(o, min(p, meanMu))
                if meanMu == o:
                    alpha = 1
                else:
                    alpha = 1 + 4 * ((meanMu - o) / (p - o))
                if meanMu == p:
                    beta = 1
                else:
                    beta = 1 + 4 * ((p - meanMu) / (p - o))
                randomBeta = np.random.beta(alpha, beta)
                simulatedDuration = o + randomBeta * (p - o)
            sampled[task] = float(simulatedDuration)

        forward = cpmForwardPass(G, sampled)
        projectEnd = max(v[1] for v in forward.values())
        results.append(projectEnd)

    arr = np.array(results)
    avg = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    minVal = float(arr.min())
    maxVal = float(arr.max())
    confidenceValue = float(np.quantile(arr, confidence))

    return {
        "average": avg,
        "std": std,
        "min": minVal,
        "max": maxVal,
        "confidence": confidence,
        "confidence_value": confidenceValue,
        "samples": results,
    }
