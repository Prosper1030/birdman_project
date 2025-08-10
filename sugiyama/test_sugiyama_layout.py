#!/usr/bin/env python3
"""
測試完整實現的杉山方法階層式佈局
Test Complete Sugiyama Method Implementation
"""

import sys
import os
import pandas as pd
import networkx as nx
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QColor, QPainterPath, QFont

# 假設已經將新的 hierarchical.py 替換到正確位置
# 這裡直接包含核心邏輯用於測試

class TestNode:
    """簡單的測試節點類"""
    def __init__(self, node_id, x, y, scene):
        self.id = node_id
        self.x = x
        self.y = y
        self.width = 100
        self.height = 60
        
        # 創建圖形項目
        self.rect = scene.addRect(
            x - self.width/2, y - self.height/2,
            self.width, self.height,
            QPen(Qt.black, 2),
            QBrush(QColor(255, 215, 0))  # 金黃色
        )
        
        # 添加文字標籤
        self.text = scene.addText(node_id, QFont("Arial", 10))
        self.text.setPos(x - 20, y - 10)
        

class TestEdge:
    """簡單的測試邊類"""
    def __init__(self, src_node, dst_node, scene, is_reversed=False):
        self.src = src_node
        self.dst = dst_node
        
        # 計算連接點
        path = QPainterPath()
        path.moveTo(src_node.x, src_node.y)
        path.lineTo(dst_node.x, dst_node.y)
        
        # 根據是否為反轉邊選擇顏色
        if is_reversed:
            pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)  # 紅色虛線
        else:
            pen = QPen(Qt.black, 2)
        
        self.path_item = scene.addPath(path, pen)
        
        # 添加箭頭
        self._add_arrow(scene, is_reversed)
    
    def _add_arrow(self, scene, is_reversed):
        """添加箭頭"""
        # 簡單的三角形箭頭
        arrow_size = 10
        dx = self.dst.x - self.src.x
        dy = self.dst.y - self.src.y
        
        import math
        angle = math.atan2(dy, dx)
        
        # 箭頭頂點
        tip_x = self.dst.x - (self.dst.width/2 + 5) * math.cos(angle)
        tip_y = self.dst.y - (self.dst.height/2 + 5) * math.sin(angle)
        
        # 箭頭兩側點
        left_x = tip_x - arrow_size * math.cos(angle - math.pi/6)
        left_y = tip_y - arrow_size * math.sin(angle - math.pi/6)
        
        right_x = tip_x - arrow_size * math.cos(angle + math.pi/6)
        right_y = tip_y - arrow_size * math.sin(angle + math.pi/6)
        
        # 創建箭頭路徑
        arrow_path = QPainterPath()
        arrow_path.moveTo(tip_x, tip_y)
        arrow_path.lineTo(left_x, left_y)
        arrow_path.lineTo(right_x, right_y)
        arrow_path.closeSubpath()
        
        # 根據是否反轉選擇顏色
        if is_reversed:
            brush = QBrush(QColor(255, 0, 0))
        else:
            brush = QBrush(Qt.black)
        
        scene.addPath(arrow_path, QPen(Qt.NoPen), brush)


class SugiyamaTestWindow(QMainWindow):
    """測試視窗"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("杉山方法階層式佈局測試")
        self.setGeometry(100, 100, 1200, 800)
        
        # 創建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 創建按鈕列
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)
        
        # 測試案例按鈕
        btn_simple = QPushButton("簡單DAG")
        btn_simple.clicked.connect(self.test_simple_dag)
        button_layout.addWidget(btn_simple)
        
        btn_cycle = QPushButton("含循環圖")
        btn_cycle.clicked.connect(self.test_with_cycle)
        button_layout.addWidget(btn_cycle)
        
        btn_complex = QPushButton("複雜依賴")
        btn_complex.clicked.connect(self.test_complex)
        button_layout.addWidget(btn_complex)
        
        btn_long_edges = QPushButton("跨層邊測試")
        btn_long_edges.clicked.connect(self.test_long_edges)
        button_layout.addWidget(btn_long_edges)
        
        # 創建圖形場景
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-600, -400, 1200, 800)
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.view)
        
        # 預設載入簡單DAG
        self.test_simple_dag()
    
    def clear_scene(self):
        """清空場景"""
        self.scene.clear()
        
    def visualize_layout(self, wbs_df, edges, title=""):
        """視覺化佈局結果"""
        self.clear_scene()
        
        # 添加標題
        title_text = self.scene.addText(title, QFont("Arial", 14, QFont.Bold))
        title_text.setPos(-100, -350)
        
        # 導入新的佈局實現
        from sugiyama_hierarchical_layout import SugiyamaLayout
        
        # 執行佈局
        layout_engine = SugiyamaLayout()
        coordinates = layout_engine.layout(
            wbs_df, edges,
            direction="TB",
            layer_spacing=150,
            node_spacing=120
        )
        
        # 創建節點
        nodes = {}
        for task_id, (x, y) in coordinates.items():
            nodes[task_id] = TestNode(task_id, x, y, self.scene)
        
        # 創建邊（包括標記反轉的邊）
        reversed_edges = layout_engine.reversed_edges
        for src, dst in edges:
            if src in nodes and dst in nodes:
                is_reversed = (src, dst) in reversed_edges
                TestEdge(nodes[src], nodes[dst], self.scene, is_reversed)
        
        # 顯示統計信息
        info_text = f"節點數: {len(coordinates)}\n"
        info_text += f"邊數: {len(edges)}\n"
        info_text += f"層數: {len(set(layout_engine.layers.values()))}\n"
        info_text += f"虛擬節點: {len(layout_engine.virtual_nodes)}\n"
        info_text += f"反轉邊: {len(reversed_edges)}\n"
        info_text += f"交叉數: {layout_engine._count_all_crossings()}"
        
        stats = self.scene.addText(info_text, QFont("Courier", 10))
        stats.setPos(400, -350)
    
    def test_simple_dag(self):
        """測試簡單的DAG"""
        # 創建測試數據
        task_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        wbs_df = pd.DataFrame({'Task ID': task_ids})
        
        # 定義邊（已經是DAG）
        edges = {
            ('A', 'B'), ('A', 'C'),
            ('B', 'D'), ('B', 'E'),
            ('C', 'E'), ('C', 'F'),
            ('D', 'G'),
            ('E', 'G'), ('E', 'H'),
            ('F', 'H')
        }
        
        self.visualize_layout(wbs_df, edges, "簡單DAG測試")
    
    def test_with_cycle(self):
        """測試含循環的圖"""
        # 創建測試數據
        task_ids = ['A', 'B', 'C', 'D', 'E', 'F']
        wbs_df = pd.DataFrame({'Task ID': task_ids})
        
        # 定義邊（包含循環）
        edges = {
            ('A', 'B'), ('B', 'C'), ('C', 'D'),
            ('D', 'B'),  # 循環: B->C->D->B
            ('A', 'E'), ('E', 'F'),
            ('F', 'A'),  # 循環: A->E->F->A
            ('C', 'F')
        }
        
        self.visualize_layout(wbs_df, edges, "含循環圖測試（紅色虛線為反轉邊）")
    
    def test_complex(self):
        """測試複雜依賴關係"""
        # 使用您提供的實際數據的子集
        task_ids = [
            'A26-001', 'A26-002', 'A26-003', 'A26-004',
            'S26-001', 'S26-002', 'S26-003', 'S26-004',
            'D26-001', 'D26-002', 'D26-003', 'D26-004',
            'C26-001', 'C26-002', 'C26-003', 'C26-004'
        ]
        wbs_df = pd.DataFrame({'Task ID': task_ids})
        
        # 定義複雜的依賴關係
        edges = {
            ('A26-001', 'A26-002'), ('A26-001', 'A26-003'),
            ('A26-002', 'A26-004'), ('A26-003', 'A26-004'),
            ('A26-001', 'S26-001'), ('S26-001', 'S26-002'),
            ('S26-002', 'S26-003'), ('S26-003', 'S26-004'),
            ('A26-004', 'D26-001'), ('D26-001', 'D26-002'),
            ('D26-002', 'D26-003'), ('D26-003', 'D26-004'),
            ('S26-004', 'C26-001'), ('C26-001', 'C26-002'),
            ('C26-002', 'C26-003'), ('C26-003', 'C26-004'),
            ('D26-004', 'C26-004'),  # 交叉連接
            ('A26-003', 'C26-001'),  # 長邊
        }
        
        self.visualize_layout(wbs_df, edges, "複雜依賴測試")
    
    def test_long_edges(self):
        """測試跨層邊（需要虛擬節點）"""
        task_ids = ['Start', 'L1-A', 'L1-B', 'L2-A', 'L2-B', 'L3-A', 'L3-B', 'End']
        wbs_df = pd.DataFrame({'Task ID': task_ids})
        
        # 定義包含跨層邊的結構
        edges = {
            ('Start', 'L1-A'), ('Start', 'L1-B'),
            ('L1-A', 'L2-A'), ('L1-B', 'L2-B'),
            ('L2-A', 'L3-A'), ('L2-B', 'L3-B'),
            ('L3-A', 'End'), ('L3-B', 'End'),
            # 跨層邊
            ('Start', 'L3-A'),  # 跨3層
            ('L1-A', 'End'),    # 跨3層
        }
        
        self.visualize_layout(wbs_df, edges, "跨層邊測試（虛擬節點處理）")


def main():
    """主程式"""
    app = QApplication(sys.argv)
    window = SugiyamaTestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # 如果需要單獨測試演算法
    print("=== 杉山方法單元測試 ===")
    
    # 測試簡單案例
    from sugiyama_hierarchical_layout import SugiyamaLayout
    
    # 創建測試數據
    task_ids = ['A', 'B', 'C', 'D', 'E']
    wbs_df = pd.DataFrame({'Task ID': task_ids})
    edges = {('A', 'B'), ('A', 'C'), ('B', 'D'), ('C', 'D'), ('D', 'E')}
    
    # 執行佈局
    layout = SugiyamaLayout()
    coords = layout.layout(wbs_df, edges)
    
    print("\n佈局結果:")
    for node, (x, y) in coords.items():
        layer = layout.layers.get(node, -1)
        print(f"  {node}: Layer {layer}, Position ({x:.1f}, {y:.1f})")
    
    print(f"\n統計:")
    print(f"  總交叉數: {layout._count_all_crossings()}")
    print(f"  虛擬節點數: {len(layout.virtual_nodes)}")
    print(f"  反轉邊數: {len(layout.reversed_edges)}")
    
    # 執行GUI測試
    main()