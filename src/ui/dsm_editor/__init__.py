"""DSM 編輯器模組化架構

重構說明：
- 原始的 dsm_editor.py 文件已拆分為多個模組，提高代碼可維護性
- 主要入口為 DsmEditor 類，從 main_editor 模組導出

模組結構：
- main_editor.py: DsmEditor 主編輯器類
- scene.py: DsmScene 場景管理
- view.py: CanvasView 視圖組件  
- nodes.py: TaskNode 節點相關類
- edges.py: EdgeItem, GlowArrowHead 邊線相關類
- commands.py: 命令模式相關類
- handles.py: ResizeHandle 調整手柄
- routing.py: 簡單邊線路由器
- advanced_routing.py: 高級路由引擎
- enums.py: 枚舉和常量定義
"""

from .main_editor import DsmEditor
from .enums import EditorState, LayoutAlgorithm
from .nodes import TaskNode
from .edges import EdgeItem, GlowArrowHead
from .scene import DsmScene
from .view import CanvasView
from .commands import (
    Command, AddNodeCommand, AddEdgeCommand, 
    RemoveEdgeCommand, MoveNodeCommand, ResizeNodeCommand
)
from .handles import ResizeHandle
from .routing import SimpleEdgeRouter

__all__ = [
    # 主要類別
    'DsmEditor',
    
    # 枚舉
    'EditorState', 'LayoutAlgorithm',
    
    # UI 組件
    'TaskNode', 'EdgeItem', 'GlowArrowHead',
    'DsmScene', 'CanvasView', 'ResizeHandle',
    
    # 路由功能
    'SimpleEdgeRouter',
    
    # 命令模式
    'Command', 'AddNodeCommand', 'AddEdgeCommand',
    'RemoveEdgeCommand', 'MoveNodeCommand', 'ResizeNodeCommand'
]