import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.wbs_processor import (  # noqa: E402
    validateIds,
    mergeByScc,
    _extract_year,
)  # noqa: E402
from src.dsm_processor import readDsm, reorderDsm  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


def test_read_dsm_matrix_check(tmp_path):
    path = tmp_path / "dsm.csv"
    # 建立 2x3 非方陣資料
    df = pd.DataFrame(
        [[0, 1, 0], [0, 0, 1]], index=["A", "B"], columns=["A", "B", "C"]
    )
    df.to_csv(path, encoding="utf-8-sig")
    with pytest.raises(ValueError):
        readDsm(path)


def test_validate_ids(tmp_path):
    dsm_path = tmp_path / "dsm.csv"
    df = pd.DataFrame([[0, 1], [0, 0]], index=["A", "B"], columns=["A", "B"])
    df.to_csv(dsm_path)
    dsm = readDsm(dsm_path)

    wbs = pd.DataFrame({"Task ID": ["A", "C"], "TRF": [1, 1]})
    with pytest.raises(ValueError):
        validateIds(wbs, dsm)


def test_validate_trf_negative(tmp_path):
    """檢查 TRF 為負數時是否拋出例外"""
    dsm_path = tmp_path / "dsm.csv"
    df = pd.DataFrame([[0]], index=["A"], columns=["A"])
    df.to_csv(dsm_path)
    dsm = readDsm(dsm_path)

    wbs = pd.DataFrame({"Task ID": ["A"], "TRF": [-1]})
    with pytest.raises(ValueError):
        validateIds(wbs, dsm)


def test_merge_by_scc():
    data = {
        "Task ID": ["A24-001", "A24-002"],
        "TRF": [1, 2],
        "M_expert": [10, 20],
        "Layer": [0, 0],
        "SCC_ID": [0, 0],
    }
    wbs = pd.DataFrame(data)
    merged = mergeByScc(wbs)
    assert len(merged) == 1
    newId = merged.iloc[0]["Task ID"]
    assert newId.startswith("M24-")


def test_reorder_dsm():
    dsm = pd.DataFrame(
        [[0, 1], [0, 0]], index=["A", "B"], columns=["A", "B"]
    )
    order = ["B", "A"]
    reordered = reorderDsm(dsm, order)
    assert list(reordered.index) == order
    assert list(reordered.columns) == order


def test_reorder_dsm_missing_task():
    """當順序缺少任務時應拋出錯誤"""
    dsm = pd.DataFrame([[0, 0], [0, 0]], index=["A", "B"], columns=["A", "B"])
    order = ["A"]
    with pytest.raises(ValueError):
        reorderDsm(dsm, order)


def test_reorder_dsm_extra_task():
    """當順序多出任務時應拋出錯誤"""
    dsm = pd.DataFrame([[0]], index=["A"], columns=["A"])
    order = ["A", "B"]
    with pytest.raises(ValueError):
        reorderDsm(dsm, order)


def test_extract_year_numeric_prefix():
    """Task ID 前綴含數字亦可正確解析年份"""
    assert _extract_year("0X26-001") == "26"


def test_reorder_dsm_duplicate():
    """排序陣列出現重複 Task ID 應拋出錯誤"""
    dsm = pd.DataFrame([[0, 0], [0, 0]], index=["A", "B"], columns=["A", "B"])
    order = ["A", "A"]
    with pytest.raises(ValueError):
        reorderDsm(dsm, order)
