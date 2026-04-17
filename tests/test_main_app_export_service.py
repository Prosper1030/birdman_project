from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from src.ui.main_app.export_service import (
    exportDataFrameWithDialog,
    exportFigureWithDialog,
)


def test_export_dataframe_with_dialog_writes_csv(monkeypatch, tmp_path):
    """DataFrame 匯出應自動補上副檔名並寫入 CSV。"""
    target_path = tmp_path / "sorted_wbs"
    info_calls = []

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target_path), "CSV Files (*.csv)")),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *args: info_calls.append(args)),
    )

    dataframe = pd.DataFrame({"Task ID": ["A"], "TRF": [1]})
    written_path = exportDataFrameWithDialog(
        None,
        dataframe,
        title="匯出排序後 WBS",
        defaultName="sorted_wbs.csv",
        emptyMessage="沒有資料",
    )

    assert written_path == str(target_path.with_suffix(".csv"))
    assert target_path.with_suffix(".csv").exists()
    assert "已匯出" in info_calls[0][2]


def test_export_dataframe_with_dialog_warns_when_missing(monkeypatch):
    """沒有資料時應顯示警告並停止匯出。"""
    warning_calls = []

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *args: warning_calls.append(args)),
    )

    result = exportDataFrameWithDialog(
        None,
        None,
        title="匯出排序後 WBS",
        emptyMessage="請先執行分析",
    )

    assert result is None
    assert warning_calls[0][2] == "請先執行分析"


def test_export_figure_with_dialog_writes_png(monkeypatch, tmp_path):
    """圖檔匯出應自動補上副檔名並寫入 PNG。"""
    target_path = tmp_path / "gantt_chart"
    info_calls = []

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target_path), "PNG 圖片 (*.png)")),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *args: info_calls.append(args)),
    )

    figure = Figure()
    figure.add_subplot(111).plot([0, 1], [0, 1])

    written_path = exportFigureWithDialog(
        None,
        figure,
        title="匯出甘特圖",
        emptyMessage="沒有圖形",
    )

    assert written_path == str(target_path.with_suffix(".png"))
    assert target_path.with_suffix(".png").exists()
    assert "已匯出" in info_calls[0][2]
