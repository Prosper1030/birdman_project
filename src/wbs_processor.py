# -*- coding: utf-8 -*-
"""WBS 處理模組"""

from __future__ import annotations

import pandas as pd
from typing import Dict, List

from .dsm_processor import DSMData

TIME_COLUMNS = [
    'O_expert', 'M_expert', 'P_expert', 'Te_expert',
    'O_newbie', 'M_newbie', 'P_newbie', 'Te_newbie'
]


def readWbs(path: str) -> pd.DataFrame:
    """讀取 WBS CSV 並驗證"""
    df = pd.read_csv(path)
    if 'Task ID' not in df.columns or 'TRF' not in df.columns:
        raise ValueError('WBS 缺少必要欄位')
    df['Task ID'] = df['Task ID'].astype(str)
    df['TRF'] = pd.to_numeric(df['TRF'], errors='coerce').fillna(0)
    return df


def validateIds(wbs: pd.DataFrame, dsm: DSMData):
    """檢查 WBS 與 DSM 的 Task_ID 是否一致"""
    idsDsm = set(dsm.taskIds)
    idsWbs = set(wbs['Task ID'])
    if idsDsm != idsWbs:
        missing = idsDsm - idsWbs
        extra = idsWbs - idsDsm
        msg = []
        if missing:
            msg.append(f'缺少 {missing}')
        if extra:
            msg.append(f'多出 {extra}')
        raise ValueError('Task_ID 不一致: ' + ' '.join(msg))


def reorderWbs(wbs: pd.DataFrame, order: List[str], sccMap: Dict[str, int]) -> pd.DataFrame:
    """依照拓撲排序與 SCC 重新排序 WBS"""
    wbs = wbs.set_index('Task ID').loc[order].reset_index()
    layers = [0] * len(order)
    for i, tid in enumerate(order):
        layers[i] = sccMap.get(tid, 0)
    wbs['SCC_ID'] = [sccMap.get(tid, 0) for tid in order]
    return wbs


def mergeByScc(wbs: pd.DataFrame, sccMap: Dict[str, int], year: str = '25') -> pd.DataFrame:
    """將相同 SCC_ID 的任務合併並計算新工時"""
    merged = []
    serial = 1
    grouped = wbs.groupby('SCC_ID')
    for sccId, group in grouped:
        if len(group) == 1 and sccId == 0:
            merged.append(group.assign(New_Task_ID=group['Task ID']).iloc[0])
            continue
        newId = f"M{year}-{serial:03d}[{','.join(group['Task ID'])}]"
        serial += 1
        trfSum = group['TRF'].sum()
        n = len(group)
        k = 1 + ((trfSum / n) * 10) ** 0.5 / 10 + 0.05 * (n - 1)
        data = {
            'New_Task_ID': newId,
            'TRF': trfSum,
            'SCC_ID': sccId
        }
        for col in TIME_COLUMNS:
            total = group[col].sum() if col in group.columns else 0
            data[col] = total * k
        merged.append(pd.Series(data))
    mergedDf = pd.DataFrame(merged)
    return mergedDf
