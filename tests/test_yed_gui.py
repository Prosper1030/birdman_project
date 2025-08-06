#!/usr/bin/env python3
"""
yEd 風格 GUI 測試腳本
測試重構後的 DSM 編輯器功能
"""

import sys
import os
import pandas as pd
from PyQt5.QtWidgets import QApplication

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ui.dsm_editor import DsmEditor

def create_test_data():
    """創建測試用的 WBS 數據"""
    test_data = {
        'Task ID': ['A', 'B', 'C', 'D', 'E'],
        'Name': [
            '需求分析',
            '系統設計', 
            '編碼實現',
            '測試驗證',
            '部署上線'
        ],
        'Property': [
            '分析',
            '設計',
            '開發', 
            '測試',
            '部署'
        ]
    }
    return pd.DataFrame(test_data)

def main():
    """主函數 - 啟動 yEd 風格 GUI 測試"""
    app = QApplication(sys.argv)
    
    # 創建測試數據
    wbs_df = create_test_data()
    
    # 創建並顯示編輯器
    editor = DsmEditor(wbs_df)
    editor.show()
    
    print("🚀 yEd 風格 GUI 測試啟動")
    print("✅ 功能測試項目:")
    print("   1. 調整大小把手 - 拖拽節點邊緣的黑色小方塊")
    print("   2. 選取與移動 - 單擊選中顯示把手，然後拖拽移動")  
    print("   3. 橡皮筋框選 - 在空白區域拖拽產生選取框")
    print("   4. 連線功能 - 在節點內按住拖拽創建箭頭連線")
    print("   5. 多選操作 - Ctrl+點擊進行多重選取")
    print("   6. 鍵盤快捷鍵 - F2編輯、Delete刪除、ESC取消")
    print("\n⚡ 預期體驗: 如 yEd 般流暢的 60fps 互動體驗")
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
