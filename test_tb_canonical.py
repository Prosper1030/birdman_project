#!/usr/bin/env python3
"""
TB 版面規範路由測試程式
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt5.QtCore import QPointF, QRectF
from src.ui.dsm_editor.edge_router_manager import EdgeRouterManager, GRID, PORT_STUB, CLEAR


class MockNode:
    def __init__(self, x, y, w, h):
        self.rect = QRectF(x, y, w, h)
    
    def sceneBoundingRect(self):
        return self.rect


class MockEdge:
    def __init__(self, src_node, dst_node):
        self.src = src_node
        self.dst = dst_node


def test_tb_canonical():
    """測試 TB 版面規範路由"""
    print("=== TB 版面規範路由測試 ===")
    
    manager = EdgeRouterManager()
    
    # 測試節點
    src_node = MockNode(100, 50, 80, 40)   # 上方節點
    dst_node = MockNode(200, 150, 80, 40)  # 下方節點
    
    edge_item = MockEdge(src_node, dst_node)
    
    print(f"常數: GRID={GRID}, PORT_STUB={PORT_STUB}, CLEAR={CLEAR}")
    
    # 測試 1: 同軸例外（x 相同，允許直線）
    print("\n1. 測試同軸例外（x 相同）:")
    ps1 = QPointF(150, 90)   # 起點
    pt1 = QPointF(150, 190)  # 終點（相同 x）
    path1 = manager._route_tb_canonical(edge_item, ps1, pt1)
    print(f"   起點: ({ps1.x()}, {ps1.y()})")
    print(f"   終點: ({pt1.x()}, {pt1.y()})")
    print(f"   路徑: {[(p.x(), p.y()) for p in path1]}")
    print(f"   點數: {len(path1)} (應該是2)")
    assert len(path1) == 2, f"同軸應為2點，實際{len(path1)}點"
    
    # 測試 2: 不同 x，完整 TB 路由
    print("\n2. 測試完整 TB 路由（不同 x）:")
    ps2 = QPointF(140, 90)   # 起點（src 節點底部中心）
    pt2 = QPointF(240, 150)  # 終點（dst 節點頂部中心）
    path2 = manager._route_tb_canonical(edge_item, ps2, pt2)
    print(f"   起點: ({ps2.x()}, {ps2.y()})")
    print(f"   終點: ({pt2.x()}, {pt2.y()})")
    print(f"   路徑: {[(p.x(), p.y()) for p in path2]}")
    print(f"   點數: {len(path2)} (應該是6: ps→s_out→mid1→mid2→t_in→pt)")
    
    # 驗證路徑結構
    assert len(path2) == 6, f"TB路由應為6點，實際{len(path2)}點"
    
    # 驗證 stub 長度
    s_out = path2[1]
    t_in = path2[-2]
    stub_len_s = abs(s_out.y() - ps2.y())
    stub_len_t = abs(t_in.y() - pt2.y())
    print(f"   源 stub 長度: {stub_len_s} (應為 {PORT_STUB})")
    print(f"   目標 stub 長度: {stub_len_t} (應為 {PORT_STUB})")
    
    # 驗證末段垂直（最後兩點 x 相同）
    assert abs(path2[-2].x() - path2[-1].x()) < 0.1, "末段必須垂直"
    print("   ✓ 末段垂直檢查通過")
    
    # 驗證路徑完全正交
    for i in range(len(path2) - 1):
        p1, p2 = path2[i], path2[i + 1]
        is_orthogonal = (abs(p1.x() - p2.x()) < 0.1) or (abs(p1.y() - p2.y()) < 0.1)
        assert is_orthogonal, f"路徑段 {i}-{i+1} 非正交: ({p1.x()},{p1.y()}) -> ({p2.x()},{p2.y()})"
    print("   ✓ 完全正交檢查通過")
    
    # 測試 3: 工具函式
    print("\n3. 測試工具函式:")
    
    # _snap 對齊測試
    assert manager._snap(23) == 16, "_snap(23) 應為 16"
    assert manager._snap(25) == 32, "_snap(25) 應為 32"
    print("   ✓ _snap 對齊功能正確")
    
    # _port_side 測試
    node = MockNode(100, 100, 100, 50)
    assert manager._port_side(node, QPointF(100, 125)) == 'left'   # 左側
    assert manager._port_side(node, QPointF(200, 125)) == 'right'  # 右側
    assert manager._port_side(node, QPointF(150, 100)) == 'top'    # 頂部
    assert manager._port_side(node, QPointF(150, 150)) == 'bottom' # 底部
    print("   ✓ _port_side 推斷正確")
    
    # _stub 測試
    port = QPointF(150, 125)
    stub_left = manager._stub(port, 'left', PORT_STUB)
    stub_right = manager._stub(port, 'right', PORT_STUB)
    stub_top = manager._stub(port, 'top', PORT_STUB)
    stub_bottom = manager._stub(port, 'bottom', PORT_STUB)
    
    assert stub_left.x() == 150 - PORT_STUB and stub_left.y() == 125
    assert stub_right.x() == 150 + PORT_STUB and stub_right.y() == 125
    assert stub_top.x() == 150 and stub_top.y() == 125 - PORT_STUB
    assert stub_bottom.x() == 150 and stub_bottom.y() == 125 + PORT_STUB
    print("   ✓ _stub 點生成正確")
    
    print("\n=== 所有 TB 版面規範測試通過！===")
    print("TB 版面規範路由系統已準備就緒")


def test_integration():
    """整合測試：完整路由流程"""
    print("\n=== 整合測試：完整路由流程 ===")
    
    manager = EdgeRouterManager()
    
    # 模擬 DSM 編輯器中的實際場景
    src_node = MockNode(50, 50, 100, 60)    # A 節點
    dst_node = MockNode(300, 200, 100, 60)  # B 節點
    
    edge_item = MockEdge(src_node, dst_node)
    
    start_pos = QPointF(150, 110)  # A 節點右邊中心
    end_pos = QPointF(350, 200)    # B 節點頂部中心（讓 TB 版面末段垂直）
    
    # 先測試 _route_tb_canonical 的輸出
    canonical_path = manager._route_tb_canonical(edge_item, start_pos, end_pos)
    print(f"TB 規範路徑:")
    print(f"  路徑: {[(p.x(), p.y()) for p in canonical_path]}")
    print(f"  點數: {len(canonical_path)}")
    
    # 使用完整的 _route_orthogonal_safe 路由（明確傳遞空障礙物列表）
    path = manager._route_orthogonal_safe(edge_item, start_pos, end_pos, obstacles=[])
    
    print(f"完整路由結果:")
    print(f"  起點: ({start_pos.x()}, {start_pos.y()})")
    print(f"  終點: ({end_pos.x()}, {end_pos.y()})")
    print(f"  路徑: {[(p.x(), p.y()) for p in path]}")
    print(f"  點數: {len(path)}")
    
    # 驗證路徑基本要求
    assert len(path) >= 2, "路徑至少應有2點"
    assert path[0] == start_pos, "第一點應為起點"
    assert path[-1] == end_pos, "最後點應為終點"
    
    # 驗證末段垂直
    if len(path) >= 2:
        assert abs(path[-2].x() - path[-1].x()) < 0.1, "末段必須垂直"
    
    # 驗證完全正交
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i + 1]
        is_orthogonal = (abs(p1.x() - p2.x()) < 0.1) or (abs(p1.y() - p2.y()) < 0.1)
        assert is_orthogonal, f"路徑段 {i}-{i+1} 非正交"
    
    print("  ✓ 整合測試通過")


if __name__ == "__main__":
    test_tb_canonical()
    test_integration()