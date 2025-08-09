from __future__ import annotations
from typing import Dict, List, Tuple
from PyQt5.QtCore import QPointF, QRectF

# 沿用既有邊線繞線引擎
from src.edge_routing import EdgeRoutingEngine


def route_all(nodes: Dict[str, QRectF],
              edges: List[Tuple[str, str]]) -> Dict[Tuple[str, str], List[QPointF]]:
    """
    封裝批次繞線。不得引入 solver/processor 的任何依賴。
    nodes: {node_id: QRectF} 以場景座標為準
    edges: [(src_id, dst_id)]
    回傳：{(src_id, dst_id): [QPointF, ...]}
    """
    engine = EdgeRoutingEngine()
    obstacles = [(rect, nid) for nid, rect in nodes.items()]
    engine.set_obstacles(obstacles)

    def center(r: QRectF) -> QPointF:
        return QPointF(r.center().x(), r.center().y())

    result: Dict[Tuple[str, str], List[QPointF]] = {}
    for (s, d) in edges:
        p0 = center(nodes[s])
        p1 = center(nodes[d])
        path = engine.route_edge(p0, p1)
        points = [QPointF(path.elementAt(i).x, path.elementAt(i).y)
                  for i in range(path.elementCount())]
        result[(s, d)] = points
    return result
