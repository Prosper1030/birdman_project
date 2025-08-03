"""表格模型模組"""

from __future__ import annotations

from PyQt5.QtCore import QAbstractTableModel, Qt
from pandas import DataFrame


class PandasModel(QAbstractTableModel):
    """用於顯示 DataFrame 的 Qt 模型"""

    def __init__(self, df: DataFrame, dsm_mode: bool = False) -> None:
        super().__init__()
        self._df = df
        self._dsm_mode = dsm_mode

    def rowCount(self, parent=None):  # type: ignore[override]
        return self._df.shape[0]

    def columnCount(self, parent=None):  # type: ignore[override]
        return self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        value = self._df.iloc[index.row(), index.column()]
        if role == Qt.DisplayRole:
            return str(value)
        if self._dsm_mode and role == Qt.BackgroundRole:
            """若值為 1 則以紅色標示，避免解析失敗"""
            try:
                if str(value).strip() in {"1", "1.0"}:
                    from PyQt5.QtGui import QColor
                    return QColor(255, 120, 120)
                if float(value) == 1:
                    from PyQt5.QtGui import QColor
                    return QColor(255, 120, 120)
            except (ValueError, TypeError):
                pass
        return None

    def headerData(
        self, section, orientation, role=Qt.DisplayRole
    ):  # type: ignore[override]
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            if self._dsm_mode:
                return str(self._df.index[section])
            return str(section + 1)
        return None


__all__ = ["PandasModel"]
