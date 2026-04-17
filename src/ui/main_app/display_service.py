"""主 GUI 顯示模式與文案服務。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


TIME_MODE_OPTIONS = [
    "期望時間 (Te)",
    "樂觀時間 (O)",
    "悲觀時間 (P)",
    "最可能時間 (M)",
]

TIME_MODE_MAP = {
    "期望時間 (Te)": "Te",
    "樂觀時間 (O)": "O",
    "悲觀時間 (P)": "P",
    "最可能時間 (M)": "M",
}

TIME_MODE_LABEL_MAP = {
    "Te": "期望時間",
    "O": "樂觀時間",
    "P": "悲觀時間",
    "M": "最可能時間",
}

ROLE_LABEL_MAP = {
    "newbie": "新手",
    "expert": "專家",
}


@dataclass(slots=True)
class ScenarioDisplayState:
    """甘特圖與 CPM 顯示狀態。"""

    timeKey: str
    roleLabel: str
    modeLabel: str
    totalHoursText: str
    figureTitle: str
    displayDf: pd.DataFrame


def resolveTimeKey(modeText: str) -> str:
    """將下拉文字轉成時間欄位鍵值。"""
    return TIME_MODE_MAP.get(modeText, "Te")


def getRoleLabel(roleKey: str) -> str:
    """取得角色顯示文字。"""
    return ROLE_LABEL_MAP.get(roleKey, roleKey)


def buildRoleStatusMessage(roleKey: str) -> str:
    """建立角色切換狀態列文字。"""
    return f"已切換至 {getRoleLabel(roleKey)} 模式"


def buildScenarioDisplayState(
    *,
    roleKey: str,
    timeKey: str,
    projectEnd: float,
    displayDf: pd.DataFrame,
) -> ScenarioDisplayState:
    """建立顯示情境所需的文案與資料。"""
    roleLabel = getRoleLabel(roleKey)
    modeLabel = TIME_MODE_LABEL_MAP.get(timeKey, timeKey)
    totalHoursText = f"總工時：{projectEnd:.1f} 小時"
    keyTitle = f"{roleLabel} - {modeLabel} ({timeKey}_{roleKey})"
    figureTitle = f"{keyTitle}\n總工時: {projectEnd:.2f} 小時"
    return ScenarioDisplayState(
        timeKey=timeKey,
        roleLabel=roleLabel,
        modeLabel=modeLabel,
        totalHoursText=totalHoursText,
        figureTitle=figureTitle,
        displayDf=displayDf,
    )
