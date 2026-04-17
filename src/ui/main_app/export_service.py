"""主 GUI 匯出服務。"""

from __future__ import annotations

from typing import Any

import pandas as pd
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QFileDialog, QMessageBox


def _resolveSavePath(path: str, fmt: str) -> str:
    """補齊副檔名後回傳實際儲存路徑。"""
    if not path:
        return path

    suffix = f".{fmt.lower()}"
    if path.lower().endswith(suffix):
        return path
    return f"{path}{suffix}"


def _getTableFileFilter(fmt: str) -> str:
    """回傳表格匯出的檔案篩選器。"""
    if fmt == "xlsx":
        return "Excel 檔案 (*.xlsx)"
    return "CSV Files (*.csv)"


def _getFigureFileFilter(fmt: str) -> str:
    """回傳圖檔匯出的檔案篩選器。"""
    if fmt == "svg":
        return "SVG 向量圖 (*.svg)"
    return "PNG 圖片 (*.png)"


def exportDataFrameWithDialog(
    parent: Any,
    dataframe: pd.DataFrame | None,
    *,
    title: str,
    emptyMessage: str,
    defaultName: str = "",
    fmt: str = "csv",
    includeIndex: bool = False,
    successMessage: str = "已匯出 {path}",
) -> str | None:
    """透過檔案對話框匯出 DataFrame。"""
    if dataframe is None:
        QMessageBox.warning(parent, "警告", emptyMessage)
        return None

    path, _ = QFileDialog.getSaveFileName(
        parent,
        title,
        defaultName,
        _getTableFileFilter(fmt),
    )
    if not path:
        return None

    targetPath = _resolveSavePath(path, fmt)
    try:
        if fmt == "xlsx":
            dataframe.to_excel(targetPath, index=includeIndex)
        else:
            dataframe.to_csv(targetPath, index=includeIndex, encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        QMessageBox.critical(parent, "錯誤", f"匯出檔案時發生錯誤：{exc}")
        return None

    QMessageBox.information(parent, "完成", successMessage.format(path=targetPath))
    return targetPath


def exportFigureWithDialog(
    parent: Any,
    figure: Figure | None,
    *,
    title: str,
    emptyMessage: str,
    fmt: str = "png",
    successMessage: str = "已匯出 {path}",
    savefigKwargs: dict[str, Any] | None = None,
) -> str | None:
    """透過檔案對話框匯出 Matplotlib 圖形。"""
    if figure is None:
        QMessageBox.warning(parent, "警告", emptyMessage)
        return None

    path, _ = QFileDialog.getSaveFileName(
        parent,
        title,
        "",
        _getFigureFileFilter(fmt),
    )
    if not path:
        return None

    targetPath = _resolveSavePath(path, fmt)
    options = {"format": fmt, "bbox_inches": "tight", "dpi": 300}
    if savefigKwargs:
        options.update(savefigKwargs)
    try:
        figure.savefig(targetPath, **options)
    except (OSError, ValueError) as exc:
        QMessageBox.critical(parent, "錯誤", f"匯出圖檔時發生錯誤：{exc}")
        return None

    QMessageBox.information(parent, "完成", successMessage.format(path=targetPath))
    return targetPath


__all__ = [
    "exportDataFrameWithDialog",
    "exportFigureWithDialog",
]
