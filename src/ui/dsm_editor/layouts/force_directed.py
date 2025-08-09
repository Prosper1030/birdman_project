"""
力導向佈局演算法模組
Force-Directed Layout Algorithm Module

使用物理模擬的力導向演算法，適用於展示節點間的自然關係和群聚。
"""

from typing import Dict, Tuple, Set, Optional
import pandas as pd
import networkx as nx
import math


def layout_force_directed(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    iterations: int = 100,
    k_spring: float = 1.0,
    k_repulsion: float = 1.0,
    damping: float = 0.9,
    scale: int = 300,
    seed: Optional[int] = None
) -> Dict[str, Tuple[float, float]]:
    """
    計算力導向佈局的節點位置。
    
    使用 Fruchterman-Reingold 演算法的簡化版本，透過彈簧力和排斥力
    的平衡來達到自然的節點分佈。
    
    Args:
        wbs_df: WBS 資料框，需包含 "Task ID" 欄位
        edges: 邊的集合，格式為 {(src_id, dst_id), ...}
        iterations: 迭代次數，越多越精確但計算越慢
        k_spring: 彈簧力係數，越大連接節點越緊密
        k_repulsion: 排斥力係數，越大節點間越分散
        damping: 阻尼係數，控制系統收斂速度
        scale: 佈局縮放係數，控制整體大小
        seed: 隨機種子，確保結果可重現
    
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
    
    # 如果只有一個節點，放在原點
    if len(task_ids) == 1:
        return {task_ids[0]: (0.0, 0.0)}
    
    # 如果沒有邊，使用簡單的力導向佈局
    if not edges:
        return _simple_force_layout(task_ids, scale=scale, seed=seed)
    
    # 建立圖形
    try:
        # 使用 NetworkX 的 spring_layout (Fruchterman-Reingold 演算法)
        graph = nx.Graph()  # 使用無向圖以獲得更好的力平衡
        
        for task_id in task_ids:
            graph.add_node(task_id)
        
        for src, dst in edges:
            if src in task_ids and dst in task_ids:
                graph.add_edge(src, dst)
        
        # 計算佈局 - 調整參數以適應節點數量
        node_count = len(task_ids)
        
        # 根據節點數量調整參數
        adjusted_k = k_spring / max(1, node_count ** 0.5)  # 節點多時減小 k 值
        adjusted_scale = scale * max(1, node_count ** 0.3)  # 節點多時增大 scale
        
        pos_dict = nx.spring_layout(
            graph,
            iterations=iterations,
            k=adjusted_k,
            scale=adjusted_scale,
            seed=seed
        )
        
        # 轉換為所需格式
        positions = {}
        for task_id in task_ids:
            if task_id in pos_dict:
                x, y = pos_dict[task_id]
                positions[task_id] = (float(x), float(y))
            else:
                # 孤立節點放在邊緣
                positions[task_id] = (scale * 1.2, 0.0)
        
        return positions
        
    except Exception as e:
        print(f"力導向佈局計算失敗: {e}")
        # 回退到簡單佈局
        return _simple_force_layout(task_ids, scale=scale, seed=seed)


def layout_force_directed_with_constraints(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    fixed_nodes: Dict[str, Tuple[float, float]] = None,
    iterations: int = 100,
    scale: int = 300,
    seed: Optional[int] = None
) -> Dict[str, Tuple[float, float]]:
    """
    帶約束的力導向佈局。
    
    允許某些節點固定在指定位置，其他節點圍繞它們進行力導向佈局。
    適用於有重要核心節點或需要保持某些節點位置的情況。
    
    Args:
        wbs_df: WBS 資料框
        edges: 邊的集合
        fixed_nodes: 固定節點位置 {task_id: (x, y)}
        iterations: 迭代次數
        scale: 佈局縮放係數
        seed: 隨機種子
    
    Returns:
        節點位置字典 {task_id: (x, y)}
    """
    task_ids = []
    for _, row in wbs_df.iterrows():
        task_id = str(row.get("Task ID", f"Task_{_}"))
        task_ids.append(task_id)
    
    if not task_ids:
        return {}
    
    if fixed_nodes is None:
        fixed_nodes = {}
    
    try:
        # 建立圖形
        graph = nx.Graph()
        for task_id in task_ids:
            graph.add_node(task_id)
        
        if edges:
            for src, dst in edges:
                if src in task_ids and dst in task_ids:
                    graph.add_edge(src, dst)
        
        # 使用 NetworkX 的帶約束佈局
        pos_dict = nx.spring_layout(
            graph,
            pos=fixed_nodes,  # 固定節點的初始位置
            fixed=list(fixed_nodes.keys()),  # 固定的節點列表
            iterations=iterations,
            scale=scale,
            seed=seed
        )
        
        # 轉換為所需格式
        positions = {}
        for task_id in task_ids:
            if task_id in pos_dict:
                x, y = pos_dict[task_id]
                positions[task_id] = (float(x), float(y))
            else:
                positions[task_id] = (scale * 1.2, 0.0)
        
        return positions
        
    except Exception as e:
        print(f"約束力導向佈局計算失敗: {e}")
        # 回退到基礎力導向佈局
        return layout_force_directed(wbs_df, edges, scale=scale, seed=seed)


def _simple_force_layout(
    task_ids: list,
    scale: int = 300,
    seed: Optional[int] = None
) -> Dict[str, Tuple[float, float]]:
    """
    簡單的力導向佈局，用於沒有邊的情況。
    
    將節點以圓形或螺旋狀分佈，避免重疊。
    
    Args:
        task_ids: 任務 ID 列表
        scale: 佈局縮放係數
        seed: 隨機種子
    
    Returns:
        節點位置字典
    """
    if seed is not None:
        import random
        random.seed(seed)
    
    positions = {}
    n = len(task_ids)
    
    if n == 1:
        positions[task_ids[0]] = (0.0, 0.0)
    elif n <= 8:
        # 少量節點：圓形排列
        for i, task_id in enumerate(task_ids):
            angle = 2 * math.pi * i / n
            radius = scale * 0.8
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            positions[task_id] = (x, y)
    else:
        # 大量節點：阿基米德螺旋排列
        for i, task_id in enumerate(task_ids):
            t = i * 0.5  # 螺旋參數
            radius = scale * 0.1 * t
            angle = 2 * math.pi * t * 0.2
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            positions[task_id] = (x, y)
    
    return positions


def optimize_force_layout(
    positions: Dict[str, Tuple[float, float]],
    edges: Set[Tuple[str, str]],
    iterations: int = 50
) -> Dict[str, Tuple[float, float]]:
    """
    對現有佈局進行力導向優化。
    
    在已有位置的基礎上進行微調，適用於對現有佈局進行局部優化。
    
    Args:
        positions: 初始位置
        edges: 邊的集合
        iterations: 優化迭代次數
    
    Returns:
        優化後的位置
    """
    if not positions or not edges:
        return positions
    
    try:
        # 建立圖形
        graph = nx.Graph()
        task_ids = list(positions.keys())
        
        for task_id in task_ids:
            graph.add_node(task_id)
        
        for src, dst in edges:
            if src in task_ids and dst in task_ids:
                graph.add_edge(src, dst)
        
        # 使用現有位置作為起點
        initial_pos = {task_id: pos for task_id, pos in positions.items()}
        
        # 進行優化
        optimized_pos = nx.spring_layout(
            graph,
            pos=initial_pos,
            iterations=iterations,
            k=1.0,
            scale=None  # 保持現有縮放
        )
        
        # 轉換為所需格式
        result = {}
        for task_id in task_ids:
            if task_id in optimized_pos:
                x, y = optimized_pos[task_id]
                result[task_id] = (float(x), float(y))
            else:
                result[task_id] = positions[task_id]
        
        return result
        
    except Exception as e:
        print(f"佈局優化失敗: {e}")
        return positions