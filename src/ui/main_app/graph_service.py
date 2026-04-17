"""主 GUI 依賴圖服務。"""

from __future__ import annotations

from typing import Any

from ... import visualizer
from ...matplotlib_runtime import prepareMatplotlibForQt

prepareMatplotlibForQt()

from matplotlib.backends.backend_qt5agg import (  # noqa: E402
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure  # noqa: E402
from PyQt5.QtWidgets import QLayout, QWidget  # noqa: E402


def clearLayoutWidgets(layout: QLayout) -> None:
    """移除 layout 中既有的 widget。"""
    for index in reversed(range(layout.count())):
        oldWidget = layout.itemAt(index).widget()
        if oldWidget is not None:
            oldWidget.setParent(None)


def updateContainerMinimumSize(
    container: QWidget,
    canvas: FigureCanvas,
    scale: float = 1.1,
) -> None:
    """依照畫布尺寸調整容器最小大小。"""
    width, height = canvas.get_width_height()
    if width > 0 and height > 0:
        container.setMinimumSize(int(width * scale), int(height * scale))


def renderDependencyGraph(
    *,
    graph,
    sccMap: dict,
    layerMap: dict,
    vizParams: dict,
    layout: QLayout,
    container: QWidget,
    criticalPathEdges=None,
) -> tuple[Figure, FigureCanvas]:
    """建立依賴圖並放入指定容器。"""
    clearLayoutWidgets(layout)
    figure = visualizer.create_dependency_graph_figure(
        graph,
        sccMap,
        layerMap,
        vizParams,
        criticalPathEdges,
    )
    canvas = FigureCanvas(figure)
    layout.addWidget(canvas)
    canvas.draw()
    updateContainerMinimumSize(container, canvas)
    return figure, canvas


__all__ = [
    "clearLayoutWidgets",
    "renderDependencyGraph",
    "updateContainerMinimumSize",
]
