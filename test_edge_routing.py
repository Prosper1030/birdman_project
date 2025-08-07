"""
測試 yEd 風格邊線路由系統

測試內容:
1. 正交可見性圖構建
2. A* 路徑搜尋
3. Manhattan routing
4. 多邊線處理
5. 性能測試
"""

import sys
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLabel, QComboBox
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter

from src.edge_routing import EdgeRoutingEngine, RoutingNode
from src.routed_edge_item import RoutedEdgeItem


class MockTaskNode:
    """模擬節點類別 - 用於測試"""
    def __init__(self, task_id: str, pos: QPointF, size: QRectF):
        self.taskId = task_id
        self.position = pos
        self.size = size
    
    def sceneBoundingRect(self):
        return QRectF(
            self.position.x() - self.size.width()/2,
            self.position.y() - self.size.height()/2,
            self.size.width(),
            self.size.height()
        )


class EdgeRoutingTestWindow(QMainWindow):
    """邊線路由測試視窗"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("yEd 風格邊線路由測試")
        self.setGeometry(100, 100, 1200, 800)
        
        # 創建路由引擎
        self.routing_engine = EdgeRoutingEngine()
        
        # 創建測試節點
        self.test_nodes = self._create_test_nodes()
        
        # 設定 UI
        self.setupUI()
        
        # 初始化測試
        self.update_obstacles()
        self.create_test_edges()
    
    def setupUI(self):
        """設定使用者介面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 控制面板
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
        
        # 圖形視圖
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.view)
        
        # 狀態欄
        self.status_label = QLabel("就緒")
        layout.addWidget(self.status_label)
    
    def _create_control_panel(self):
        """創建控制面板"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # 路由模式選擇
        layout.addWidget(QLabel("路由模式:"))
        self.routing_mode_combo = QComboBox()
        self.routing_mode_combo.addItems(["直線", "正交", "智慧"])
        self.routing_mode_combo.setCurrentText("智慧")
        self.routing_mode_combo.currentTextChanged.connect(self.change_routing_mode)
        layout.addWidget(self.routing_mode_combo)
        
        # 控制按鈕
        self.refresh_btn = QPushButton("重新路由")
        self.refresh_btn.clicked.connect(self.refresh_routing)
        layout.addWidget(self.refresh_btn)
        
        self.performance_btn = QPushButton("性能測試")
        self.performance_btn.clicked.connect(self.run_performance_test)
        layout.addWidget(self.performance_btn)
        
        self.clear_btn = QPushButton("清除")
        self.clear_btn.clicked.connect(self.clear_scene)
        layout.addWidget(self.clear_btn)
        
        layout.addStretch()
        
        return panel
    
    def _create_test_nodes(self):
        """創建測試節點"""
        nodes = [
            MockTaskNode("A", QPointF(150, 150), QRectF(0, 0, 100, 60)),
            MockTaskNode("B", QPointF(400, 150), QRectF(0, 0, 100, 60)),
            MockTaskNode("C", QPointF(150, 350), QRectF(0, 0, 100, 60)),
            MockTaskNode("D", QPointF(400, 350), QRectF(0, 0, 100, 60)),
            MockTaskNode("E", QPointF(275, 250), QRectF(0, 0, 80, 80)),  # 中間障礙物
            MockTaskNode("F", QPointF(600, 200), QRectF(0, 0, 120, 40)),
            MockTaskNode("G", QPointF(700, 400), QRectF(0, 0, 90, 70)),
        ]
        return {node.taskId: node for node in nodes}
    
    def update_obstacles(self):
        """更新路由引擎的障礙物"""
        obstacles = []
        for node in self.test_nodes.values():
            obstacles.append((node.sceneBoundingRect(), node.taskId))
        
        start_time = time.time()
        self.routing_engine.set_obstacles(obstacles)
        end_time = time.time()
        
        stats = self.routing_engine.get_performance_stats()
        self.status_label.setText(
            f"障礙物更新完成 ({(end_time-start_time)*1000:.1f}ms) - "
            f"節點: {stats['nodes']}, 邊: {stats['edges']}, 障礙物: {stats['obstacles']}"
        )
    
    def create_test_edges(self):
        """創建測試邊線"""
        self.clear_scene()
        
        # 繪製節點
        for node in self.test_nodes.values():
            rect = node.sceneBoundingRect()
            rect_item = self.scene.addRect(rect, QPen(Qt.black, 2), QBrush(QColor(255, 215, 0, 150)))
            
            # 添加標籤
            text_item = self.scene.addText(node.taskId, font=self.view.font())
            text_item.setPos(rect.center() - QPointF(text_item.boundingRect().width()/2, 
                                                   text_item.boundingRect().height()/2))
        
        # 測試邊線
        test_edges = [
            ("A", "B"),  # 水平
            ("A", "C"),  # 垂直
            ("A", "D"),  # 對角線，需要繞過中間節點
            ("B", "F"),  # 長距離
            ("C", "G"),  # 複雜路徑
            ("E", "F"),  # 從中間障礙物
            ("A", "E"),  # 短距離
            ("D", "F"),  # 多重障礙物
        ]
        
        self.test_routed_edges = []
        total_routing_time = 0
        
        for src_id, dst_id in test_edges:
            if src_id in self.test_nodes and dst_id in self.test_nodes:
                src_node = self.test_nodes[src_id]
                dst_node = self.test_nodes[dst_id]
                
                # 創建路由邊線
                start_time = time.time()
                routed_edge = RoutedEdgeItem(src_node, dst_node, self.routing_engine)
                end_time = time.time()
                
                routing_time = (end_time - start_time) * 1000
                total_routing_time += routing_time
                
                # 設定路由模式
                mode_map = {"直線": "direct", "正交": "orthogonal", "智慧": "smart"}
                routed_edge.setRoutingMode(mode_map[self.routing_mode_combo.currentText()])
                
                self.scene.addItem(routed_edge)
                self.test_routed_edges.append(routed_edge)
                
                print(f"邊線 {src_id}->{dst_id} 路由時間: {routing_time:.2f}ms")
        
        print(f"總路由時間: {total_routing_time:.2f}ms")
        self.status_label.setText(f"已創建 {len(self.test_routed_edges)} 條路由邊線 (總計: {total_routing_time:.1f}ms)")
    
    def change_routing_mode(self, mode_text):
        """改變路由模式"""
        mode_map = {"直線": "direct", "正交": "orthogonal", "智慧": "smart"}
        mode = mode_map[mode_text]
        
        start_time = time.time()
        for edge in self.test_routed_edges:
            edge.setRoutingMode(mode)
        end_time = time.time()
        
        print(f"路由模式切換到 {mode_text} ({(end_time-start_time)*1000:.1f}ms)")
        self.status_label.setText(f"路由模式: {mode_text} ({(end_time-start_time)*1000:.1f}ms)")
    
    def refresh_routing(self):
        """重新路由"""
        start_time = time.time()
        
        # 清除快取並重新路由
        for edge in self.test_routed_edges:
            edge.invalidateRouteCache()
            edge.updateRoutedPath()
        
        end_time = time.time()
        print(f"重新路由完成 ({(end_time-start_time)*1000:.1f}ms)")
        self.status_label.setText(f"重新路由完成 ({(end_time-start_time)*1000:.1f}ms)")
    
    def run_performance_test(self):
        """運行性能測試"""
        print("\n=== 性能測試開始 ===")
        
        # 測試 1: 大量障礙物
        print("測試 1: 大量障礙物建構")
        large_obstacles = []
        for i in range(50):
            for j in range(20):
                rect = QRectF(i * 25, j * 25, 20, 20)
                large_obstacles.append((rect, f"obs_{i}_{j}"))
        
        start_time = time.time()
        temp_engine = EdgeRoutingEngine()
        temp_engine.set_obstacles(large_obstacles)
        end_time = time.time()
        
        print(f"  1000 障礙物建構: {(end_time-start_time)*1000:.1f}ms")
        
        # 測試 2: 大量路由計算
        print("測試 2: 大量路由計算")
        start_time = time.time()
        
        for i in range(20):
            start_pos = QPointF(i * 60, 100)
            end_pos = QPointF(1200 - i * 60, 400)
            path = temp_engine.route_edge(start_pos, end_pos)
        
        end_time = time.time()
        print(f"  20 條路由計算: {(end_time-start_time)*1000:.1f}ms")
        print(f"  平均每條: {((end_time-start_time)*1000/20):.2f}ms")
        
        # 測試 3: 複雜度分析
        node_counts = [10, 25, 50, 100]
        for count in node_counts:
            obstacles = []
            for i in range(count):
                rect = QRectF(i * 15, (i % 10) * 15, 10, 10)
                obstacles.append((rect, f"node_{i}"))
            
            start_time = time.time()
            test_engine = EdgeRoutingEngine()
            test_engine.set_obstacles(obstacles)
            end_time = time.time()
            
            print(f"  {count} 節點建構: {(end_time-start_time)*1000:.2f}ms")
        
        print("=== 性能測試完成 ===\n")
        self.status_label.setText("性能測試完成 - 查看控制台輸出")
    
    def clear_scene(self):
        """清除場景"""
        self.scene.clear()
        self.test_routed_edges = []


def main():
    """主函數"""
    app = QApplication(sys.argv)
    
    # 創建測試視窗
    window = EdgeRoutingTestWindow()
    window.show()
    
    # 運行測試
    print("yEd 風格邊線路由測試啟動")
    print("- 測試正交可見性圖構建")
    print("- 測試 A* 路徑搜尋算法")
    print("- 測試 Manhattan routing")
    print("- 測試多種路由模式")
    print("\n使用控制面板切換路由模式和測試功能")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()