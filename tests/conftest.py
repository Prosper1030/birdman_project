import os

os.environ.setdefault("QT_QPA_PLATFORM", "minimal")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="session")
def qapp():
    """提供整個測試工作階段共用的 QApplication。"""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def suppress_blocking_message_boxes(monkeypatch):
    """避免測試期間被 QMessageBox 阻塞。"""
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *args, **kwargs: QMessageBox.Ok),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *args, **kwargs: QMessageBox.Ok),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda *args, **kwargs: QMessageBox.Ok),
    )
