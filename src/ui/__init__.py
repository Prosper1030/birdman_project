"""UI 模組架構

整合了兩大 UI 功能：
- 主應用程式：多求解器主頁面
- DSM 編輯器：依賴關係視覺化編輯
- 共用組件：通用 UI 工具
"""

# 主應用程式
from .main_app import MainWindow, MonteCarloWorker

# DSM 編輯器
from .dsm_editor import DsmEditor

# 共用組件
from .shared import PandasModel, SelectionStyleManager

__all__ = [
    # 主應用程式
    "MainWindow", 
    "MonteCarloWorker",
    
    # DSM 編輯器
    "DsmEditor",
    
    # 共用組件
    "PandasModel", 
    "SelectionStyleManager"
]
