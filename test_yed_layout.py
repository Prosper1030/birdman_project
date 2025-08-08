#!/usr/bin/env python3
"""
測試 yEd 風格布局系統
"""

import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication
from src.ui.dsm_editor import DsmEditor


def create_test_data():
    """創建測試資料"""
    # 創建測試 WBS 資料
    data = {
        'Task ID': ['A26-001', 'A26-002', 'A26-003', 'A26-004', 'A26-005', 
                   'A26-006', 'A26-007', 'A26-008', 'A26-009', 'A26-010'],
        'Name': ['需求分析', '系統設計', '資料庫設計', '前端開發', '後端開發',
                '單元測試', '整合測試', '系統測試', '部署準備', '上線發布'],
        'TRF': [0.3, 0.5, 0.4, 0.6, 0.7, 0.3, 0.4, 0.5, 0.3, 0.2],
        'Property': ['A', 'D', 'D', 'C', 'C', 'T', 'T', 'T', 'O', 'O'],
        'Te_newbie': [40, 60, 30, 80, 100, 20, 30, 40, 20, 10]
    }
    
    return pd.DataFrame(data)


def main():
    """主程式"""
    app = QApplication(sys.argv)
    
    # 創建測試資料
    wbs_df = create_test_data()
    
    # 創建編輯器
    editor = DsmEditor(wbs_df)
    
    # 手動添加一些依賴關係以測試布局
    if hasattr(editor, 'nodes'):
        # 添加一些測試邊線
        test_edges = [
            ('A26-001', 'A26-002'),  # 需求分析 -> 系統設計
            ('A26-002', 'A26-003'),  # 系統設計 -> 資料庫設計
            ('A26-002', 'A26-004'),  # 系統設計 -> 前端開發
            ('A26-002', 'A26-005'),  # 系統設計 -> 後端開發
            ('A26-003', 'A26-005'),  # 資料庫設計 -> 後端開發
            ('A26-004', 'A26-006'),  # 前端開發 -> 單元測試
            ('A26-005', 'A26-006'),  # 後端開發 -> 單元測試
            ('A26-006', 'A26-007'),  # 單元測試 -> 整合測試
            ('A26-007', 'A26-008'),  # 整合測試 -> 系統測試
            ('A26-008', 'A26-009'),  # 系統測試 -> 部署準備
            ('A26-009', 'A26-010'),  # 部署準備 -> 上線發布
        ]
        
        for src_id, dst_id in test_edges:
            if src_id in editor.nodes and dst_id in editor.nodes:
                src_node = editor.nodes[src_id]
                dst_node = editor.nodes[dst_id]
                # 使用 AddEdgeCommand 添加邊線
                from src.ui.dsm_editor import AddEdgeCommand
                command = AddEdgeCommand(editor, src_node, dst_node)
                command.execute()
    
    # 顯示編輯器
    editor.show()
    
    # 測試不同的布局
    print("測試 yEd 布局功能...")
    print("可以使用以下布局選項：")
    print("- 佈局選單：階層式、正交式、力導向")
    print("- yEd 布局：yEd 階層、yEd 樹狀、yEd 環形")
    print("- 快捷鍵：Ctrl+Z (撤銷), Ctrl+Y (重做)")
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()