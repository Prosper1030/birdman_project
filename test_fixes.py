#!/usr/bin/env python3
"""
測試所有修復的功能
"""

import sys
import os
sys.path.insert(0, '.')

def test_components_import():
    """測試組件導入"""
    print("測試 1: 組件導入...")
    try:
        from src.layout.yed_layout_engine import YEdLayoutEngine, LayoutStyle
        from src.layout.animated_layout import LayoutAnimator
        from src.routing.enhanced_edge_item import EnhancedEdgeItem, RoutingStyle
        from src.routing.engine import RoutingEngine
        print("✓ 所有組件成功導入")
        return True
    except Exception as e:
        print(f"✗ 導入失敗: {e}")
        return False

def test_routing_engine():
    """測試路由引擎初始化"""
    print("測試 2: 路由引擎...")
    try:
        from PyQt5.QtCore import QRectF
        from src.routing.enhanced_edge_item import EnhancedEdgeItem
        
        # 初始化路由引擎
        scene_rect = QRectF(-1000, -1000, 2000, 2000)
        EnhancedEdgeItem.initialize_router(scene_rect)
        
        if EnhancedEdgeItem._router:
            print("✓ 路由引擎初始化成功")
            return True
        else:
            print("✗ 路由引擎返回 None")
            return False
    except Exception as e:
        print(f"✗ 路由引擎測試失敗: {e}")
        return False

def test_connection_point():
    """測試連接點方法"""
    print("測試 3: 連接點計算...")
    try:
        from PyQt5.QtCore import QRectF, QPointF
        from src.routing.enhanced_edge_item import EnhancedEdgeItem
        
        # 創建虛擬節點
        class MockNode:
            def sceneBoundingRect(self):
                return QRectF(0, 0, 100, 50)
        
        src_node = MockNode()
        dst_node = MockNode()
        
        # 創建增強邊線
        edge = EnhancedEdgeItem(src_node, dst_node)
        
        # 測試 getConnectionPoint 方法
        rect = QRectF(0, 0, 100, 50)
        target_point = QPointF(200, 100)
        connection_point = edge.getConnectionPoint(rect, target_point)
        
        print(f"✓ 連接點計算成功: {connection_point}")
        return True
    except Exception as e:
        print(f"✗ 連接點測試失敗: {e}")
        return False

def test_arrow_head():
    """測試箭頭顯示"""
    print("測試 4: 箭頭組件...")
    try:
        from PyQt5.QtCore import QPointF
        from src.routing.enhanced_edge_item import GlowArrowHead, EnhancedEdgeItem
        
        # 創建虛擬邊線
        class MockEdge:
            def isSelected(self):
                return False
        
        edge = MockEdge()
        arrow = GlowArrowHead(edge)
        
        # 測試箭頭位置更新
        end_point = QPointF(100, 100)
        direction = (1.0, 0.0)
        arrow.updatePosition(end_point, direction)
        
        print("✓ 箭頭組件測試成功")
        return True
    except Exception as e:
        print(f"✗ 箭頭測試失敗: {e}")
        return False

def test_layout_engines():
    """測試布局引擎"""
    print("測試 5: 布局引擎...")
    try:
        from src.layout.yed_layout_engine import YEdLayoutEngine
        from src.layout.animated_layout import LayoutAnimator
        
        # 創建引擎
        layout_engine = YEdLayoutEngine()
        animator = LayoutAnimator()
        
        print("✓ 布局引擎創建成功")
        return True
    except Exception as e:
        print(f"✗ 布局引擎測試失敗: {e}")
        return False

def main():
    """主測試程序"""
    print("開始測試 YED_LAYOUT_ISSUES.md 中的修復...")
    print("=" * 50)
    
    tests = [
        test_components_import,
        test_routing_engine,
        test_connection_point,
        test_arrow_head,
        test_layout_engines
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 測試執行錯誤: {e}")
    
    print("=" * 50)
    print(f"測試完成: {passed}/{total} 通過")
    
    if passed == total:
        print("✓ 所有修復都已成功完成！")
    else:
        print("✗ 部分測試失敗，需要進一步檢查")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)