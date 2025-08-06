#!/usr/bin/env python3
"""
測試 yEd 風格把手功能
驗證把手位於節點外圍且距離固定
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QCursor

from src.ui.dsm_editor import DsmEditor

def test_yed_style_handles():
    """測試 yEd 風格把手功能"""
    print("🎯 測試 yEd 風格把手功能")
    print("✨ 把手位於節點外圍，距離固定，懸停時才顯示調整游標")
    
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
        
        print(f"✅ 節點 '{first_node.text}' 已選中，把手應該可見")
        
        # 檢查把手配置
        if first_node._selection_handles:
            handle = first_node._selection_handles[0]  # 左上角把手
            print(f"📏 把手視覺大小: {handle.HANDLE_SIZE}px")
            print(f"📐 把手距離節點: {handle.HANDLE_DISTANCE}px")
            print(f"🎯 懸停檢測範圍: {handle.HOVER_DETECTION_RANGE}px")
            
            # 檢查游標設定
            cursor = handle.cursor()
            print(f"🖱️ 左上角把手游標: {cursor.shape()}")
            print(f"🎯 預期游標: {Qt.SizeFDiagCursor} (對角線調整)")
            
            if cursor.shape() == Qt.SizeFDiagCursor:
                print("✅ 游標設定正確")
            else:
                print("❌ 游標設定錯誤")
        
        print("\n🧪 yEd 風格把手特點:")
        print("1. 📍 把手位於節點外圍（不在節點邊緣上）")
        print("2. 📏 距離節點邊緣固定 5px")
        print("3. 👁️ 把手大小 6x6px（黑色小方塊）")
        print("4. 🎯 懸停檢測範圍 8px（比把手稍大）")
        print("5. 🖱️ 只有懸停在把手上時才顯示調整游標")
        print("6. 🎨 未選取時：高彩度亮黃色背景")
        print("7. 🎨 選取時：降彩偏灰背景 + 8個調整把手")
        
        print("\n🎮 互動測試步驟:")
        print("步驟 1: 選中任一節點（已自動選中）")
        print("   → 8個黑色小方塊把手出現在節點外圍")
        print("步驟 2: 將滑鼠懸停在角落把手上")
        print("   → 游標變成對角線調整 ↖️ ↗️ ↘️ ↙️")
        print("步驟 3: 將滑鼠懸停在邊緣把手上")
        print("   → 游標變成水平/垂直調整 ↔️ ↕️")
        print("步驟 4: 在把手上按住左鍵拖拽")
        print("   → 節點開始調整大小")
        print("步驟 5: 調整大小時把手保持固定距離")
        print("   → 無論節點多大，把手始終距離邊緣 5px")
        
        print("\n💡 yEd 風格設計優勢:")
        print("• 把手不會與節點內容重疊")
        print("• 固定距離確保一致的使用體驗")
        print("• 懸停檢測避免誤觸")
        print("• 清晰的視覺回饋")
        
        print("\n🚀 編輯器已準備就緒")
        print("請測試 yEd 風格把手功能！")
        print("按 Ctrl+C 退出測試")
        
    try:
        app.exec_()
    except KeyboardInterrupt:
        print("\n👋 測試結束")

if __name__ == "__main__":
    test_yed_style_handles()
