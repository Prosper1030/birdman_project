"""蒙地卡羅模擬處理模組"""

from typing import Any, Dict, List

import networkx as nx
import pandas as pd
import numpy as np

from ..cpm_processor import cpmForwardPass


def run_monte_carlo_simulation(
    graph: nx.DiGraph,
    wbs: pd.DataFrame,
    iterations: int = 100,
    confidence: float = 0.9,
    role_key: str = "newbie",
) -> Dict[str, Any]:
    """依角色欄位執行蒙地卡羅模擬

    參數:
        graph: 依賴關係圖
        wbs:   合併後的 WBS 資料框
        iterations: 模擬次數
        confidence: 信心水準 (0~1)
        role_key: 角色鍵值，"newbie" 或 "expert"

    回傳值:
        模擬結果字典，含平均工期與信心水準等資訊
    """
    oCol = f"O_{role_key}"
    mCol = f"M_{role_key}"
    pCol = f"P_{role_key}"

    for field in (oCol, mCol, pCol):
        if field not in wbs.columns:
            raise KeyError(f"WBS 缺少 {field} 欄位")

    wbsDf = wbs.set_index("Task ID")

    results: List[float] = []
    for _ in range(max(1, iterations)):
        sampled: Dict[str, float] = {}
        for taskId in wbsDf.index:
            o = wbsDf.loc[taskId, oCol]
            m = wbsDf.loc[taskId, mCol]
            p = wbsDf.loc[taskId, pCol]

            # 處理 P 與 O 相等的邊界情況
            if p == o:
                simulatedDuration = o
            else:
                # 依 PERT 公式推導 alpha、beta 參數
                mu = (o + 4 * m + p) / 6
                mu = max(o, min(p, mu))
                if mu == o:
                    alpha = 1
                else:
                    alpha = 1 + 4 * ((mu - o) / (p - o))
                if mu == p:
                    beta = 1
                else:
                    beta = 1 + 4 * ((p - mu) / (p - o))

                # 使用 Beta 分佈取樣並映射至 O~P 區間
                randomBeta = np.random.beta(alpha, beta)
                simulatedDuration = o + randomBeta * (p - o)

            sampled[taskId] = float(simulatedDuration)

        forward = cpmForwardPass(graph, sampled)
        projectEnd = max(v[1] for v in forward.values())
        results.append(projectEnd)

    arr = np.array(results, dtype=float)
    avg = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    minV = float(arr.min())
    maxV = float(arr.max())
    confV = float(np.quantile(arr, confidence))

    return {
        "average": avg,
        "std": std,
        "min": minV,
        "max": maxV,
        "confidence": confidence,
        "confidence_value": confV,
        "samples": results,
    }
