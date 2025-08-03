"""資源資料處理模組"""

from typing import Dict
import math
import pandas as pd


def readResources(path: str, wbs: pd.DataFrame, durationField: str = "Te_newbie") -> Dict[str, int]:
    """讀取資源資料並計算各組可同時執行的任務數

    先計算 WBS 中任務平均工期，若資源表提供 Headcount_Cap 直接使用，
    否則以 Hr_Per_Week 除以平均工期估算可並行的任務數。
    """
    resources = pd.read_csv(path, encoding="utf-8-sig")
    avgDuration = float(wbs[durationField].dropna().astype(float).mean() or 0)
    if avgDuration <= 0:
        avgDuration = 1.0

    capacityMap: Dict[str, int] = {}
    for _, row in resources.iterrows():
        group = row.get("Group")
        headcount = row.get("Headcount_Cap")
        hours = row.get("Hr_Per_Week")
        cap = None
        if pd.notna(headcount):
            try:
                cap = int(float(headcount))
            except ValueError:
                cap = None
        if cap is None:
            cap = 0
            if pd.notna(hours):
                try:
                    cap = math.floor(float(hours) / avgDuration)
                except ValueError:
                    cap = 0
            cap = max(1, cap)
        capacityMap[str(group)] = cap
    return capacityMap
