from __future__ import annotations
from typing import Dict, List, Tuple
from PyQt5.QtCore import QPointF, QRectF

# 沿用既有邊線繞線引擎
from src.edge_routing import EdgeRoutingEngine


def route_all(nodes: Dict[str, QRectF],
              edges: List[Tuple[str, str]]) -> Dict[Tuple[str, str], List[QPointF]]:
    """批次路由所有邊線。"""
    engine = EdgeRoutingEngine()
    # 若引擎需要障礙資料，嘗試設定；若失敗則忽略
    try:
        obstacles = [(rect, nid) for nid, rect in nodes.items()]
        engine.set_obstacles(obstacles)
    except Exception:
        pass

    def center(r: QRectF) -> QPointF:
        return QPointF(r.center().x(), r.center().y())

    result: Dict[Tuple[str, str], List[QPointF]] = {}
    for (s, d) in edges:
        p0 = center(nodes[s])
        p1 = center(nodes[d])
        path = engine.route_edge(p0, p1)
        points: List[QPointF] = []
        # 可能回傳 QPainterPath 或點列，統一轉成點列表
        try:
            for i in range(path.elementCount()):
                e = path.elementAt(i)
                points.append(QPointF(e.x, e.y))
        except Exception:
            points = list(path)
        result[(s, d)] = points
    return result
