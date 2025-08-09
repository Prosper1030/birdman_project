#!/usr/bin/env python3
"""
DSM Editor 啟動器
DSM Editor Launcher

用於快速啟動 DSM 編輯器的最小腳本。

使用方式：
    python run_dsm_editor.py                    # 使用預設 sample 資料
    python run_dsm_editor.py --wbs path/to.csv  # 指定 WBS 檔案
    python run_dsm_editor.py --dsm path/to.csv  # 指定 DSM 檔案（未來支援）
    python run_dsm_editor.py --help             # 顯示說明

快速操作指南：
    - 拖曳節點：選中節點（點擊）後拖動
    - 建立連線：從未選中節點拖曳到目標節點
    - 階層式佈局：選單 > 佈局 > 階層式佈局
    - 匯出 DSM：選單 > 檔案 > 匯出 DSM
    - 撤銷/重做：Ctrl+Z / Ctrl+Y
    - 框選：在空白處拖曳
    - 刪除：選中後按 Delete

佈局選項：
    - 階層式：基於依賴關係的分層佈局（Longest-Path）
    - 正交式：網格佈局
    - 力導向：物理模擬佈局

TODO(next):
    - 支援載入 DSM 矩陣
    - 支援命令列參數設定佈局方向
    - 加入批次處理模式
"""

import sys
import os
import argparse
from pathlib import Path

# 將 src 目錄加入 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
from PyQt5.QtWidgets import QApplication, QMessageBox
try:
    from ui.dsm_editor import DsmEditor
except ImportError:
    from src.ui.dsm_editor import DsmEditor


def load_sample_wbs() -> pd.DataFrame:
    """
    載入預設的 sample WBS 資料。
    
    Returns:
        WBS DataFrame
    """
    sample_path = Path(__file__).parent / "sample_data" / "WBS.csv"
    
    if not sample_path.exists():
        print(f"找不到 sample 檔案：{sample_path}")
        print("嘗試其他可能的位置...")
        
        # 嘗試其他可能的路徑
        alternative_paths = [
            Path("sample_data/WBS.csv"),
            Path("sample/WBS.csv"),
            Path("../sample_data/WBS.csv"),
        ]
        
        for alt_path in alternative_paths:
            if alt_path.exists():
                sample_path = alt_path
                print(f"找到檔案：{sample_path}")
                break
        else:
            print("錯誤：找不到任何 sample WBS 檔案")
            return pd.DataFrame()
    
    try:
        # 讀取 CSV，處理可能的編碼問題
        df = pd.read_csv(sample_path, encoding='utf-8-sig')
        print(f"成功載入 {len(df)} 筆任務資料")
        print(f"欄位：{', '.join(df.columns.tolist())}")
        return df
    except UnicodeDecodeError:
        # 嘗試其他編碼
        try:
            df = pd.read_csv(sample_path, encoding='utf-8')
            return df
        except Exception as e:
            print(f"載入檔案失敗：{e}")
            return pd.DataFrame()
    except Exception as e:
        print(f"載入檔案失敗：{e}")
        return pd.DataFrame()


def load_wbs_file(file_path: str) -> pd.DataFrame:
    """
    載入指定的 WBS 檔案。
    
    Args:
        file_path: WBS CSV 檔案路徑
    
    Returns:
        WBS DataFrame
    """
    path = Path(file_path)
    
    if not path.exists():
        print(f"錯誤：檔案不存在 - {path}")
        return pd.DataFrame()
    
    try:
        # 自動偵測編碼
        df = pd.read_csv(path, encoding='utf-8-sig')
        print(f"成功載入 {len(df)} 筆任務資料從 {path}")
        
        # 檢查必要欄位
        required_columns = ["Task ID"]
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            print(f"警告：缺少必要欄位 {missing}")
        
        return df
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(path, encoding='utf-8')
            return df
        except Exception as e:
            print(f"載入檔案失敗（編碼問題）：{e}")
            return pd.DataFrame()
    except Exception as e:
        print(f"載入檔案失敗：{e}")
        return pd.DataFrame()


def load_dsm_file(file_path: str) -> pd.DataFrame:
    """
    載入 DSM 矩陣檔案（未來功能）。
    
    Args:
        file_path: DSM CSV 檔案路徑
    
    Returns:
        DSM DataFrame
    
    TODO(next): 實作 DSM 載入並轉換為 WBS + edges
    """
    print("DSM 載入功能尚未實作")
    return pd.DataFrame()


def create_parser() -> argparse.ArgumentParser:
    """
    建立命令列參數解析器。
    
    Returns:
        ArgumentParser 物件
    """
    parser = argparse.ArgumentParser(
        description="DSM Editor - 視覺化依賴關係編輯器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  %(prog)s                           # 使用預設 sample 資料
  %(prog)s --wbs project.csv        # 載入指定的 WBS 檔案
  %(prog)s --direction LR            # 使用左到右的佈局方向
  
佈局方向選項：
  TB: Top-Bottom (上到下，預設)
  LR: Left-Right (左到右)
  BT: Bottom-Top (下到上) [未來支援]
  RL: Right-Left (右到左) [未來支援]
        """
    )
    
    parser.add_argument(
        '--wbs',
        type=str,
        help='WBS CSV 檔案路徑'
    )
    
    parser.add_argument(
        '--dsm',
        type=str,
        help='DSM CSV 檔案路徑（未來功能）'
    )
    
    parser.add_argument(
        '--direction',
        type=str,
        choices=['TB', 'LR'],
        default='TB',
        help='預設佈局方向（預設：TB）'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='啟用除錯模式'
    )
    
    return parser


def main():
    """主程式進入點。"""
    # 解析命令列參數
    parser = create_parser()
    args = parser.parse_args()
    
    # 除錯模式
    if args.debug:
        print("除錯模式已啟用")
        print(f"參數：{args}")
    
    # 載入資料
    if args.wbs:
        print(f"載入 WBS 檔案：{args.wbs}")
        wbs_df = load_wbs_file(args.wbs)
    elif args.dsm:
        print(f"載入 DSM 檔案：{args.dsm}")
        wbs_df = load_dsm_file(args.dsm)
    else:
        print("使用預設 sample 資料")
        wbs_df = load_sample_wbs()
    
    # 檢查資料
    if wbs_df.empty:
        print("錯誤：無法載入任何資料")
        response = input("是否要繼續開啟空白編輯器？(y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # 建立 Qt 應用程式
    app = QApplication(sys.argv)
    app.setApplicationName("DSM Editor")
    app.setOrganizationName("DSM Tools")
    
    # 設定樣式（選用）
    app.setStyle('Fusion')  # 使用 Fusion 風格獲得更現代的外觀
    
    try:
        # 建立並顯示主視窗
        editor = DsmEditor(wbs_df)
        
        # 儲存佈局方向設定（供編輯器使用）
        editor.default_layout_direction = args.direction
        if args.debug:
            print(f"佈局方向設定為：{args.direction}")
        
        # 顯示視窗
        editor.show()
        
        # 如果有資料，自動執行一次階層式佈局
        if not wbs_df.empty:
            print("執行初始階層式佈局...")
            # 延遲執行以確保視窗已完全顯示
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, editor.applyHierarchicalLayout)
        
        # 執行應用程式
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"錯誤：{e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        
        # 顯示錯誤對話框
        QMessageBox.critical(None, "錯誤", f"無法啟動編輯器：\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()