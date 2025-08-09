#!/usr/bin/env python3
"""
yEd 風格階層佈局演示腳本

展示新實現的專業級階層佈局功能：
- 方向限制 (TB/LR)
- 孤立節點處理
- 層級分配
- 佈局參數配置
"""

import sys
import pandas as pd
from PyQt5.QtWidgets import QApplication
from src.ui.dsm_editor.main_editor import DsmEditor

def create_demo_data():
    """創建演示用的 WBS 數據"""
    tasks = [
        {'Task ID': 'A', 'Name': '需求分析'},
        {'Task ID': 'B', 'Name': '系統設計'},
        {'Task ID': 'C', 'Name': '編碼實現'},
        {'Task ID': 'D', 'Name': '單元測試'},
        {'Task ID': 'E', 'Name': '整合測試'},
        {'Task ID': 'F', 'Name': '部署上線'},
        {'Task ID': 'G', 'Name': '文檔編寫'},  # 孤立節點
        {'Task ID': 'H', 'Name': '培訓材料'},  # 孤立節點
    ]
    return pd.DataFrame(tasks)

def demo_hierarchical_layouts():
    """演示階層佈局功能"""
    print("=== yEd 風格階層佈局演示 ===\n")
    
    # 創建應用程序
    app = QApplication(sys.argv)
    
    # 創建演示數據
    wbs_df = create_demo_data()
    
    # 創建編輯器
    editor = DsmEditor(wbs_df)
    editor.show()
    
    # 添加一些依賴邊
    edges_to_add = [
        ('A', 'B'),  # 需求分析 -> 系統設計
        ('B', 'C'),  # 系統設計 -> 編碼實現  
        ('C', 'D'),  # 編碼實現 -> 單元測試
        ('D', 'E'),  # 單元測試 -> 整合測試
        ('E', 'F'),  # 整合測試 -> 部署上線
        ('A', 'G'),  # 需求分析 -> 文檔編寫 (會讓G不再孤立)
    ]
    
    for src, dst in edges_to_add:
        if src in editor.nodes and dst in editor.nodes:
            editor.edges.add((src, dst))
            # 這裡可以添加視覺邊線，但為了演示簡單起見先省略
    
    print(f"已載入 {len(editor.nodes)} 個節點")
    print(f"已添加 {len(editor.edges)} 條依賴邊")
    print(f"孤立節點: H (培訓材料)")
    print()
    
    # 演示不同佈局方向
    print("1. 測試 TB (上到下) 佈局...")
    editor.setLayoutDirection('TB')
    editor.applyHierarchicalLayout()
    print("   TB 佈局完成")
    print()
    
    print("2. 測試 LR (左到右) 佈局...")
    editor.setLayoutDirection('LR')
    editor.applyHierarchicalLayout()
    print("   LR 佈局完成")
    print()
    
    # 演示佈局參數調整
    print("3. 測試自定義佈局參數...")
    editor.setLayoutSpacing(
        layer_spacing=300,    # 增加層間距
        node_spacing=200,     # 增加節點間距
        isolated_spacing=120  # 調整孤立節點間距
    )
    editor.applyHierarchicalLayout()
    print("   自定義參數佈局完成")
    print()
    
    # 演示路由功能
    print("4. 測試正交路由...")
    editor.enableOrthogonalRouting(True)
    print("   正交路由已啟用")
    print()
    
    print("=== 演示完成 ===")
    print()
    print("功能說明:")
    print("- 孤立節點 (H) 會根據方向放置在指定位置")
    print("- TB模式：孤立節點在左側，依賴節點在右側")
    print("- LR模式：孤立節點在上方，依賴節點在下方")  
    print("- 佈局參數可以動態調整")
    print("- 支援先佈局後路由的專業流程")
    print()
    print("菜單操作:")
    print("- 佈局 > 佈局方向：切換 TB/LR")
    print("- 佈局 > 啟用正交路由：切換路由模式")
    print("- 佈局 > 階層式佈局：重新執行佈局")
    
    # 運行應用程序
    sys.exit(app.exec_())

if __name__ == "__main__":
    demo_hierarchical_layouts()
