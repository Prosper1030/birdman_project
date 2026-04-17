"""主 GUI 摘要資訊服務。"""

from __future__ import annotations

import pandas as pd

from .display_service import getRoleLabel


def countDependencies(dsmDf: pd.DataFrame | None) -> int:
    """計算 DSM 中的依賴數量。"""
    if dsmDf is None or dsmDf.empty:
        return 0
    return int(dsmDf.fillna(0).astype(float).ne(0).sum().sum())


def buildAnalysisSummaryHtml(
    *,
    sortedWbs: pd.DataFrame | None,
    mergedWbs: pd.DataFrame | None,
    sortedDsm: pd.DataFrame | None,
    sccMap: dict[str, int] | None,
    hasResources: bool,
    roleKey: str | None = None,
    timeKey: str | None = None,
    projectEnd: float | None = None,
) -> str:
    """建立結果頁上方的分析摘要。"""
    rawTaskCount = 0 if sortedWbs is None else len(sortedWbs)
    mergedTaskCount = 0 if mergedWbs is None else len(mergedWbs)
    dependencyCount = countDependencies(sortedDsm)
    sccCount = len(set((sccMap or {}).values()))
    resourcesText = "已匯入" if hasResources else "未匯入"

    lines = [
        "<b>分析摘要</b>",
        f"原始任務數：{rawTaskCount}",
        f"合併後任務數：{mergedTaskCount}",
        f"依賴數：{dependencyCount}",
        f"SCC 數量：{sccCount}",
        f"Resources：{resourcesText}",
    ]

    if roleKey is not None and timeKey is not None and projectEnd is not None:
        lines.append(
            "目前顯示："
            f"{getRoleLabel(roleKey)} / {timeKey} / 總工時 {projectEnd:.2f} 小時"
        )

    return "　|　".join(lines)
