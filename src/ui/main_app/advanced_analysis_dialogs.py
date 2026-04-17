"""主 GUI 進階分析對話框。"""

from __future__ import annotations

from collections.abc import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


def _buildResultTextEdit(resultHtml: str, *, maximumHeight: int | None = None) -> QTextEdit:
    """建立只讀結果文字區塊。"""
    textEdit = QTextEdit()
    textEdit.setHtml(resultHtml)
    textEdit.setReadOnly(True)
    if maximumHeight is not None:
        textEdit.setMaximumHeight(maximumHeight)
    return textEdit


def showFigureResultDialog(
    parent: QWidget,
    title: str,
    resultHtml: str,
    figure: Figure,
    *,
    figureScrollable: bool = False,
    textMaximumHeight: int | None = None,
    minimumWidth: int = 600,
    minimumHeight: int = 500,
    existingDialog: QDialog | None = None,
    onDialogClosed: Callable[[], None] | None = None,
    floating: bool = False,
) -> QDialog:
    """建立帶圖表的結果對話框。"""
    if existingDialog is not None:
        try:
            existingDialog.close()
        except RuntimeError:
            pass

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(minimumWidth, minimumHeight)

    if floating:
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        if onDialogClosed is not None:
            dialog.finished.connect(lambda _: onDialogClosed())

    layout = QVBoxLayout()
    layout.addWidget(
        _buildResultTextEdit(resultHtml, maximumHeight=textMaximumHeight)
    )

    canvas = FigureCanvas(figure)
    if figureScrollable:
        scrollArea = QScrollArea()
        scrollArea.setWidget(canvas)
        scrollArea.setWidgetResizable(True)
        scrollArea.setMinimumHeight(400)
        layout.addWidget(scrollArea)
    else:
        layout.addWidget(canvas)

    buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
    buttonBox.accepted.connect(dialog.accept)
    layout.addWidget(buttonBox)
    dialog.setLayout(layout)

    if floating:
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    else:
        dialog.exec_()

    return dialog


def promptResourceCapacities(
    parent: QWidget,
    resourceCap: dict[str, int],
    manualResourceCap: dict[str, int],
) -> dict[str, int] | None:
    """顯示資源容量設定對話框。"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("設定資源容量")

    form = QFormLayout(dialog)
    spinBoxes: dict[str, QSpinBox] = {}
    for group, cap in resourceCap.items():
        spin = QSpinBox()
        spin.setMinimum(1)
        spin.setValue(manualResourceCap.get(group, cap))
        form.addRow(QLabel(group), spin)
        spinBoxes[group] = spin

    buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    form.addRow(buttonBox)
    buttonBox.accepted.connect(dialog.accept)
    buttonBox.rejected.connect(dialog.reject)

    if dialog.exec_() != QDialog.Accepted:
        return None

    return {group: spin.value() for group, spin in spinBoxes.items()}
