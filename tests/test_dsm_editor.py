from PyQt5.QtWidgets import QApplication
import pandas as pd

from src.ui.dsm_editor import DsmEditor


def test_build_dsm_matrix():
    """驗證 buildDsmMatrix 生成正確的 DSM"""
    app = QApplication.instance() or QApplication([])
    wbs = pd.DataFrame({"Task ID": ["T1", "T2", "T3"]})
    editor = DsmEditor(wbs)
    editor.addDependencyById("T1", "T2")
    editor.addDependencyById("T2", "T3")
    matrix = editor.buildDsmMatrix()
    assert matrix.loc["T1", "T2"] == 1
    assert matrix.loc["T2", "T3"] == 1
    assert matrix.loc["T1", "T3"] == 0
    editor.close()
    app.quit()
