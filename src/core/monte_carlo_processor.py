"""蒙地卡羅模擬處理模組"""

from typing import Any, Dict

import networkx as nx
import pandas as pd

from ..cpm_processor import (
    extractDurationFromWbs,
    monteCarloSchedule,
)


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
    o_field = f"O_{role_key}"
    m_field = f"M_{role_key}"
    p_field = f"P_{role_key}"

    for field in (o_field, m_field, p_field):
        if field not in wbs.columns:
            raise KeyError(f"WBS 缺少 {field} 欄位")

    o_dur = extractDurationFromWbs(wbs, o_field)
    m_dur = extractDurationFromWbs(wbs, m_field)
    p_dur = extractDurationFromWbs(wbs, p_field)

    return monteCarloSchedule(
        graph,
        o_dur,
        m_dur,
        p_dur,
        iterations,
        confidence,
    )
