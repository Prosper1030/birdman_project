#!/usr/bin/env python3
"""
測試選取狀態同步效果
驗證顏色變化和把手顯示的同步性
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer

from src.ui.dsm_editor import DsmEditor

def test_selection_sync():
    """測試選取狀態同步效果"""
    print("🎯 測試選取狀態同步效果")
    print("✨ 驗證顏色變化和把手顯示是否同步")
    
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
    
    if editor.nodes:
        nodes = list(editor.nodes.values())
        
        print("\n🧪 測試選取狀態變化的同步性:")
        print("1. 🎨 未選取時：高彩度亮黃色背景，無把手")
        print("2. 🎨 選取時：降彩偏灰背景，立即顯示8個調整把手")
        print("3. ⚡ 狀態變化應該瞬間完成，無延遲")
        
        print("\n🎮 自動測試步驟:")
        print("步驟 1: 初始狀態 - 所有節點未選取（亮黃色）")
        print("步驟 2: 選取第一個節點（瞬間變灰 + 顯示把手）")
        print("步驟 3: 選取第二個節點（第一個恢復黃色，第二個變灰）")
        print("步驟 4: 清除選取（所有節點恢復黃色，把手消失）")
        
        def auto_test():
            print("\n⏰ 開始自動測試...")
            
            # 測試序列
            test_sequence = [
                (1000, lambda: nodes[0].setSelected(True), "選取節點1"),
                (2000, lambda: (nodes[0].setSelected(False), nodes[1].setSelected(True)), "切換到節點2"),
                (3000, lambda: (nodes[1].setSelected(False), nodes[2].setSelected(True)), "切換到節點3"),
                (4000, lambda: nodes[2].setSelected(False), "清除所有選取"),
                (5000, lambda: (nodes[0].setSelected(True), nodes[1].setSelected(True)), "多選測試"),
                (6000, lambda: editor.scene().clearSelection(), "清除多選"),
            ]
            
            for delay, action, description in test_sequence:
                QTimer.singleShot(delay, lambda desc=description, act=action: (
                    print(f"🔄 {desc}"),
                    act() if callable(act) else [a() for a in act] if isinstance(act, tuple) else None
                ))
        
        # 啟動自動測試
        QTimer.singleShot(500, auto_test)
        
        print("\n🚀 編輯器已準備就緒")
        print("觀察節點顏色和把手的同步變化！")
        print("按 Ctrl+C 退出測試")
        
    try:
        app.exec_()
    except KeyboardInterrupt:
        print("\n👋 測試結束")

if __name__ == "__main__":
    test_selection_sync()
