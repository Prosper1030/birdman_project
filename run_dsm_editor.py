#!/usr/bin/env python3
"""
DSM Editor 快速啟動器
Quick DSM Editor Launcher

這是一個簡單的啟動器，會調用 tests 目錄中的完整測試工具。

使用方式：
    python run_dsm_editor.py                    # 使用預設 sample 資料
    python run_dsm_editor.py --wbs path/to.csv  # 指定 WBS 檔案
    python run_dsm_editor.py --help             # 顯示說明
"""

import sys
import subprocess
from pathlib import Path

def main():
    """轉發所有參數到 tests 目錄中的完整版本"""
    test_launcher = Path(__file__).parent / "tests" / "run_dsm_editor.py"
    
    if not test_launcher.exists():
        print(f"錯誤：找不到測試啟動器 {test_launcher}")
        return 1
    
    # 轉發所有命令列參數
    cmd = [sys.executable, str(test_launcher)] + sys.argv[1:]
    
    try:
        # 使用 subprocess 執行，保持當前工作目錄
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode
    except Exception as e:
        print(f"啟動 DSM Editor 失敗：{e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())