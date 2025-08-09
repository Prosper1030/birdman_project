#!/usr/bin/env python3
"""
yEd Edge Routing 系統 - 完整演示應用程式
展示所有路由功能的互動式應用
"""

import sys
import json
import random
from typing import List, Dict, Optional

from PyQt5.QtCore import (
    Qt, QPointF, QRectF, QTimer, pyqtSignal, QObject
)
from PyQt5.QtGui import (
    QPen, QBrush, QColor, QPainter, QFont, QPainterPath
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QComboBox,
    QSlider, QLabel, QGroupBox, QCheckBox, QSpinBox,
    QTextEdit, QSplitter, QMenuBar, QMenu, QAction,
    QFileDialog, QMessageBox, QDockWidget, QListWidget,
    QTableWidget, QTableWidgetItem, QHeaderView
)

# 假設已經導入 yed_edge_routing 模組
# from yed_edge_routing import *


class DemoTaskNode(QGraphicsRectItem):
    """演示用的任務節點"""
    
    def __init__(self, task_id: str, title: str = ""):
        super().__init__(0, 0, 120, 60)
        
        self.taskId = task_id
        self.title = title or task_id
        
        # 樣式設定
        self.setBrush(QBrush(QColor(200, 220, 255)))
        self.setPen(QPen(QColor(100, 100, 150), 2))
        
        # 標籤
        self.label = QGraphicsTextItem(self.title, self)
        self.label.setPos(10, 20)
        font = QFont("Arial", 10)
        self.label.setFont(font)
        
        # 互動設定
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # 連接的邊線
        self.edges = []
        
    def add_edge(self, edge):
        """添加連接的邊線"""
        self.edges.append(edge)
        
    def remove_edge(self, edge):
        """移除連接的邊線"""
        if edge in self.edges:
            self.edges.remove(edge)
            
    def itemChange(self, change, value):
        """處理項目變更"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            # 更新所有連接的邊線
            for edge in self.edges:
                edge.invalidateRoute()
                edge.updatePath()
        
        return super().itemChange(change, value)
        
    def set_highlight(self, highlight: bool):
        """設定高亮狀態"""
        if highlight:
            self.setBrush(QBrush(QColor(255, 220, 100)))
            self.setPen(QPen(QColor(200, 150, 0), 3))
        else:
            self.setBrush(QBrush(QColor(200, 220, 255)))
            self.setPen(QPen(QColor(100, 100, 150), 2))


class DemoGraphWidget(QGraphicsView):
    """主圖形視圖"""
    
    # 信號
    node_selected = pyqtSignal(str)
    edge_selected = pyqtSignal(str, str)
    stats_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        # 初始化場景
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 1200, 800)
        self.setScene(self.scene)
        
        # 設定視圖屬性
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        
        # 初始化組件（假設已導入相關類）
        self.init_routing_system()
        
        # 節點和邊線容器
        self.nodes: Dict[str, DemoTaskNode] = {}
        self.edges: List = []
        
        # 狀態
        self.grid_visible = False
        self.routing_style = "orthogonal"
        self.animation_enabled = True
        
        # 網格顯示項目
        self.grid_items = []
        
    def init_routing_system(self):
        """初始化路由系統"""
        # 這裡應該初始化實際的路由系統
        # self.edge_manager = SceneEdgeManager(self.scene)
        # EnhancedEdgeItem.initialize_router(self.scene.sceneRect())
        pass
        
    def create_node(self, node_id: str, title: str, x: float, y: float) -> DemoTaskNode:
        """創建節點"""
        node = DemoTaskNode(node_id, title)
        node.setPos(x, y)
        self.scene.addItem(node)
        self.nodes[node_id] = node
        
        # 添加為路由障礙物
        # self.edge_manager.router.add_node_obstacle(node.sceneBoundingRect())
        
        return node
        
    def create_edge(self, src_id: str, dst_id: str):
        """創建邊線"""
        if src_id not in self.nodes or dst_id not in self.nodes:
            return None
            
        src_node = self.nodes[src_id]
        dst_node = self.nodes[dst_id]
        
        # 這裡應該創建實際的 EnhancedEdgeItem
        # edge = EnhancedEdgeItem(src_node, dst_node)
        # self.edge_manager.add_edge(edge)
        
        # 臨時：創建簡單線條
        edge = self.create_simple_edge(src_node, dst_node)
        self.edges.append(edge)
        
        src_node.add_edge(edge)
        dst_node.add_edge(edge)
        
        return edge
        
    def create_simple_edge(self, src: DemoTaskNode, dst: DemoTaskNode):
        """創建簡單邊線（臨時方法）"""
        from PyQt5.QtWidgets import QGraphicsLineItem
        
        src_center = src.sceneBoundingRect().center()
        dst_center = dst.sceneBoundingRect().center()
        
        line = QGraphicsLineItem(
            src_center.x(), src_center.y(),
            dst_center.x(), dst_center.y()
        )
        line.setPen(QPen(Qt.black, 2))
        self.scene.addItem(line)
        
        # 添加簡單的更新方法
        line.src = src
        line.dst = dst
        line.invalidateRoute = lambda: None
        line.updatePath = lambda: self.update_simple_edge(line)
        
        return line
        
    def update_simple_edge(self, edge):
        """更新簡單邊線（臨時方法）"""
        src_center = edge.src.sceneBoundingRect().center()
        dst_center = edge.dst.sceneBoundingRect().center()
        edge.setLine(
            src_center.x(), src_center.y(),
            dst_center.x(), dst_center.y()
        )
        
    def clear_all(self):
        """清除所有元素"""
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()
        self.grid_items.clear()
        
        # 重新初始化路由系統
        self.init_routing_system()
        
    def toggle_grid(self):
        """切換網格顯示"""
        if self.grid_visible:
            self.hide_grid()
        else:
            self.show_grid()
        self.grid_visible = not self.grid_visible
        
    def show_grid(self):
        """顯示網格"""
        grid_size = 10
        scene_rect = self.scene.sceneRect()
        
        pen = QPen(QColor(200, 200, 200), 0.5)
        
        # 垂直線
        x = scene_rect.left()
        while x <= scene_rect.right():
            line = self.scene.addLine(
                x, scene_rect.top(),
                x, scene_rect.bottom(),
                pen
            )
            line.setZValue(-10)
            self.grid_items.append(line)
            x += grid_size
            
        # 水平線
        y = scene_rect.top()
        while y <= scene_rect.bottom():
            line = self.scene.addLine(
                scene_rect.left(), y,
                scene_rect.right(), y,
                pen
            )
            line.setZValue(-10)
            self.grid_items.append(line)
            y += grid_size
            
    def hide_grid(self):
        """隱藏網格"""
        for item in self.grid_items:
            self.scene.removeItem(item)
        self.grid_items.clear()
        
    def route_all_edges(self):
        """路由所有邊線"""
        # self.edge_manager.route_all_edges()
        
        # 發送統計更新
        stats = self.get_statistics()
        self.stats_updated.emit(stats)
        
    def get_statistics(self) -> dict:
        """獲取統計資訊"""
        # 實際應該從 edge_manager 獲取
        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'routing_style': self.routing_style,
            'animation_enabled': self.animation_enabled
        }


class ControlPanel(QWidget):
    """控制面板"""
    
    def __init__(self, graph_widget: DemoGraphWidget):
        super().__init__()
        self.graph_widget = graph_widget
        self.init_ui()
        
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        
        # 預設佈局
        layout_group = QGroupBox("預設佈局")
        layout_box = QVBoxLayout()
        
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "3x3 網格", "星形", "樹狀", "環形", 
            "隨機", "層次", "二分圖"
        ])
        layout_box.addWidget(QLabel("選擇佈局:"))
        layout_box.addWidget(self.layout_combo)
        
        create_btn = QPushButton("創建佈局")
        create_btn.clicked.connect(self.create_layout)
        layout_box.addWidget(create_btn)
        
        layout_group.setLayout(layout_box)
        layout.addWidget(layout_group)
        
        # 路由設定
        routing_group = QGroupBox("路由設定")
        routing_box = QVBoxLayout()
        
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "正交 (Orthogonal)",
            "多邊形 (Polyline)",
            "直線 (Straight)",
            "曲線 (Curved)"
        ])
        routing_box.addWidget(QLabel("路由風格:"))
        routing_box.addWidget(self.style_combo)
        
        self.grid_size_spin = QSpinBox()
        self.grid_size_spin.setRange(5, 50)
        self.grid_size_spin.setValue(10)
        self.grid_size_spin.setSuffix(" px")
        routing_box.addWidget(QLabel("網格大小:"))
        routing_box.addWidget(self.grid_size_spin)
        
        self.corner_radius_slider = QSlider(Qt.Horizontal)
        self.corner_radius_slider.setRange(0, 20)
        self.corner_radius_slider.setValue(5)
        routing_box.addWidget(QLabel("圓角半徑:"))
        routing_box.addWidget(self.corner_radius_slider)
        
        routing_group.setLayout(routing_box)
        layout.addWidget(routing_group)
        
        # 優化選項
        optimize_group = QGroupBox("優化選項")
        optimize_box = QVBoxLayout()
        
        self.cache_check = QCheckBox("啟用快取")
        self.cache_check.setChecked(True)
        optimize_box.addWidget(self.cache_check)
        
        self.smooth_check = QCheckBox("平滑轉角")
        self.smooth_check.setChecked(True)
        optimize_box.addWidget(self.smooth_check)
        
        self.animation_check = QCheckBox("動畫效果")
        self.animation_check.setChecked(True)
        optimize_box.addWidget(self.animation_check)
        
        self.batch_check = QCheckBox("批次處理")
        self.batch_check.setChecked(True)
        optimize_box.addWidget(self.batch_check)
        
        optimize_group.setLayout(optimize_box)
        layout.addWidget(optimize_group)
        
        # 操作按鈕
        action_group = QGroupBox("操作")
        action_box = QVBoxLayout()
        
        route_btn = QPushButton("重新路由所有邊線")
        route_btn.clicked.connect(self.route_all)
        action_box.addWidget(route_btn)
        
        clear_btn = QPushButton("清除全部")
        clear_btn.clicked.connect(self.clear_all)
        action_box.addWidget(clear_btn)
        
        grid_btn = QPushButton("顯示/隱藏網格")
        grid_btn.clicked.connect(self.toggle_grid)
        action_box.addWidget(grid_btn)
        
        export_btn = QPushButton("匯出路由")
        export_btn.clicked.connect(self.export_routing)
        action_box.addWidget(export_btn)
        
        import_btn = QPushButton("匯入路由")
        import_btn.clicked.connect(self.import_routing)
        action_box.addWidget(import_btn)
        
        action_group.setLayout(action_box)
        layout.addWidget(action_group)
        
        # 添加彈性空間
        layout.addStretch()
        
        self.setLayout(layout)
        
    def create_layout(self):
        """創建預設佈局"""
        self.graph_widget.clear_all()
        
        layout_type = self.layout_combo.currentText()
        
        if "3x3 網格" in layout_type:
            self.create_grid_layout(3, 3)
        elif "星形" in layout_type:
            self.create_star_layout()
        elif "樹狀" in layout_type:
            self.create_tree_layout()
        elif "環形" in layout_type:
            self.create_circular_layout()
        elif "隨機" in layout_type:
            self.create_random_layout()
        elif "層次" in layout_type:
            self.create_hierarchical_layout()
        elif "二分圖" in layout_type:
            self.create_bipartite_layout()
            
        # 自動路由
        self.route_all()
        
    def create_grid_layout(self, rows: int, cols: int):
        """創建網格佈局"""
        start_x, start_y = 100, 100
        spacing_x, spacing_y = 200, 150
        
        nodes = []
        for row in range(rows):
            for col in range(cols):
                node_id = f"Node_{row}_{col}"
                x = start_x + col * spacing_x
                y = start_y + row * spacing_y
                node = self.graph_widget.create_node(node_id, node_id, x, y)
                nodes.append(node_id)
        
        # 創建網格連接
        for row in range(rows):
            for col in range(cols):
                current = f"Node_{row}_{col}"
                
                # 右邊連接
                if col < cols - 1:
                    right = f"Node_{row}_{col + 1}"
                    self.graph_widget.create_edge(current, right)
                
                # 下方連接
                if row < rows - 1:
                    down = f"Node_{row + 1}_{col}"
                    self.graph_widget.create_edge(current, down)
                    
    def create_star_layout(self):
        """創建星形佈局"""
        center_x, center_y = 400, 400
        radius = 250
        
        # 中心節點
        center = self.graph_widget.create_node("Center", "中心", center_x, center_y)
        
        # 外圍節點
        num_nodes = 8
        for i in range(num_nodes):
            angle = (2 * 3.14159 * i) / num_nodes
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            node_id = f"Node_{i}"
            self.graph_widget.create_node(node_id, node_id, x, y)
            self.graph_widget.create_edge("Center", node_id)
            
    def create_tree_layout(self):
        """創建樹狀佈局"""
        def create_subtree(parent_id, parent_x, parent_y, level, max_level, branch_factor=2):
            if level >= max_level:
                return
                
            spacing_x = 300 / (level + 1)
            spacing_y = 120
            
            for i in range(branch_factor):
                child_id = f"{parent_id}_{i}"
                offset = (i - branch_factor / 2 + 0.5) * spacing_x
                child_x = parent_x + offset
                child_y = parent_y + spacing_y
                
                self.graph_widget.create_node(child_id, child_id, child_x, child_y)
                self.graph_widget.create_edge(parent_id, child_id)
                
                create_subtree(child_id, child_x, child_y, level + 1, max_level, branch_factor)
        
        # 根節點
        root = self.graph_widget.create_node("Root", "根", 400, 50)
        create_subtree("Root", 400, 50, 0, 3, 3)
        
    def create_circular_layout(self):
        """創建環形佈局"""
        center_x, center_y = 400, 400
        radius = 250
        num_nodes = 10
        
        nodes = []
        for i in range(num_nodes):
            angle = (2 * 3.14159 * i) / num_nodes
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            node_id = f"Node_{i}"
            self.graph_widget.create_node(node_id, node_id, x, y)
            nodes.append(node_id)
        
        # 環形連接
        for i in range(num_nodes):
            next_i = (i + 1) % num_nodes
            self.graph_widget.create_edge(nodes[i], nodes[next_i])
            
        # 添加一些交叉連接
        for i in range(0, num_nodes, 2):
            opposite = (i + num_nodes // 2) % num_nodes
            self.graph_widget.create_edge(nodes[i], nodes[opposite])
            
    def create_random_layout(self):
        """創建隨機佈局"""
        import random
        
        num_nodes = 12
        nodes = []
        
        for i in range(num_nodes):
            x = random.randint(50, 750)
            y = random.randint(50, 550)
            node_id = f"Node_{i}"
            self.graph_widget.create_node(node_id, node_id, x, y)
            nodes.append(node_id)
        
        # 隨機連接
        num_edges = num_nodes * 2
        for _ in range(num_edges):
            src = random.choice(nodes)
            dst = random.choice(nodes)
            if src != dst:
                self.graph_widget.create_edge(src, dst)
                
    def create_hierarchical_layout(self):
        """創建層次佈局"""
        levels = [
            ["CEO"],
            ["CTO", "CFO", "COO"],
            ["Dev1", "Dev2", "Fin1", "Fin2", "Op1", "Op2"],
            ["Jr1", "Jr2", "Jr3", "Jr4", "Jr5", "Jr6"]
        ]
        
        y_spacing = 150
        nodes_by_level = []
        
        for level_idx, level_nodes in enumerate(levels):
            y = 100 + level_idx * y_spacing
            x_spacing = 800 / (len(level_nodes) + 1)
            
            level_node_ids = []
            for node_idx, node_name in enumerate(level_nodes):
                x = (node_idx + 1) * x_spacing
                self.graph_widget.create_node(node_name, node_name, x, y)
                level_node_ids.append(node_name)
            
            nodes_by_level.append(level_node_ids)
        
        # 連接層次
        self.graph_widget.create_edge("CEO", "CTO")
        self.graph_widget.create_edge("CEO", "CFO")
        self.graph_widget.create_edge("CEO", "COO")
        
        self.graph_widget.create_edge("CTO", "Dev1")
        self.graph_widget.create_edge("CTO", "Dev2")
        self.graph_widget.create_edge("CFO", "Fin1")
        self.graph_widget.create_edge("CFO", "Fin2")
        self.graph_widget.create_edge("COO", "Op1")
        self.graph_widget.create_edge("COO", "Op2")
        
        for i, jr in enumerate(["Jr1", "Jr2", "Jr3", "Jr4", "Jr5", "Jr6"]):
            parent = ["Dev1", "Dev2", "Fin1", "Fin2", "Op1", "Op2"][i]
            self.graph_widget.create_edge(parent, jr)
            
    def create_bipartite_layout(self):
        """創建二分圖佈局"""
        left_nodes = []
        right_nodes = []
        
        # 左側節點
        for i in range(5):
            y = 100 + i * 120
            node_id = f"Left_{i}"
            self.graph_widget.create_node(node_id, node_id, 200, y)
            left_nodes.append(node_id)
        
        # 右側節點
        for i in range(4):
            y = 150 + i * 140
            node_id = f"Right_{i}"
            self.graph_widget.create_node(node_id, node_id, 600, y)
            right_nodes.append(node_id)
        
        # 創建完全二分圖連接
        for left in left_nodes:
            for right in right_nodes:
                if random.random() > 0.3:  # 70% 連接機率
                    self.graph_widget.create_edge(left, right)
                    
    def route_all(self):
        """路由所有邊線"""
        # 應用設定
        self.apply_settings()
        
        # 執行路由
        self.graph_widget.route_all_edges()
        
    def clear_all(self):
        """清除所有"""
        reply = QMessageBox.question(
            self, '確認', '確定要清除所有節點和邊線嗎？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.graph_widget.clear_all()
            
    def toggle_grid(self):
        """切換網格顯示"""
        self.graph_widget.toggle_grid()
        
    def apply_settings(self):
        """應用當前設定"""
        # 這裡應該將設定應用到實際的路由系統
        style_map = {
            "正交 (Orthogonal)": "orthogonal",
            "多邊形 (Polyline)": "polyline",
            "直線 (Straight)": "straight",
            "曲線 (Curved)": "curved"
        }
        
        self.graph_widget.routing_style = style_map.get(
            self.style_combo.currentText(), "orthogonal"
        )
        self.graph_widget.animation_enabled = self.animation_check.isChecked()
        
        # 應用到路由器配置
        # self.graph_widget.edge_manager.router.configure(
        #     grid_size=self.grid_size_spin.value(),
        #     corner_radius=self.corner_radius_slider.value(),
        #     enable_caching=self.cache_check.isChecked(),
        #     enable_smoothing=self.smooth_check.isChecked()
        # )
        
    def export_routing(self):
        """匯出路由"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "匯出路由", "", "JSON Files (*.json)"
        )
        
        if filename:
            # 實際應該使用 RoutingSerializer
            data = {
                'nodes': [],
                'edges': [],
                'settings': {
                    'routing_style': self.graph_widget.routing_style,
                    'grid_size': self.grid_size_spin.value(),
                    'corner_radius': self.corner_radius_slider.value()
                }
            }
            
            # 匯出節點
            for node_id, node in self.graph_widget.nodes.items():
                data['nodes'].append({
                    'id': node_id,
                    'x': node.pos().x(),
                    'y': node.pos().y()
                })
            
            # 匯出邊線
            for edge in self.graph_widget.edges:
                if hasattr(edge, 'src') and hasattr(edge, 'dst'):
                    data['edges'].append({
                        'src': edge.src.taskId,
                        'dst': edge.dst.taskId
                    })
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
                
            QMessageBox.information(self, "成功", "路由已匯出")
            
    def import_routing(self):
        """匯入路由"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "匯入路由", "", "JSON Files (*.json)"
        )
        
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            self.graph_widget.clear_all()
            
            # 匯入節點
            for node_data in data.get('nodes', []):
                self.graph_widget.create_node(
                    node_data['id'],
                    node_data['id'],
                    node_data['x'],
                    node_data['y']
                )
            
            # 匯入邊線
            for edge_data in data.get('edges', []):
                self.graph_widget.create_edge(
                    edge_data['src'],
                    edge_data['dst']
                )
            
            # 匯入設定
            settings = data.get('settings', {})
            if 'grid_size' in settings:
                self.grid_size_spin.setValue(settings['grid_size'])
            if 'corner_radius' in settings:
                self.corner_radius_slider.setValue(settings['corner_radius'])
            
            self.route_all()
            QMessageBox.information(self, "成功", "路由已匯入")


class StatisticsPanel(QWidget):
    """統計面板"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        
        # 基本統計
        self.stats_table = QTableWidget(10, 2)
        self.stats_table.setHorizontalHeaderLabels(["項目", "值"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.verticalHeader().setVisible(False)
        
        # 初始化統計項目
        stats_items = [
            ("節點總數", "0"),
            ("邊線總數", "0"),
            ("成功路由", "0"),
            ("失敗路由", "0"),
            ("平均彎曲數", "0"),
            ("平均路徑長度", "0"),
            ("快取命中率", "0%"),
            ("平均計算時間", "0ms"),
            ("效能分數", "0/100"),
            ("記憶體使用", "0 MB")
        ]
        
        for i, (name, value) in enumerate(stats_items):
            self.stats_table.setItem(i, 0, QTableWidgetItem(name))
            self.stats_table.setItem(i, 1, QTableWidgetItem(value))
        
        layout.addWidget(QLabel("路由統計"))
        layout.addWidget(self.stats_table)
        
        # 效能建議
        self.suggestions_text = QTextEdit()
        self.suggestions_text.setReadOnly(True)
        self.suggestions_text.setMaximumHeight(150)
        
        layout.addWidget(QLabel("優化建議"))
        layout.addWidget(self.suggestions_text)
        
        self.setLayout(layout)
        
    def update_statistics(self, stats: dict):
        """更新統計資訊"""
        # 更新表格
        if 'total_nodes' in stats:
            self.stats_table.item(0, 1).setText(str(stats['total_nodes']))
        if 'total_edges' in stats:
            self.stats_table.item(1, 1).setText(str(stats['total_edges']))
            
        # 更新其他統計...
        
        # 生成優化建議
        suggestions = []
        if stats.get('total_edges', 0) > 50:
            suggestions.append("• 邊線數量較多，建議啟用批次處理")
        if stats.get('total_nodes', 0) > 30:
            suggestions.append("• 節點密度較高，建議使用正交路由")
            
        self.suggestions_text.setText("\n".join(suggestions))


class MainWindow(QMainWindow):
    """主視窗"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("yEd Edge Routing 演示系統")
        self.setGeometry(100, 100, 1400, 900)
        
        self.init_ui()
        self.init_menu()
        
    def init_ui(self):
        """初始化使用者介面"""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主佈局
        main_layout = QHBoxLayout(central_widget)
        
        # 創建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 圖形視圖
        self.graph_widget = DemoGraphWidget()
        splitter.addWidget(self.graph_widget)
        
        # 右側面板
        right_panel = QSplitter(Qt.Vertical)
        
        # 控制面板
        self.control_panel = ControlPanel(self.graph_widget)
        right_panel.addWidget(self.control_panel)
        
        # 統計面板
        self.stats_panel = StatisticsPanel()
        right_panel.addWidget(self.stats_panel)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([1000, 400])
        
        main_layout.addWidget(splitter)
        
        # 連接信號
        self.graph_widget.stats_updated.connect(self.stats_panel.update_statistics)
        
        # 狀態列
        self.statusBar().showMessage("就緒")
        
    def init_menu(self):
        """初始化選單"""
        menubar = self.menuBar()
        
        # 檔案選單
        file_menu = menubar.addMenu("檔案")
        
        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_graph)
        file_menu.addAction(new_action)
        
        open_action = QAction("開啟", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_graph)
        file_menu.addAction(open_action)
        
        save_action = QAction("儲存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_graph)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("離開", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 編輯選單
        edit_menu = menubar.addMenu("編輯")
        
        select_all_action = QAction("全選", self)
        select_all_action.setShortcut("Ctrl+A")
        edit_menu.addAction(select_all_action)
        
        # 檢視選單
        view_menu = menubar.addMenu("檢視")
        
        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("縮小", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        # 幫助選單
        help_menu = menubar.addMenu("幫助")
        
        about_action = QAction("關於", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def new_graph(self):
        """新建圖形"""
        self.graph_widget.clear_all()
        self.statusBar().showMessage("已創建新圖形")
        
    def open_graph(self):
        """開啟圖形"""
        self.control_panel.import_routing()
        
    def save_graph(self):
        """儲存圖形"""
        self.control_panel.export_routing()
        
    def zoom_in(self):
        """放大"""
        self.graph_widget.scale(1.2, 1.2)
        
    def zoom_out(self):
        """縮小"""
        self.graph_widget.scale(0.8, 0.8)
        
    def show_about(self):
        """顯示關於對話框"""
        QMessageBox.about(
            self,
            "關於",
            "yEd Edge Routing 演示系統\n\n"
            "版本：1.0\n"
            "展示 yEd 風格的邊線路由功能\n\n"
            "功能特點：\n"
            "• 正交路由\n"
            "• 智慧避障\n"
            "• 多邊線分散\n"
            "• 路徑優化\n"
            "• 效能監控"
        )


def main():
    """主程式入口"""
    import math  # 確保 math 模組已導入
    
    app = QApplication(sys.argv)
    
    # 設定應用程式樣式
    app.setStyle("Fusion")
    
    # 創建並顯示主視窗
    window = MainWindow()
    window.show()
    
    # 創建初始演示佈局
    window.control_panel.layout_combo.setCurrentText("3x3 網格")
    window.control_panel.create_layout()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()