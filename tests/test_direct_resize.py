#!/usr/bin/env python3
"""
測試直接調整大小功能
驗證當 diagonal resize cursor 出現時能立即調整大小
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QCursor

from src.ui.dsm_editor import DsmEditor

def test_direct_resize_functionality():
    """測試直接調整大小功能"""
    print("🎯 測試直接調整大小功能")
    print("✨ 當 diagonal resize cursor 出現時能立即調整節點大小")
    
    # 創建測試資料
    test_data = pd.DataFrame({
        'Task ID': ['T1', 'T2', 'T3'],
        'Name': ['任務一', '任務二', '任務三'],
        'Property': ['重要', '普通', '緊急']
    })
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 創建編輯器
    editor = DsmEditor(test_data)
    editor.show()
    
    print("✅ DSM 編輯器已創建")
    
    # 獲取第一個節點進行測試
    if editor.nodes:
        first_node = list(editor.nodes.values())[0]
        first_node.setSelected(True)  # 選中節點
        
        print(f"✅ 節點 '{first_node.text}' 已選中")
        print(f"📏 邊緣檢測距離: {first_node.RESIZE_MARGIN}px")
        
        # 檢查初始狀態
        print(f"🔧 調整大小模式: {first_node._resize_mode}")
        print(f"📐 調整大小中: {first_node._resizing}")
        
        print("\n🧪 功能測試說明:")
        print("1. 選中任一節點（已自動選中第一個節點）")
        print("2. 將滑鼠移至節點邊緣（15px 範圍內）")
        print("3. 觀察游標變化：")
        print("   - 角落: ↖️ ↗️ ↘️ ↙️ (對角線調整)")
        print("   - 邊緣: ↔️ ↕️ (水平/垂直調整)")
        print("4. 當看到調整大小游標時，立即按住左鍵拖拽")
        print("5. 節點應該立即開始調整大小")
        print("6. 鬆開滑鼠按鈕完成調整")
        
        print("\n🎮 互動測試步驟:")
        print("步驟 1: 將滑鼠移至節點左上角附近")
        print("   → 游標應變成 ↖️ (SizeFDiagCursor)")
        print("步驟 2: 立即按住左鍵並拖拽")
        print("   → 節點應立即開始調整大小")
        print("步驟 3: 測試其他邊緣和角落")
        print("   → 每個位置都應有對應的調整游標")
        
        print("\n💡 關鍵改進:")
        print("• 不再需要精確點擊小把手")
        print("• 游標變化立即表示可以調整大小")
        print("• 15px 邊緣檢測範圍，更容易觸發")
        print("• 支援8個方向的調整大小")
        
        print("\n🚀 編輯器已準備就緒")
        print("請測試邊緣調整大小功能！")
        print("按 Ctrl+C 退出測試")
        
    try:
        app.exec_()
    except KeyboardInterrupt:
        print("\n👋 測試結束")

if __name__ == "__main__":
    test_direct_resize_functionality()
