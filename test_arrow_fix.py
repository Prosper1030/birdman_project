#!/usr/bin/env python3
"""
測試箭頭修復
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                            QWidget, QPushButton, QLabel, QGraphicsScene)
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QBrush, QColor

from src.routing.enhanced_edge_item import EnhancedEdgeItem
from src.routing.engine import RoutingStyle
from src.ui.dsm_editor import CanvasView


class TestNode:
    """簡單測試節點"""
    def __init__(self, x, y, width=80, height=60, task_id="TestNode"):
        self._rect = QRectF(x, y, width, height)
        self.taskId = task_id
        
    def sceneBoundingRect(self):
        return self._rect


class ArrowFixTestWindow(QMainWindow):
    """箭頭修復測試視窗"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("箭頭修復測試")
        self.setGeometry(100, 100, 800, 600)
        
        # 建立 UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.status_label = QLabel("準備測試...")
        layout.addWidget(self.status_label)
        
        # 建立場景和視圖
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-400, -300, 800, 600)
        self.scene.setBackgroundBrush(QBrush(QColor(240, 240, 240)))
        
        self.view = CanvasView(self.scene)
        layout.addWidget(self.view)
        
        # 控制按鈕
        test_btn = QPushButton("開始測試")
        test_btn.clicked.connect(self.run_test)
        layout.addWidget(test_btn)
        
    def run_test(self):
        """運行測試"""
        try:
            self.status_label.setText("正在測試...")
            
            # 1. 初始化路由引擎
            EnhancedEdgeItem.initialize_router(self.scene.sceneRect())
            self.status_label.setText("✅ 路由引擎初始化成功")
            
            # 2. 創建測試節點
            node1 = TestNode(-150, -50, 100, 60, "測試節點1")
            node2 = TestNode(50, -50, 100, 60, "測試節點2")
            
            # 3. 創建邊線
            edge = EnhancedEdgeItem(node1, node2)
            self.scene.addItem(edge)
            
            # 4. 檢查箭頭
            if hasattr(edge, 'arrow_head') and edge.arrow_head:
                self.status_label.setText("✅ 邊線創建成功，箭頭存在")
                
                # 5. 測試 getConnectionPoint 方法
                try:
                    # 測試新的調用方式
                    point1 = edge.getConnectionPoint(node1.sceneBoundingRect(), QPointF(0, 0))
                    # 測試舊的調用方式  
                    point2 = edge.getConnectionPoint(node1.sceneBoundingRect(), QPointF(-150, -20), 100, 0)
                    self.status_label.setText("✅ getConnectionPoint 方法測試成功")
                except Exception as e:
                    self.status_label.setText(f"❌ getConnectionPoint 測試失敗：{e}")
                    return
                
                # 6. 強制更新路徑
                edge.updatePath()
                self.status_label.setText("✅ 所有測試通過！邊線應該有箭頭")
                
                # 7. 檢查箭頭的父項目設定
                if edge.arrow_head.parentItem() == edge:
                    self.status_label.setText("✅ 箭頭父項目設定正確")
                else:
                    self.status_label.setText("❌ 箭頭父項目設定錯誤")
                    
            else:
                self.status_label.setText("❌ 箭頭創建失敗")
                
        except Exception as e:
            self.status_label.setText(f"❌ 測試失敗：{e}")
            import traceback
            traceback.print_exc()


def main():
    app = QApplication(sys.argv)
    
    window = ArrowFixTestWindow()
    window.show()
    
    print("=== 箭頭修復測試 ===")
    print("點擊「開始測試」按鈕測試箭頭修復")
    print("如果看到「所有測試通過！」表示修復成功")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()