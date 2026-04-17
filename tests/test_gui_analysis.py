import pandas as pd

from src.gui_qt import BirdmanQtApp


def test_run_full_analysis_updates_gantt_without_name_error(tmp_path, qapp):
    """完整分析後更新甘特圖不應因舊變數名而崩潰。"""
    wbs_path = tmp_path / "wbs.csv"
    dsm_path = tmp_path / "dsm.csv"

    wbs_df = pd.DataFrame(
        {
            "Task ID": ["A26-001", "A26-002"],
            "Name": ["需求", "開發"],
            "TRF": [1, 2],
            "O_expert": [1, 2],
            "M_expert": [2, 3],
            "P_expert": [3, 4],
            "Te_expert": [2, 3],
            "O_newbie": [2, 3],
            "M_newbie": [3, 4],
            "P_newbie": [4, 5],
            "Te_newbie": [3, 4],
        }
    )
    dsm_df = pd.DataFrame(
        [[0, 0], [1, 0]],
        index=["A26-001", "A26-002"],
        columns=["A26-001", "A26-002"],
    )

    wbs_df.to_csv(wbs_path, index=False, encoding="utf-8-sig")
    dsm_df.to_csv(dsm_path, encoding="utf-8-sig")

    gui = BirdmanQtApp()
    gui.wbsPath = str(wbs_path)
    gui.dsmPath = str(dsm_path)

    gui.run_full_analysis()

    assert gui.cmpResult is not None
    assert gui.ganttCanvas is not None
    assert gui.total_hours_label.text().startswith("總工時：")
