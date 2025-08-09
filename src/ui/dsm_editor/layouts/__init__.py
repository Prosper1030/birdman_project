"""
佈局演算法套件
Layout Algorithms Package

包含多種圖形佈局演算法，支援不同的視覺化需求：
- 階層式佈局：基於依賴關係的分層排列
- 正交式佈局：網格式整齊排列
- 力導向佈局：物理模擬的自然分佈
"""

from .hierarchical import (
    layout_hierarchical,
    _simple_grid_layout,
    _simple_hierarchical_fallback
)
from .orthogonal import (
    layout_orthogonal,
    layout_orthogonal_with_groups
)
from .force_directed import (
    layout_force_directed,
    layout_force_directed_with_constraints,
    optimize_force_layout
)

__all__ = [
    # 階層式佈局
    'layout_hierarchical',
    '_simple_grid_layout',
    '_simple_hierarchical_fallback',
    
    # 正交式佈局
    'layout_orthogonal',
    'layout_orthogonal_with_groups',
    
    # 力導向佈局
    'layout_force_directed',
    'layout_force_directed_with_constraints',
    'optimize_force_layout',
]
