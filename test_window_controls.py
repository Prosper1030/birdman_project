#!/usr/bin/env python3
"""
簡單測試依賴關係編輯器的視窗控制功能
"""

import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication

# 確保可以導入 dsm_editor
try:
    from src.ui.dsm_editor import DsmEditor
    print("✅ 成功導入 DsmEditor")
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    sys.exit(1)

def create_simple_test_data():
    """創建簡單的測試數據"""
    return pd.DataFrame({
        'Task ID': ['A', 'B', 'C'],
        'Name': ['任務A', '任務B', '任務C'],
        'Property': ['測試', '測試', '測試']
    })

def main():
    """測試視窗控制功能"""
    app = QApplication(sys.argv)
    
    # 創建測試數據
    test_df = create_simple_test_data()
    
    # 創建編輯器
    editor = DsmEditor(test_df)
    
    print("🚀 依賴關係編輯器啟動")
    print("📋 視窗控制功能測試:")
    print("   ✅ 最小化按鈕 - 視窗標題列左側")
    print("   ✅ 最大化按鈕 - 視窗標題列中間") 
    print("   ✅ 關閉按鈕 - 視窗標題列右側")
    print("\n🔍 請檢查視窗標題列是否有完整的控制按鈕")
    
    editor.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
