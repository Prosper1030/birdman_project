"""
正交式佈局演算法模組
Orthogonal Layout Algorithm Module

實現簡單的網格式正交佈局，適用於快速預覽和結構化排列。
"""

from typing import Dict, Tuple, List
import pandas as pd


def layout_orthogonal(
    wbs_df: pd.DataFrame,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150,
    grid_cols: int = 5
) -> Dict[str, Tuple[float, float]]:
    """
    計算正交式（網格）佈局的節點位置。
    
    使用簡單的網格排列，忽略依賴關係，適用於：
    - 快速預覽大量節點
    - 初始佈局參考
    - 當依賴關係過於複雜時的回退選項
    
    Args:
        wbs_df: WBS 資料框，需包含 "Task ID" 欄位
        direction: 佈局方向，"TB"(上到下) 或 "LR"(左到右)
        layer_spacing: 層間距離（像素）
        node_spacing: 同層節點間距離（像素）
        grid_cols: 每行/列的節點數量
    
    Returns:
        節點位置字典 {task_id: (x, y)}
    """
    # 提取任務 ID 列表
    task_ids = []
    for _, row in wbs_df.iterrows():
        task_id = str(row.get("Task ID", f"Task_{_}"))
        task_ids.append(task_id)
    
    if not task_ids:
        return {}
    
    positions = {}
    
    for i, task_id in enumerate(task_ids):
        row = i // grid_cols
        col = i % grid_cols
        
        if direction == "TB":
            # 上到下：x 軸為列，y 軸為行
            x = (col - grid_cols // 2) * node_spacing
            y = row * layer_spacing
        else:  # LR: 左到右
            # 左到右：x 軸為行，y 軸為列
            x = row * layer_spacing
            y = (col - grid_cols // 2) * node_spacing
        
        positions[task_id] = (x, y)
    
    return positions


def layout_orthogonal_with_groups(
    wbs_df: pd.DataFrame,
    groups: Dict[str, List[str]] = None,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150,
    group_spacing: int = 300
) -> Dict[str, Tuple[float, float]]:
    """
    基於分組的正交式佈局。
    
    將節點按給定的分組排列，每組形成一個區域，組間有較大間距。
    適用於按屬性、模組或功能分組的節點排列。
    
    Args:
        wbs_df: WBS 資料框
        groups: 分組字典 {group_name: [task_id1, task_id2, ...]}
        direction: 佈局方向
        layer_spacing: 組內層間距
        node_spacing: 組內節點間距
        group_spacing: 組間間距
    
    Returns:
        節點位置字典 {task_id: (x, y)}
    """
    # 提取任務 ID 列表
    all_task_ids = set()
    for _, row in wbs_df.iterrows():
        task_id = str(row.get("Task ID", f"Task_{_}"))
        all_task_ids.add(task_id)
    
    if not all_task_ids:
        return {}
    
    # 如果沒有提供分組，按屬性自動分組
    if groups is None:
        groups = _auto_group_by_property(wbs_df)
    
    positions = {}
    current_offset = 0
    
    for group_name, task_ids in groups.items():
        # 過濾出實際存在的任務
        valid_task_ids = [tid for tid in task_ids if tid in all_task_ids]
        if not valid_task_ids:
            continue
        
        # 計算該組的佈局
        group_positions = layout_orthogonal(
            pd.DataFrame({'Task ID': valid_task_ids}),
            direction=direction,
            layer_spacing=layer_spacing,
            node_spacing=node_spacing
        )
        
        # 應用組偏移
        for task_id, (x, y) in group_positions.items():
            if direction == "TB":
                positions[task_id] = (x + current_offset, y)
            else:  # LR
                positions[task_id] = (x, y + current_offset)
        
        # 計算下一組的偏移
        if group_positions:
            if direction == "TB":
                group_width = max(abs(pos[0]) for pos in group_positions.values()) * 2 + node_spacing
                current_offset += group_width + group_spacing
            else:  # LR
                group_height = max(abs(pos[1]) for pos in group_positions.values()) * 2 + node_spacing
                current_offset += group_height + group_spacing
    
    # 處理未分組的節點
    ungrouped = all_task_ids - set(task_id for group in groups.values() for task_id in group)
    if ungrouped:
        ungrouped_positions = layout_orthogonal(
            pd.DataFrame({'Task ID': list(ungrouped)}),
            direction=direction,
            layer_spacing=layer_spacing,
            node_spacing=node_spacing
        )
        
        for task_id, (x, y) in ungrouped_positions.items():
            if direction == "TB":
                positions[task_id] = (x + current_offset, y)
            else:  # LR
                positions[task_id] = (x, y + current_offset)
    
    return positions


def _auto_group_by_property(wbs_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    根據 Property 欄位自動分組。
    
    Args:
        wbs_df: WBS 資料框
    
    Returns:
        分組字典 {property: [task_id1, task_id2, ...]}
    """
    groups = {}
    
    for _, row in wbs_df.iterrows():
        task_id = str(row.get("Task ID", f"Task_{_}"))
        prop = str(row.get("Property", "未分類"))
        
        if prop not in groups:
            groups[prop] = []
        groups[prop].append(task_id)
    
    return groups