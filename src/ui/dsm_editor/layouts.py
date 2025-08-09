"""
佈局演算法模組（相容薄包）
Layout Algorithms Module (Compatibility Wrapper)

保持向後相容的匯入包裝，實際實現已移至 layouts 子套件。
"""

# 匯入所有佈局函數以保持相容性
from .layouts import (
    # 階層式佈局
    layout_hierarchical,
    _simple_grid_layout,
    _simple_hierarchical_fallback,
    
    # 正交式佈局
    layout_orthogonal,
    layout_orthogonal_with_groups,
    
    # 力導向佈局
    layout_force_directed,
    layout_force_directed_with_constraints,
    optimize_force_layout,
)

# 向後相容的別名
simple_grid_layout = _simple_grid_layout

__all__ = [
    'layout_hierarchical',
    'layout_orthogonal', 
    'layout_force_directed',
    'simple_grid_layout',
    '_simple_grid_layout',
    '_simple_hierarchical_fallback',
    'layout_orthogonal_with_groups',
    'layout_force_directed_with_constraints',
    'optimize_force_layout',
]