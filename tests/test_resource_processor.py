import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.resource_processor import readResources  # noqa: E402


def test_read_resources_capacity(tmp_path):
    """測試依照 Headcount_Cap 或 Hr_Per_Week 計算容量"""
    wbs = pd.DataFrame({"Task ID": ["T1", "T2", "T3"], "Te_newbie": [10, 20, 30]})
    resources = pd.DataFrame(
        {
            "Group": ["G1", "G2", "G3"],
            "Headcount_Cap": [2, None, None],
            "Hr_Per_Week": [None, 40, 5],
        }
    )
    resPath = tmp_path / "Resources.csv"
    resources.to_csv(resPath, index=False, encoding="utf-8-sig")
    cap = readResources(str(resPath), wbs)
    assert cap == {"G1": 2, "G2": 2, "G3": 1}
