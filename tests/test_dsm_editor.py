import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pandas as pd  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from src.ui.dsm_editor import DsmEditor  # noqa: E402


def test_build_dsm_matrix():
    """測試編輯器可依連線生成 DSM"""
    app = QApplication.instance() or QApplication([])
    wbs = pd.DataFrame(
        {
            "Task ID": ["A1", "A2", "A3"],
            "Property": ["A", "A", "B"],
            "Name": ["任務1", "任務2", "任務3"],
        }
    )
    editor = DsmEditor(wbs)
    editor.addDependencyById("A1", "A2")
    editor.addDependencyById("A2", "A3")
    matrix = editor.buildDsmMatrix()
    assert matrix.loc["A1", "A2"] == 1
    assert matrix.loc["A2", "A3"] == 1
    assert matrix.loc["A1", "A3"] == 0
    editor.close()
    app.quit()
