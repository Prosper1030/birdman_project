from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    from PyQt5.QtCore import QPointF  # type: ignore
except Exception:
    class QPointF:  # type: ignore
        def __init__(self, x: float = 0.0, y: float = 0.0):
            self._x = float(x)
            self._y = float(y)
        def x(self) -> float:
            return self._x
        def y(self) -> float:
            return self._y


@dataclass(frozen=True)
class DrawEdge:
    """繪製/排程層的獨立 stroke（方向唯一）。
    - draw_id 穩定且唯一（此處以 "src->dst" 生成；若未來允許多重平行邊，再附加序號即可）。
    - item 指向對應的 EdgeItem（可選，但在 GUI 套用路徑時需要）。
    """
    draw_id: str
    src_id: str
    dst_id: str
    ps: QPointF
    pt: QPointF
    item: Optional[object] = None  # EdgeItem


def make_draw_id(src_id: str, dst_id: str) -> str:
    return f"{src_id}->{dst_id}"


def expand_to_draw_edges(edge_records: List[Tuple[object, QPointF, QPointF]]) -> List[DrawEdge]:
    """將資料層記錄展開為 DrawEdge 清單。
    目前 UI 已以單向 EdgeItem 呈現，因此 edge_records 事實上已是單向；
    這個轉換層主要負責產生穩定 draw_id 並包裝成 DrawEdge。

    Args:
        edge_records: list of (edge_item, ps, pt)
    Returns:
        list of DrawEdge
    """
    out: List[DrawEdge] = []
    for edge_item, ps, pt in edge_records:
        src_id = getattr(getattr(edge_item, 'src', None), 'taskId', 'unknown')
        dst_id = getattr(getattr(edge_item, 'dst', None), 'taskId', 'unknown')
        out.append(DrawEdge(
            draw_id=make_draw_id(str(src_id), str(dst_id)),
            src_id=str(src_id),
            dst_id=str(dst_id),
            ps=ps,
            pt=pt,
            item=edge_item,
        ))
    return out
