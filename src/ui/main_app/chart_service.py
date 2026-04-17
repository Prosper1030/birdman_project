"""主 GUI 圖表服務。"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde


def _configureChineseFont() -> None:
    """設定圖表使用的中文字型。"""
    plt.rcParams["font.sans-serif"] = [
        "Microsoft JhengHei",
        "SimHei",
        "Arial Unicode MS",
        "sans-serif",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def createGanttFigure(
    cpmData: pd.DataFrame,
    durations: dict[str, float],
    title: str,
    wbsDf: pd.DataFrame,
) -> Figure:
    """建立 CPM 甘特圖。"""
    fig = Figure(figsize=(16, 12), dpi=100)
    ax = fig.add_subplot(111)

    fig.patch.set_facecolor(plt.rcParams["figure.facecolor"])
    ax.set_facecolor(plt.rcParams["axes.facecolor"])
    fig.subplots_adjust(top=0.9, bottom=0.15, left=0.2, right=0.95)

    tasks = wbsDf["Task ID"].tolist()
    startTimes = [cpmData.at[taskId, "ES"] for taskId in tasks]
    taskDurations = [durations.get(taskId, 0) for taskId in tasks]
    yPositions = range(len(tasks))
    colors = ["red" if cpmData.at[taskId, "Critical"] else "skyblue" for taskId in tasks]

    ax.barh(
        yPositions,
        taskDurations,
        left=startTimes,
        color=colors,
        alpha=0.8,
        height=0.6,
        edgecolor=plt.rcParams["axes.edgecolor"],
        linewidth=1,
        zorder=2,
    )
    ax.set_yticks(list(yPositions))
    ax.set_yticklabels(
        tasks,
        fontsize=10,
        fontweight="bold",
        color=plt.rcParams["axes.labelcolor"],
    )
    ax.tick_params(axis="x", colors=plt.rcParams["xtick.color"])
    ax.tick_params(axis="y", colors=plt.rcParams["ytick.color"])
    for spine in ax.spines.values():
        spine.set_edgecolor(plt.rcParams["axes.edgecolor"])
    ax.grid(
        True,
        axis="x",
        linestyle="--",
        color=plt.rcParams["grid.color"],
        alpha=0.3,
        zorder=1,
    )
    ax.set_axisbelow(True)
    ax.set_xlabel(
        "時間 (小時)",
        fontsize=11,
        fontweight="bold",
        color=plt.rcParams["axes.labelcolor"],
    )
    ax.set_title(
        title,
        fontsize=14,
        pad=20,
        color=plt.rcParams["axes.labelcolor"],
    )

    for index, (duration, startTime) in enumerate(zip(taskDurations, startTimes)):
        if duration > 0:
            ax.text(
                startTime + duration + 2,
                index,
                f"{duration:.1f}h",
                va="center",
                fontsize=9,
                alpha=0.7,
                color=plt.rcParams["text.color"],
            )

    ax.invert_yaxis()
    return fig


def createRcpspGanttFigure(
    scheduleDf: pd.DataFrame,
    durationField: str,
    title: str,
) -> Figure:
    """建立 RCPSP 甘特圖。"""
    fig = Figure(figsize=(16, 12), dpi=100)
    ax = fig.add_subplot(111)

    fig.patch.set_facecolor(plt.rcParams["figure.facecolor"])
    ax.set_facecolor(plt.rcParams["axes.facecolor"])
    fig.subplots_adjust(top=0.9, bottom=0.15, left=0.2, right=0.95)

    tasks = scheduleDf["Task ID"].tolist()
    startTimes = scheduleDf["Start"].tolist()
    durations = scheduleDf[durationField].tolist()
    yPositions = range(len(tasks))

    ax.barh(
        yPositions,
        durations,
        left=startTimes,
        color="dodgerblue",
        alpha=0.8,
        height=0.6,
        edgecolor=plt.rcParams["axes.edgecolor"],
        linewidth=1,
        zorder=2,
    )
    ax.set_yticks(list(yPositions))
    ax.set_yticklabels(
        tasks,
        fontsize=10,
        fontweight="bold",
        color=plt.rcParams["axes.labelcolor"],
    )
    ax.tick_params(axis="x", colors=plt.rcParams["xtick.color"])
    ax.tick_params(axis="y", colors=plt.rcParams["ytick.color"])
    for spine in ax.spines.values():
        spine.set_edgecolor(plt.rcParams["axes.edgecolor"])
    ax.grid(
        True,
        axis="x",
        linestyle="--",
        color=plt.rcParams["grid.color"],
        alpha=0.3,
        zorder=1,
    )
    ax.set_axisbelow(True)
    ax.set_xlabel(
        "時間 (小時)",
        fontsize=11,
        fontweight="bold",
        color=plt.rcParams["axes.labelcolor"],
    )
    ax.set_title(
        title,
        fontsize=14,
        pad=20,
        color=plt.rcParams["axes.labelcolor"],
    )

    for index, (duration, startTime) in enumerate(zip(durations, startTimes)):
        if duration > 0:
            ax.text(
                startTime + duration + 0.1,
                index,
                f"{duration:.1f}h",
                va="center",
                fontsize=9,
                alpha=0.7,
                color=plt.rcParams["text.color"],
            )

    ax.invert_yaxis()
    return fig


def summarizeMonteCarloResults(results: list[float]) -> dict[str, float]:
    """計算蒙地卡羅模擬的統計摘要。"""
    arr = np.array(results, dtype=float)
    return {
        "average": float(arr.mean()),
        "std": float(arr.std()),
        "p50": float(np.percentile(arr, 50)),
        "p85": float(np.percentile(arr, 85)),
        "p95": float(np.percentile(arr, 95)),
    }


def renderMonteCarloFigure(
    figure: Figure,
    results: list[float],
    *,
    isDarkMode: bool,
    chartMode: str,
    selectedRole: str,
    iterations: int,
) -> dict[str, float]:
    """將蒙地卡羅結果繪製到既有 Figure，並回傳統計摘要。"""
    _configureChineseFont()

    stats = summarizeMonteCarloResults(results)
    arr = np.array(results, dtype=float)

    figure.clear()
    ax = figure.add_subplot(111)

    if isDarkMode:
        barColor = "lightblue"
        edgeColor = "white"
        textColor = "white"
        figure.patch.set_facecolor("#2b2b2b")
        ax.set_facecolor("#2b2b2b")
    else:
        barColor = "skyblue"
        edgeColor = "black"
        textColor = "black"
        figure.patch.set_facecolor("white")
        ax.set_facecolor("white")

    isDensityMode = chartMode == "密度模式"
    if isDensityMode:
        ax.hist(
            arr,
            bins=25,
            color=barColor,
            edgecolor=edgeColor,
            alpha=0.8,
            rwidth=0.9,
            density=True,
            label="直方圖",
        )
        try:
            if len(arr) > 1:
                kde = gaussian_kde(arr)
                xMin, xMax = arr.min(), arr.max()
                xRange = xMax - xMin
                xSmooth = np.linspace(
                    xMin - 0.1 * xRange,
                    xMax + 0.1 * xRange,
                    200,
                )
                kdeValues = kde(xSmooth)
                kdeColor = "#ff6b6b" if isDarkMode else "#e74c3c"
                kdeAlpha = 0.9 if isDarkMode else 0.8
                ax.plot(
                    xSmooth,
                    kdeValues,
                    color=kdeColor,
                    linewidth=2.5,
                    alpha=kdeAlpha,
                    label="KDE 密度曲線",
                )
                legend = ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
                legend.get_frame().set_facecolor(
                    "white" if not isDarkMode else "#404040"
                )
                legend.get_frame().set_edgecolor(textColor)
                for text in legend.get_texts():
                    text.set_color(textColor)
        except (ValueError, np.linalg.LinAlgError):
            pass
    else:
        ax.hist(
            arr,
            bins=25,
            color=barColor,
            edgecolor=edgeColor,
            alpha=0.8,
            rwidth=0.9,
            density=False,
        )

    roleText = "新手 (Novice)" if selectedRole == "newbie" else "專家 (Expert)"
    title = (
        f"蒙地卡羅模擬結果 ({chartMode})\n"
        f"分析對象: {roleText} | 模擬次數: {iterations:,} 次"
    )
    ax.set_title(title, color=textColor, fontsize=12, pad=15)
    ax.set_xlabel("工時 (小時)", color=textColor, fontsize=10)
    ax.set_ylabel("密度" if isDensityMode else "次數", color=textColor, fontsize=10)
    ax.tick_params(colors=textColor)

    statsText = (
        f"平均: {stats['average']:.1f}h\n"
        f"標準差: {stats['std']:.1f}h\n"
        f"中位數: {stats['p50']:.1f}h"
    )
    ax.text(
        0.02,
        0.98,
        statsText,
        transform=ax.transAxes,
        verticalalignment="top",
        fontsize=9,
        bbox=dict(
            boxstyle="round",
            facecolor="white" if not isDarkMode else "#404040",
            alpha=0.8,
            edgecolor=textColor,
        ),
        color=textColor,
    )

    figure.tight_layout()
    return stats


def initializeMonteCarloFigure(figure: Figure, *, isDarkMode: bool) -> None:
    """建立尚未執行模擬時的預設蒙地卡羅圖表。"""
    _configureChineseFont()

    figure.clear()
    ax = figure.add_subplot(111)

    if isDarkMode:
        textColor = "white"
        figure.patch.set_facecolor("#2b2b2b")
        ax.set_facecolor("#2b2b2b")
    else:
        textColor = "black"
        figure.patch.set_facecolor("white")
        ax.set_facecolor("white")

    ax.set_title("蒙地卡羅模擬結果\n(請先執行模擬)", color=textColor, fontsize=12)
    ax.set_xlabel("工時 (小時)", color=textColor, fontsize=10)
    ax.set_ylabel("次數", color=textColor, fontsize=10)
    ax.tick_params(colors=textColor)
    ax.text(
        0.5,
        0.5,
        "點擊「開始模擬」按鈕\n進行蒙地卡羅分析",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=14,
        color=textColor,
        alpha=0.6,
    )
    figure.tight_layout()


__all__ = [
    "createGanttFigure",
    "createRcpspGanttFigure",
    "initializeMonteCarloFigure",
    "renderMonteCarloFigure",
    "summarizeMonteCarloResults",
]
