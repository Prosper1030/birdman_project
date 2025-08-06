#!/usr/bin/env python3
"""
測試新版 yEd 風格 DSM 編輯器
"""

import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication

# 導入新版編輯器
try:
    from src.ui.dsm_editor import DsmEditor
    print("✅ 成功導入新版 DsmEditor")
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    sys.exit(1)

def create_test_data():
    """創建測試數據"""
    return pd.DataFrame({
        'Task ID': ['T001', 'T002', 'T003', 'T004', 'T005'],
        'Name': ['系統設計', '程式開發', '測試驗證', '文件撰寫', '專案管理'],
        'Property': ['設計', '開發', '測試', '文件', '管理']
    })

def main():
    """測試新版編輯器"""
    app = QApplication(sys.argv)
    
    # 創建測試數據
    test_df = create_test_data()
    
    # 創建編輯器
    editor = DsmEditor(test_df)
    
    print("🚀 新版 yEd 風格 DSM 編輯器啟動")
    print("🎯 新功能測試:")
    print("   ✅ 視窗最大化/最小化控制")
    print("   ✅ 8 個可調整大小的把手")
    print("   ✅ 橡皮筋框選功能")
    print("   ✅ 優化的連線系統")
    print("   ✅ 撤銷/重做功能 (Ctrl+Z/Ctrl+Y)")
    print("   ✅ 網格對齊系統")
    print("   ✅ 效能優化渲染")
    print("\n🎮 操作說明:")
    print("   🖱️  單擊節點 → 顯示 8 個調整把手")
    print("   🖱️  拖拽把手 → 調整節點大小") 
    print("   🖱️  空白區域拖拽 → 橡皮筋框選")
    print("   🖱️  節點內快速拖拽 → 建立連線")
    print("   ⌨️  Delete → 刪除選中項目")
    print("   ⌨️  Ctrl+A → 全選")
    print("   ⌨️  Esc → 取消操作")
    
    editor.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
