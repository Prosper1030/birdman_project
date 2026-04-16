"""主視窗共用輔助函式。"""

from __future__ import annotations

try:
    import qdarkstyle
except ImportError:
    qdarkstyle = None

import matplotlib.pyplot as plt
import pandas as pd


def configureChartTheme(isDarkMode: bool) -> None:
    """統一設定所有圖表的顏色主題。"""
    if isDarkMode:
        darkBgColor = "#2b2b2b"
        textColor = "white"
        gridColor = "#555555"
        edgeColor = "#666666"
        plt.rcParams.update(
            {
                "figure.facecolor": darkBgColor,
                "axes.facecolor": darkBgColor,
                "axes.labelcolor": textColor,
                "axes.edgecolor": edgeColor,
                "text.color": textColor,
                "xtick.color": textColor,
                "ytick.color": textColor,
                "grid.color": gridColor,
                "axes.spines.left": True,
                "axes.spines.bottom": True,
                "axes.spines.top": True,
                "axes.spines.right": True,
            }
        )
        return

    lightBgColor = "white"
    textColor = "black"
    gridColor = "#cccccc"
    edgeColor = "black"
    plt.rcParams.update(
        {
            "figure.facecolor": lightBgColor,
            "axes.facecolor": lightBgColor,
            "axes.labelcolor": textColor,
            "axes.edgecolor": edgeColor,
            "text.color": textColor,
            "xtick.color": textColor,
            "ytick.color": textColor,
            "grid.color": gridColor,
            "axes.spines.left": True,
            "axes.spines.bottom": True,
            "axes.spines.top": True,
            "axes.spines.right": True,
        }
    )


def buildDarkModeStylesheet() -> str:
    """建立深色模式樣式表，缺少 qdarkstyle 時改用內建樣式。"""
    extraStyle = """
    QMainWindow {
        background-color: #2b2b2b;
        color: #ffffff;
    }
    QMenuBar {
        background-color: #353535;
        color: #ffffff;
        border: 1px solid #555555;
    }
    QMenuBar::item {
        background-color: transparent;
        color: #ffffff;
    }
    QMenuBar::item:selected {
        background-color: #4a90e2;
    }
    """

    if qdarkstyle is None:
        return """
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QTableView, QTabWidget::pane {
            background-color: #353535;
            color: #ffffff;
            border: 1px solid #555555;
        }
        QPushButton {
            background-color: #3d6fb4;
            color: #ffffff;
            border: 1px solid #5b87c8;
            padding: 4px 8px;
        }
        QPushButton:hover {
            background-color: #4a90e2;
        }
        """ + extraStyle

    return qdarkstyle.load_stylesheet_pyqt5() + extraStyle


def getCriticalPathEdges(graph, criticalPathNodes):
    """將關鍵路徑節點轉換為關鍵路徑邊線集合。"""
    if not criticalPathNodes or len(criticalPathNodes) < 2:
        return set()

    criticalEdges = set()
    for index in range(len(criticalPathNodes) - 1):
        currentNode = criticalPathNodes[index]
        nextNode = criticalPathNodes[index + 1]
        if graph.has_edge(currentNode, nextNode):
            criticalEdges.add((currentNode, nextNode))

    return criticalEdges


def addNoColumn(df: pd.DataFrame) -> pd.DataFrame:
    """若無 ``No.`` 欄位則新增連續編號。"""
    df = df.copy()
    firstCol = df.columns[0]
    if firstCol != "Task ID" and firstCol != "No.":
        try:
            asNum = pd.to_numeric(df[firstCol], errors="coerce")
            if asNum.notnull().all():
                df = df.drop(columns=[firstCol])
        except (ValueError, TypeError):
            pass
    df.insert(0, "No.", range(1, len(df) + 1))
    return df


def createCpmDisplayDf(
    fullResultsDf: pd.DataFrame,
    roleKey: str,
    timeKey: str,
) -> pd.DataFrame:
    """產生精簡版 CPM 結果表。"""
    coreDisplayCols = [
        "Task ID",
        "Name",
        "ES",
        "EF",
        "LS",
        "LF",
        "TF",
        "FF",
        "Critical",
    ]

    roleMap = {"novice": "newbie", "expert": "expert"}
    roleSuffix = roleMap.get(roleKey.lower(), roleKey.lower())
    timeColumn = f"{timeKey}_{roleSuffix}"

    columns = coreDisplayCols.copy()
    if timeColumn in fullResultsDf.columns:
        insertIndex = columns.index("Name") + 1
        columns.insert(insertIndex, timeColumn)

    existingCols = [column for column in columns if column in fullResultsDf.columns]
    return fullResultsDf[existingCols].copy()


__all__ = [
    "addNoColumn",
    "buildDarkModeStylesheet",
    "configureChartTheme",
    "createCpmDisplayDf",
    "getCriticalPathEdges",
]
