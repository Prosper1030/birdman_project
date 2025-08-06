import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pandas as pd  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402
from PyQt5.QtCore import QPointF  # noqa: E402

from src.ui.dsm_editor import DsmEditor, LayoutAlgorithm  # noqa: E402


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


def test_layout_algorithms():
    """測試佈局演算法"""
    app = QApplication.instance() or QApplication([])
    wbs = pd.DataFrame(
        {
            "Task ID": ["A1", "A2", "A3", "A4"],
            "Property": ["A", "A", "B", "B"],
            "Name": ["任務1", "任務2", "任務3", "任務4"],
        }
    )
    editor = DsmEditor(wbs)

    # 測試階層式佈局
    editor.applyLayout(LayoutAlgorithm.HIERARCHICAL)
    positions_hierarchical = {taskId: node.pos() for taskId, node in editor.nodes.items()}

    # 測試正交式佈局
    editor.applyLayout(LayoutAlgorithm.ORTHOGONAL)
    positions_orthogonal = {taskId: node.pos() for taskId, node in editor.nodes.items()}

    # 測試力導向佈局
    editor.applyLayout(LayoutAlgorithm.FORCE_DIRECTED)
    positions_force = {taskId: node.pos() for taskId, node in editor.nodes.items()}

    # 確認位置有改變
    assert positions_hierarchical != positions_orthogonal
    assert positions_orthogonal != positions_force

    editor.close()
    app.quit()


def test_undo_redo_functionality():
    """測試撤銷/重做功能"""
    app = QApplication.instance() or QApplication([])
    wbs = pd.DataFrame(
        {
            "Task ID": ["A1", "A2", "A3"],
            "Property": ["A", "A", "B"],
            "Name": ["任務1", "任務2", "任務3"],
        }
    )
    editor = DsmEditor(wbs)

    # 初始狀態：無依賴關係
    assert len(editor.edges) == 0

    # 新增依賴關係
    editor.addDependencyById("A1", "A2")
    assert len(editor.edges) == 1
    assert ("A1", "A2") in editor.edges

    # 撤銷操作
    editor.undo()
    assert len(editor.edges) == 0

    # 重做操作
    editor.redo()
    assert len(editor.edges) == 1
    assert ("A1", "A2") in editor.edges

    editor.close()
    app.quit()


def test_node_custom_properties():
    """測試節點自訂屬性"""
    app = QApplication.instance() or QApplication([])
    wbs = pd.DataFrame(
        {
            "Task ID": ["A1"],
            "Property": ["A"],
            "Name": ["任務1"],
        }
    )
    editor = DsmEditor(wbs)

    # 獲取節點
    node = editor.nodes["A1"]

    # 測試初始自訂屬性
    assert node.customData["assignee"] == ""
    assert node.customData["status"] == ""
    assert node.customData["duration"] == 0
    assert node.customData["priority"] == "Medium"

    # 修改屬性
    node.customData.update({
        "assignee": "張三",
        "status": "進行中",
        "duration": 8,
        "priority": "High"
    })

    # 驗證修改
    assert node.customData["assignee"] == "張三"
    assert node.customData["status"] == "進行中"
    assert node.customData["duration"] == 8
    assert node.customData["priority"] == "High"

    editor.close()
    app.quit()


def test_grid_functionality():
    """測試網格功能"""
    app = QApplication.instance() or QApplication([])
    wbs = pd.DataFrame(
        {
            "Task ID": ["A1"],
            "Property": ["A"],
            "Name": ["任務1"],
        }
    )
    editor = DsmEditor(wbs)

    # 測試網格顯示切換
    editor.view.setGridVisible(True)
    assert editor.view.showGrid is True

    editor.view.setGridVisible(False)
    assert editor.view.showGrid is False

    # 測試網格對齊
    editor.view.setSnapToGrid(True)
    assert editor.view.snapToGrid is True

    # 測試點對齊功能
    point = QPointF(23, 37)
    snapped = editor.view.snapPointToGrid(point)
    expected = QPointF(20, 40)  # 預設網格大小 20
    assert snapped == expected

    editor.close()
    app.quit()
