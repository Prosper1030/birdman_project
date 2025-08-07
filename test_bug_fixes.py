#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 DSM 編輯器 bug 修正
"""

import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt
from src.ui.dsm_editor import DsmEditor

def test_dsm_editor_fixes():
    """測試 DSM 編輯器的 bug 修正"""
    
    # 創建測試 WBS 資料
    test_wbs = pd.DataFrame({
        'Task ID': ['A', 'B', 'C', 'D'],
        'Name': ['任務A', '任務B', '任務C', '任務D'],
        'Property': ['prop1', 'prop2', 'prop3', 'prop4']
    })
    
    app = QApplication(sys.argv)
    
    # 創建主視窗
    main_window = QMainWindow()
    main_window.setWindowTitle("DSM 編輯器 Bug 修正測試")
    main_window.resize(1200, 800)
    
    # 創建 DSM 編輯器
    editor = DsmEditor(test_wbs, main_window)
    main_window.setCentralWidget(editor)
    
    # 顯示視窗
    main_window.show()
    
    print("✅ DSM 編輯器已啟動")
    print("🔧 已修正的問題：")
    print("   1. 場景項目重複添加警告")
    print("   2. 拓撲排序循環檢測")
    print("   3. 階層佈局錯誤處理")
    print("")
    print("📝 測試步驟：")
    print("   1. 嘗試創建一些邊線")
    print("   2. 點擊階層佈局按鈕")
    print("   3. 觀察是否還有錯誤訊息")
    
    return app.exec_()

if __name__ == "__main__":
    test_dsm_editor_fixes()
