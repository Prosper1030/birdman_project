import time
from pathlib import Path

import pandas as pd
import pytest
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from src.dsm_processor import readDsm
from src.gui_qt import BirdmanQtApp, launch_editor
from src.ui.dsm_editor import DsmEditor
from src.ui.dsm_editor.session import (
    listSessionSnapshots,
    validateEditorInputs,
    writeSessionSnapshot,
)


def build_test_wbs(task_ids: list[str]) -> pd.DataFrame:
    """建立測試用 WBS。"""
    return pd.DataFrame(
        {
            "Task ID": task_ids,
            "Property": ["測試"] * len(task_ids),
            "Name": [f"任務{index + 1}" for index in range(len(task_ids))],
        }
    )


def build_test_dsm(task_ids: list[str], edges: list[tuple[str, str]]) -> pd.DataFrame:
    """依據邊列表建立測試用 DSM。"""
    dsm = pd.DataFrame(0, index=task_ids, columns=task_ids, dtype=int)
    for src, dst in edges:
        dsm.loc[dst, src] = 1
    return dsm


def write_source_files(
    root: Path,
    wbs_df: pd.DataFrame,
    dsm_df: pd.DataFrame,
) -> tuple[Path, Path]:
    """寫入測試用 WBS/DSM 來源檔。"""
    wbs_path = root / "WBS.csv"
    dsm_path = root / "DSM.csv"
    wbs_df.to_csv(wbs_path, index=False, encoding="utf-8-sig")
    dsm_df.to_csv(dsm_path, encoding="utf-8-sig")
    return wbs_path, dsm_path


def test_editor_loads_existing_dsm_and_reports_clean_state(qapp):
    """編輯器可載入既有 DSM，且初始狀態不應標記為 dirty。"""
    wbs = build_test_wbs(["A1", "A2", "A3"])
    dsm = build_test_dsm(
        ["A1", "A2", "A3"],
        [("A1", "A2"), ("A2", "A3")],
    )

    editor = DsmEditor(wbs, dsmDf=dsm)

    pd.testing.assert_frame_equal(editor.getCurrentDsmDataFrame(), dsm)
    assert editor.isSessionDirty() is False
    assert editor.session.hasCycles is False
    assert editor.sccListWidget.count() == 0

    editor.close()


def test_validate_editor_inputs_rejects_duplicate_wbs_task_id():
    """重複的 WBS Task ID 應直接阻止載入。"""
    wbs = pd.DataFrame(
        {
            "Task ID": ["A1", "A1"],
            "Name": ["任務1", "任務1-重複"],
        }
    )

    with pytest.raises(ValueError, match="WBS 存在重複的 Task ID"):
        validateEditorInputs(wbs)


def test_validate_editor_inputs_allows_blank_editor_without_wbs():
    """未提供 WBS 時，應可建立空白編輯器工作階段。"""
    wbs, dsm = validateEditorInputs(pd.DataFrame())

    assert list(wbs.columns) == ["Task ID", "Name", "Property"]
    assert wbs.empty is True
    assert dsm.empty is True


def test_validate_editor_inputs_rejects_non_square_dsm():
    """非方陣 DSM 應回報明確錯誤。"""
    wbs = build_test_wbs(["A1", "A2"])
    dsm = pd.DataFrame(
        [[0, 1, 0], [0, 0, 1]],
        index=["A1", "A2"],
        columns=["A1", "A2", "A3"],
    )

    with pytest.raises(ValueError, match="DSM 必須為方陣"):
        validateEditorInputs(wbs, dsm)


def test_validate_editor_inputs_rejects_task_id_mismatch():
    """DSM 與 WBS Task ID 不對齊時應拒絕載入。"""
    wbs = build_test_wbs(["A1", "A2"])
    dsm = pd.DataFrame(
        [[0, 1], [0, 0]],
        index=["A1", "A3"],
        columns=["A1", "A3"],
    )

    with pytest.raises(ValueError, match="DSM 缺少以下 WBS 任務"):
        validateEditorInputs(wbs, dsm)


def test_cycle_changes_update_scc_summary_and_selection(qapp):
    """新增循環依賴後，SCC 摘要與高亮應立即同步。"""
    wbs = build_test_wbs(["A1", "A2", "A3"])
    editor = DsmEditor(wbs)

    editor.addDependencyById("A1", "A2")
    editor.addDependencyById("A2", "A1")

    assert editor.session.hasCycles is True
    assert len(editor.getCurrentSccSummary()) == 1
    assert editor.getCurrentSccSummary()[0].taskIds == ["A1", "A2"]
    assert editor.sccListWidget.count() == 1

    editor.sccListWidget.setCurrentRow(0)
    assert editor.highlightedSccTaskIds == {"A1", "A2"}

    editor.undo()
    assert editor.session.hasCycles is False
    assert editor.sccListWidget.count() == 0

    editor.close()


def test_editor_can_create_node_from_blank_state(qapp):
    """空白編輯器應可直接新增任務節點。"""
    editor = DsmEditor(pd.DataFrame())

    node = editor.createNode(
        taskId="TASK-001",
        taskName="建立測試任務",
        taskProperty="TEST",
    )

    assert node.taskId == "TASK-001"
    assert "TASK-001" in editor.nodes
    snapshot = editor.buildWbsSnapshot()
    assert snapshot.loc[0, "Task ID"] == "TASK-001"
    assert snapshot.loc[0, "Name"] == "建立測試任務"
    assert snapshot.loc[0, "Property"] == "TEST"
    assert editor.isSessionDirty() is True

    editor.close()


def test_export_dsm_with_cycles_still_writes_matrix(tmp_path, monkeypatch, qapp):
    """含循環時仍可匯出 DSM，且會保留正確矩陣內容。"""
    export_path = tmp_path / "exported_dsm.csv"
    warning_messages = []

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(export_path), "CSV Files (*.csv)")),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(
            lambda *args, **kwargs: warning_messages.append(args[2]) or QMessageBox.Ok
        ),
    )

    wbs = build_test_wbs(["A1", "A2"])
    editor = DsmEditor(wbs)
    editor.addDependencyById("A1", "A2")
    editor.addDependencyById("A2", "A1")

    editor.exportDsm()

    exported = readDsm(str(export_path))
    pd.testing.assert_frame_equal(exported, editor.buildDsmMatrix())
    assert any("後續 CPM 或排序分析可能受影響" in message for message in warning_messages)

    editor.close()


def test_autosave_only_keeps_latest_ten_snapshots(tmp_path, qapp):
    """自動存檔應只保留最近 10 份快照。"""
    autosave_root = tmp_path / ".birdman_autosave"
    wbs = build_test_wbs(["A1", "A2"])
    dsm = build_test_dsm(["A1", "A2"], [])
    wbs_path, dsm_path = write_source_files(tmp_path, wbs, dsm)

    editor = DsmEditor(
        wbs,
        dsmDf=dsm,
        wbsPath=str(wbs_path),
        dsmPath=str(dsm_path),
        autosaveRoot=autosave_root,
    )
    editor.addDependencyById("A1", "A2")

    for _ in range(12):
        editor._autosaveIfNeeded()
        time.sleep(0.001)

    snapshots = listSessionSnapshots(editor.session)
    assert len(snapshots) == 10
    assert all((snapshot.snapshotDir / "session.json").exists() for snapshot in snapshots)

    editor.close()


def test_editor_restores_latest_snapshot_when_user_confirms(
    tmp_path,
    monkeypatch,
    qapp,
):
    """重新開啟相同來源時，應可恢復較新的快照。"""
    autosave_root = tmp_path / ".birdman_autosave"
    wbs = build_test_wbs(["A1", "A2"])
    original_dsm = build_test_dsm(["A1", "A2"], [])
    wbs_path, dsm_path = write_source_files(tmp_path, wbs, original_dsm)

    first_editor = DsmEditor(
        wbs,
        dsmDf=original_dsm,
        wbsPath=str(wbs_path),
        dsmPath=str(dsm_path),
        autosaveRoot=autosave_root,
    )
    first_editor.addDependencyById("A1", "A2")
    writeSessionSnapshot(first_editor.session, reason="autosave")

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.Yes),
    )

    restored_editor = DsmEditor(
        wbs,
        dsmDf=original_dsm,
        wbsPath=str(wbs_path),
        dsmPath=str(dsm_path),
        autosaveRoot=autosave_root,
    )

    assert restored_editor.isSessionDirty() is True
    assert int(restored_editor.getCurrentDsmDataFrame().values.sum()) == 1
    assert restored_editor.noticeText.startswith("已恢復工作階段快照：")

    first_editor.close()
    restored_editor.close()


def test_launch_editor_smoke_loads_existing_wbs_and_dsm(tmp_path, qapp):
    """CLI/啟動器模式下可直接帶入既有 WBS 與 DSM。"""
    autosave_root = tmp_path / ".birdman_autosave"
    wbs = build_test_wbs(["A1", "A2"])
    dsm = build_test_dsm(["A1", "A2"], [("A1", "A2")])
    wbs_path, dsm_path = write_source_files(tmp_path, wbs, dsm)

    app, editor = launch_editor(
        wbs_df=wbs,
        dsm_df=dsm,
        wbs_path=str(wbs_path),
        dsm_path=str(dsm_path),
        autosave_root=autosave_root,
    )

    assert app is qapp
    assert editor.session.wbsPath == str(wbs_path)
    assert editor.session.dsmPath == str(dsm_path)
    pd.testing.assert_frame_equal(editor.getCurrentDsmDataFrame(), dsm)

    editor.close()


def test_main_window_open_dsm_editor_uses_loaded_wbs_and_dsm(
    tmp_path,
    monkeypatch,
    qapp,
):
    """主 GUI 開啟 DSM 編輯器時，應沿用目前已載入的 WBS/DSM。"""
    captured: dict[str, object] = {}
    monkeypatch.setattr("src.ui.dsm_editor.main_editor.projectRoot", tmp_path)

    def fake_exec(dialog_self):
        captured["wbs_path"] = dialog_self.session.wbsPath
        captured["dsm_path"] = dialog_self.session.dsmPath
        captured["dsm_df"] = dialog_self.getCurrentDsmDataFrame().copy()
        return 0

    monkeypatch.setattr(DsmEditor, "exec_", fake_exec)

    wbs = build_test_wbs(["A1", "A2"])
    dsm = build_test_dsm(["A1", "A2"], [("A1", "A2")])
    wbs_path, dsm_path = write_source_files(tmp_path, wbs, dsm)

    window = BirdmanQtApp()
    window.wbsDf = wbs.copy()
    window.wbsPath = str(wbs_path)
    window.dsmPath = str(dsm_path)

    window.openDsmEditor()

    assert captured["wbs_path"] == str(wbs_path)
    assert captured["dsm_path"] == str(dsm_path)
    pd.testing.assert_frame_equal(captured["dsm_df"], dsm)

    window.close()


def test_main_window_open_dsm_editor_without_loaded_wbs_opens_blank_editor(
    monkeypatch,
    qapp,
):
    """主 GUI 應允許直接開空白 DSM 編輯器。"""
    captured: dict[str, object] = {}

    def fake_exec(dialog_self):
        captured["wbs_df"] = dialog_self.session.wbsDf.copy()
        captured["dsm_df"] = dialog_self.getCurrentDsmDataFrame().copy()
        return 0

    monkeypatch.setattr(DsmEditor, "exec_", fake_exec)

    window = BirdmanQtApp()
    window.openDsmEditor()

    assert captured["wbs_df"].empty is True
    assert list(captured["wbs_df"].columns) == ["Task ID", "Name", "Property"]
    assert captured["dsm_df"].empty is True

    window.close()
