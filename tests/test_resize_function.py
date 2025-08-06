#!/usr/bin/env python3
"""
測試調整大小功能
驗證 yEd 風格把手能否正確調整節點大小
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QCursor

from src.ui.dsm_editor import DsmEditor

def test_resize_functionality():
    """測試調整大小功能"""
    print("🎯 測試調整大小功能")
    print("✨ 驗證 yEd 風格把手能否正確調整節點大小")
    
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
        first_node.setSelected(True)  # 選中節點以顯示把手
        
        print(f"✅ 節點 '{first_node.text}' 已選中")
        print(f"📐 初始節點尺寸: {first_node.rect().width():.1f} x {first_node.rect().height():.1f}")
        print(f"📍 初始節點位置: ({first_node.pos().x():.1f}, {first_node.pos().y():.1f})")
        
        # 檢查把手
        if first_node._selection_handles:
            handle = first_node._selection_handles[0]  # 左上角把手
            print(f"🔧 把手狀態:")
            print(f"   - 調整中: {handle.resizing}")
            print(f"   - 懸停狀態: {handle._is_hovered}")
            print(f"   - 最小節點尺寸: {handle.MIN_NODE_SIZE}px")
            
            # 模擬把手操作來驗證邏輯
            print(f"\n🧪 模擬測試把手邏輯:")
            print(f"   - 把手索引 0 (左上角): {handle.handle_index}")
            print(f"   - 游標類型: {handle.cursor().shape()}")
            
        print("\n🎮 手動測試步驟:")
        print("1. 🖱️ 將滑鼠移至節點角落的黑色小方塊上")
        print("   → 游標變成對角線調整 ↖️")
        print("2. 🖱️ 按住左鍵並拖拽")
        print("   → 節點應該開始調整大小")
        print("3. 📏 觀察節點尺寸變化")
        print("   → 節點應該跟隨滑鼠移動調整大小")
        print("4. 🖱️ 鬆開滑鼠按鈕")
        print("   → 調整大小完成")
        print("5. 🔄 測試其他把手")
        print("   → 每個把手都應該能正確調整對應方向")
        
        print("\n🔍 調試資訊:")
        print("如果調整大小不工作，請檢查:")
        print("• 把手是否正確響應懸停事件")
        print("• mousePressEvent 是否正確設定 resizing=True")
        print("• mouseMoveEvent 是否調用 _resizeParentNode")
        print("• _resizeParentNode 是否正確更新節點")
        
        print("\n🚀 編輯器已準備就緒")
        print("請測試調整大小功能！")
        print("按 Ctrl+C 退出測試")
        
    try:
        app.exec_()
    except KeyboardInterrupt:
        print("\n👋 測試結束")

if __name__ == "__main__":
    test_resize_functionality()
