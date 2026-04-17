from PyQt5.QtCore import QPointF, QRectF

from src.ui.dsm_editor.advanced_routing import (
    AStarPathfinder,
    AdvancedEdgeRouter,
    EdgeRouteRequest,
    RoutingNode,
    VisibilityGraph,
)
from src.ui.dsm_editor.edge_router_manager import EdgeRouterManager


def test_astar_prefers_less_congested_detour():
    """擁塞成本應能把路徑推往較空的替代走廊。"""
    graph = VisibilityGraph(grid_pitch=10)
    start = RoutingNode(0, 0, "start")
    straight = RoutingNode(10, 0, "straight")
    goal = RoutingNode(20, 0, "goal")
    upper_left = RoutingNode(0, 10, "upper_left")
    upper_right = RoutingNode(20, 10, "upper_right")

    for node in [start, straight, goal, upper_left, upper_right]:
        graph.add_node(node)

    for node1, node2 in [
        (start, straight),
        (straight, goal),
        (start, upper_left),
        (upper_left, upper_right),
        (upper_right, goal),
    ]:
        cost = abs(node2.x - node1.x) + abs(node2.y - node1.y)
        graph._add_edge(node1, node2, cost)
        graph._add_edge(node2, node1, cost)

    pathfinder = AStarPathfinder(graph)
    occupancy = {
        graph.make_segment_key(start, straight): 3,
        graph.make_segment_key(straight, goal): 3,
    }

    path = pathfinder.find_path(
        start,
        goal,
        occupancy=occupancy,
        bend_penalty=0.0,
        congestion_weight=30.0,
        stability_weight=0.0,
    )

    assert [(node.x, node.y) for node in path] == [
        (0, 0),
        (0, 10),
        (20, 10),
        (20, 0),
    ]


def test_route_edges_commits_occupancy_for_later_requests(monkeypatch):
    """批次路由應把前面已提交的路徑 load 傳給後續邊。"""
    router = AdvancedEdgeRouter()
    seen_occupancy = []

    def fake_route_edge(
        start_pos,
        end_pos,
        obstacles=None,
        occupancy=None,
        previous_path=None,
    ):
        seen_occupancy.append(dict(occupancy or {}))
        return [start_pos, end_pos]

    monkeypatch.setattr(router, "route_edge", fake_route_edge)

    requests = [
        EdgeRouteRequest("edge-1", QPointF(0, 0), QPointF(20, 0), []),
        EdgeRouteRequest("edge-2", QPointF(0, 20), QPointF(20, 20), []),
    ]

    router.route_edges(requests)

    assert seen_occupancy[0] == {}
    assert len(seen_occupancy[1]) == 1


def test_edge_router_manager_uses_batch_router_for_layout(monkeypatch, qapp):
    """layout 路由流程應把非垂直邊交給批次高級路由器。"""

    class MockNode:
        def __init__(self, task_id: str):
            self.taskId = task_id

    class MockEdge:
        def __init__(self, src_id: str, dst_id: str):
            self.src = MockNode(src_id)
            self.dst = MockNode(dst_id)
            self.applied_paths = []

        def set_complex_path(self, path_points, offset_pixels=0):
            self.applied_paths.append((path_points, offset_pixels))

    class FakeBatchRouter:
        def __init__(self):
            self.requests = None

        def route_edges(self, requests):
            self.requests = requests
            return {
                request.edgeKey: [
                    request.startPos,
                    QPointF(request.startPos.x(), request.endPos.y()),
                    request.endPos,
                ]
                for request in requests
            }

    manager = EdgeRouterManager()
    manager.set_band_router_enabled(False)
    fake_router = FakeBatchRouter()
    manager.set_orthogonal_router(fake_router)

    monkeypatch.setattr(
        manager,
        "_collect_obstacles",
        lambda edge_item, roi_rect=None: [QRectF(40, 40, 20, 20)],
    )

    edge_item = MockEdge("A1", "A2")
    routed = manager.route_all_edges_for_layout(
        [(edge_item, QPointF(0, 0), QPointF(100, 100))]
    )

    assert fake_router.requests is not None
    assert len(fake_router.requests) == 1
    assert fake_router.requests[0].edgeKey == ("A1", "A2")
    assert ("A1", "A2") in routed
    assert edge_item.applied_paths
