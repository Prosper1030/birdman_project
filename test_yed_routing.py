#!/usr/bin/env python3
"""
yEd 風格正交路由測試程式
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt5.QtCore import QPointF
from src.ui.dsm_editor.edge_router_manager import EdgeRouterManager


def test_yed_routing():
    """測試 yEd 風格正交路由功能"""
    print("=== yEd 風格正交路由測試 ===")
    
    # 建立路由管理器
    manager = EdgeRouterManager()
    
    # 測試 1: 簡單正交路由 (永遠 3 點)
    print("\n1. 測試簡單正交路由:")
    start = QPointF(100, 100)
    end = QPointF(300, 200)
    path = manager._route_simple_orthogonal(start, end)
    
    print(f"   起點: ({start.x()}, {start.y()})")
    print(f"   終點: ({end.x()}, {end.y()})")
    print(f"   路徑: {[(p.x(), p.y()) for p in path]}")
    print(f"   點數: {len(path)} (應該是3)")
    assert len(path) == 3, f"預期3點，實際{len(path)}點"
    
    # 測試 2: 端口側面推斷
    print("\n2. 測試端口側面推斷:")
    
    class MockNode:
        def sceneBoundingRect(self):
            from PyQt5.QtCore import QRectF
            return QRectF(150, 150, 100, 50)
    
    node = MockNode()
    left_port = QPointF(150, 175)  # 左側
    right_port = QPointF(250, 175)  # 右側
    top_port = QPointF(200, 150)   # 頂部
    bottom_port = QPointF(200, 200) # 底部
    
    assert manager._infer_port_side(node, left_port) == 'left'
    assert manager._infer_port_side(node, right_port) == 'right'
    assert manager._infer_port_side(node, top_port) == 'top'
    assert manager._infer_port_side(node, bottom_port) == 'bottom'
    print("   端口側面推斷: 通過")
    
    # 測試 3: Stub 點生成
    print("\n3. 測試 Stub 點生成:")
    stub_len = 16
    port = QPointF(200, 200)
    
    left_stub = manager._make_stub_point(port, 'left', stub_len)
    right_stub = manager._make_stub_point(port, 'right', stub_len)
    top_stub = manager._make_stub_point(port, 'top', stub_len)
    bottom_stub = manager._make_stub_point(port, 'bottom', stub_len)
    
    expected = [
        (184, 200),  # left: x - 16
        (216, 200),  # right: x + 16
        (200, 184),  # top: y - 16
        (200, 216),  # bottom: y + 16
    ]
    
    actual = [
        (left_stub.x(), left_stub.y()),
        (right_stub.x(), right_stub.y()),
        (top_stub.x(), top_stub.y()),
        (bottom_stub.x(), bottom_stub.y()),
    ]
    
    for i, (exp, act) in enumerate(zip(expected, actual)):
        assert exp == act, f"Stub {i}: 預期{exp}, 實際{act}"
    
    print("   Stub 點生成: 通過")
    
    # 測試 4: Manhattan 強制化
    print("\n4. 測試 Manhattan 強制化:")
    
    # 測試對角線轉正交
    diagonal_points = [QPointF(0, 0), QPointF(100, 100)]
    ortho_points = manager._ensure_manhattan(diagonal_points, prefer='TB')
    print(f"   對角線 -> 正交: {[(p.x(), p.y()) for p in ortho_points]}")
    assert len(ortho_points) == 3, "對角線應轉為3點路徑"
    
    # 測試 always_elbow 功能
    straight_points = [QPointF(0, 0), QPointF(100, 0)]  # 水平直線
    elbow_points = manager._ensure_manhattan(straight_points, always_elbow=True)
    print(f"   直線 -> 強制轉角: {[(p.x(), p.y()) for p in elbow_points]}")
    assert len(elbow_points) == 3, "直線應強制加入轉角變3點"
    
    print("   Manhattan 強制化: 通過")
    
    print("\n=== 所有測試通過！===")
    print("yEd 風格正交路由系統已準備就緒")


if __name__ == "__main__":
    test_yed_routing()