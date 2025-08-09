#!/usr/bin/env python3
"""
階層式佈局演算法測試
Hierarchical Layout Algorithm Tests

測試 layout_hierarchical 函數的基本功能和穩定性。
"""

import sys
import os
import unittest
import math
from typing import Dict, Tuple, Set

# 將 src 目錄加入 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pandas as pd
from layouts.hierarchical import (
    layout_hierarchical,
    _compute_layers_longest_path,
    _simple_grid_layout,
    _simple_hierarchical_fallback
)


class TestHierarchicalLayout(unittest.TestCase):
    """階層式佈局測試類別。"""
    
    def setUp(self):
        """設定測試環境。"""
        # 建立簡單的測試 WBS
        self.simple_wbs = pd.DataFrame({
            'Task ID': ['A', 'B', 'C', 'D'],
            'Name': ['Task A', 'Task B', 'Task C', 'Task D']
        })
        
        # 建立較複雜的測試 WBS
        self.complex_wbs = pd.DataFrame({
            'Task ID': [f'T{i:02d}' for i in range(10)],
            'Name': [f'Task {i}' for i in range(10)]
        })
        
        # 簡單的依賴關係（無循環）
        self.simple_edges = {
            ('A', 'B'),  # A -> B
            ('A', 'C'),  # A -> C
            ('B', 'D'),  # B -> D
            ('C', 'D'),  # C -> D
        }
        
        # 複雜的依賴關係（無循環）
        self.complex_edges = {
            ('T00', 'T01'),
            ('T00', 'T02'),
            ('T01', 'T03'),
            ('T02', 'T03'),
            ('T03', 'T04'),
            ('T03', 'T05'),
            ('T04', 'T06'),
            ('T05', 'T06'),
        }
        
        # 有循環的依賴關係
        self.cyclic_edges = {
            ('A', 'B'),
            ('B', 'C'),
            ('C', 'A'),  # 形成循環
        }
    
    def test_basic_functionality(self):
        """測試基本功能。"""
        # 測試無邊的情況
        positions = layout_hierarchical(self.simple_wbs)
        self.assertIsInstance(positions, dict)
        self.assertEqual(len(positions), 4)
        
        # 檢查所有任務都有位置
        for task_id in ['A', 'B', 'C', 'D']:
            self.assertIn(task_id, positions)
            pos = positions[task_id]
            self.assertIsInstance(pos, tuple)
            self.assertEqual(len(pos), 2)
            self.assertIsInstance(pos[0], (int, float))
            self.assertIsInstance(pos[1], (int, float))
    
    def test_with_edges(self):
        """測試有依賴關係的情況。"""
        positions = layout_hierarchical(self.simple_wbs, self.simple_edges)
        
        # 檢查層級關係
        # A 應該在最上層（y=0）
        # B 和 C 應該在第二層
        # D 應該在最下層
        
        self.assertEqual(positions['A'][1], 0)  # A 在第 0 層
        self.assertEqual(positions['B'][1], positions['C'][1])  # B 和 C 同層
        self.assertTrue(positions['D'][1] > positions['B'][1])  # D 在 B 下方
    
    def test_deterministic_layout(self):
        """測試佈局的確定性（重複執行結果相同）。"""
        # 執行兩次佈局
        positions1 = layout_hierarchical(self.complex_wbs, self.complex_edges)
        positions2 = layout_hierarchical(self.complex_wbs, self.complex_edges)
        
        # 計算 RMS 位移
        rms_displacement = self._calculate_rms_displacement(positions1, positions2)
        
        # RMS 位移應該非常小（< 1e-6）
        self.assertLess(rms_displacement, 1e-6, 
                       f"佈局不確定：RMS 位移 = {rms_displacement}")
    
    def test_cyclic_graph_fallback(self):
        """測試循環圖的備用方案。"""
        # 不應該拋出異常
        positions = layout_hierarchical(self.simple_wbs, self.cyclic_edges)
        
        # 應該返回有效的位置
        self.assertEqual(len(positions), 4)
        for task_id in ['A', 'B', 'C', 'D']:
            self.assertIn(task_id, positions)
    
    def test_direction_parameter(self):
        """測試佈局方向參數。"""
        # TB 方向
        positions_tb = layout_hierarchical(
            self.simple_wbs, 
            self.simple_edges,
            direction='TB'
        )
        
        # LR 方向
        positions_lr = layout_hierarchical(
            self.simple_wbs,
            self.simple_edges, 
            direction='LR'
        )
        
        # TB：垂直排列，x 變化較小，y 變化較大
        # LR：水平排列，x 變化較大，y 變化較小
        
        y_range_tb = self._get_range([p[1] for p in positions_tb.values()])
        x_range_lr = self._get_range([p[0] for p in positions_lr.values()])
        
        self.assertGreater(y_range_tb, 0)
        self.assertGreater(x_range_lr, 0)
    
    def test_spacing_parameters(self):
        """測試間距參數。"""
        # 預設間距
        positions1 = layout_hierarchical(
            self.simple_wbs,
            self.simple_edges
        )
        
        # 較大間距
        positions2 = layout_hierarchical(
            self.simple_wbs,
            self.simple_edges,
            layer_spacing=400,
            node_spacing=300
        )
        
        # 較大間距應該產生更分散的佈局
        bbox1 = self._get_bounding_box(positions1)
        bbox2 = self._get_bounding_box(positions2)
        
        area1 = bbox1[0] * bbox1[1]
        area2 = bbox2[0] * bbox2[1]
        
        self.assertGreater(area2, area1)
    
    def test_empty_wbs(self):
        """測試空 WBS 的情況。"""
        empty_wbs = pd.DataFrame()
        positions = layout_hierarchical(empty_wbs)
        
        self.assertIsInstance(positions, dict)
        self.assertEqual(len(positions), 0)
    
    def test_single_node(self):
        """測試單一節點的情況。"""
        single_wbs = pd.DataFrame({
            'Task ID': ['SINGLE'],
            'Name': ['Single Task']
        })
        
        positions = layout_hierarchical(single_wbs)
        
        self.assertEqual(len(positions), 1)
        self.assertIn('SINGLE', positions)
    
    def test_isolated_nodes(self):
        """測試有孤立節點的情況。"""
        # T09 沒有任何連線
        positions = layout_hierarchical(self.complex_wbs, self.complex_edges)
        
        # 所有節點都應該有位置，包括孤立節點
        self.assertEqual(len(positions), 10)
        self.assertIn('T09', positions)  # 孤立節點
        self.assertIn('T07', positions)  # 孤立節點
        self.assertIn('T08', positions)  # 孤立節點
    
    def _calculate_rms_displacement(self, 
                                   positions1: Dict[str, Tuple[float, float]],
                                   positions2: Dict[str, Tuple[float, float]]) -> float:
        """
        計算兩個佈局之間的 RMS 位移。
        
        Args:
            positions1: 第一個佈局
            positions2: 第二個佈局
        
        Returns:
            RMS 位移值
        """
        if not positions1 or not positions2:
            return 0.0
        
        total_sq_displacement = 0.0
        count = 0
        
        for task_id in positions1:
            if task_id in positions2:
                p1 = positions1[task_id]
                p2 = positions2[task_id]
                dx = p1[0] - p2[0]
                dy = p1[1] - p2[1]
                total_sq_displacement += dx*dx + dy*dy
                count += 1
        
        if count == 0:
            return 0.0
        
        return math.sqrt(total_sq_displacement / count)
    
    def _get_range(self, values: list) -> float:
        """計算值的範圍。"""
        if not values:
            return 0.0
        return max(values) - min(values)
    
    def _get_bounding_box(self, positions: Dict[str, Tuple[float, float]]) -> Tuple[float, float]:
        """
        計算佈局的邊界框。
        
        Args:
            positions: 節點位置字典
        
        Returns:
            (寬度, 高度)
        """
        if not positions:
            return (0, 0)
        
        x_coords = [p[0] for p in positions.values()]
        y_coords = [p[1] for p in positions.values()]
        
        width = max(x_coords) - min(x_coords)
        height = max(y_coords) - min(y_coords)
        
        return (width, height)


class TestHelperFunctions(unittest.TestCase):
    """測試輔助函數。"""
    
    def test_simple_grid_layout(self):
        """測試簡單網格佈局。"""
        task_ids = ['A', 'B', 'C', 'D', 'E', 'F']
        
        positions = _simple_grid_layout(task_ids, 100, 150, 'TB')
        
        self.assertEqual(len(positions), 6)
        
        # 檢查網格排列（5 個一行）
        self.assertEqual(positions['A'][1], positions['B'][1])  # 同一行
        self.assertEqual(positions['F'][1], 150)  # 第二行
    
    def test_simple_hierarchical_fallback(self):
        """測試簡單階層備用方案。"""
        task_ids = ['A', 'B', 'C', 'D', 'E']
        edges = {('A', 'B'), ('B', 'C')}  # 不重要，因為是備用方案
        
        positions = _simple_hierarchical_fallback(
            task_ids, edges, 200, 150, 'TB'
        )
        
        self.assertEqual(len(positions), 5)
        
        # 檢查分層（4 個一層）
        self.assertEqual(positions['A'][1], positions['B'][1])  # 同層
        self.assertEqual(positions['E'][1], 200)  # 第二層


def run_tests():
    """執行所有測試。"""
    # 建立測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 加入測試類別
    suite.addTests(loader.loadTestsFromTestCase(TestHierarchicalLayout))
    suite.addTests(loader.loadTestsFromTestCase(TestHelperFunctions))
    
    # 執行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回是否成功
    return result.wasSuccessful()


if __name__ == '__main__':
    # 執行測試
    success = run_tests()
    sys.exit(0 if success else 1)