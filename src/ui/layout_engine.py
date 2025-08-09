from __future__ import annotations
from typing import Dict, Tuple, Set
import pandas as pd

# 佈局演算法：沿用現有實作，不改對外位置
from src.layouts.hierarchical import layout_hierarchical

# 統一回傳介面：positions = {task_id: (x, y)}
def apply_hierarchical(wbs_df: pd.DataFrame,
                       edges: Set[Tuple[str, str]],
                       grid: int = 10) -> Dict[str, Tuple[float, float]]:
    """
    統一封裝分層佈局。不得改動外部欄位與資料結構。
    """
    # 現有實作尚未支援網格參數，因此暫忽略 grid 值
    return layout_hierarchical(wbs_df, edges)


def apply_force_directed(*args, **kwargs):
    """預留介面，尚未接入。"""
    raise NotImplementedError
