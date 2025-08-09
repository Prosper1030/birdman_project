"""
階層式佈局演算法模組
Hierarchical Layout Algorithm Module

實現基於 Longest-Path 的階層式佈局，保持現有 DSM 編輯器的佈局行為。
"""

from typing import Dict, Tuple, List, Set, Optional
import pandas as pd
import networkx as nx


def layout_hierarchical(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150
) -> Dict[str, Tuple[float, float]]:
    """
    計算階層式佈局的節點位置。
    
    使用改良的 Longest-Path 分層演算法，符合 yEd 風格的層級劃分：
    - 基於拓撲排序的分層
    - 區分源節點（有依賴輸出）與獨立節點（無任何連接）
    - 每層等距擺位
    - 不做 dummy nodes、交叉最小化或壓縮優化
    
    Args:
        wbs_df: WBS 資料框，需包含 "Task ID" 欄位
        edges: 邊的集合，格式為 {(src_id, dst_id), ...}。若為 None，則只做簡單網格佈局
        direction: 佈局方向，"TB"(上到下) 或 "LR"(左到右)
        layer_spacing: 層間距離（像素）
        node_spacing: 同層節點間距離（像素）
    
    Returns:
        節點位置字典 {task_id: (x, y)}
    
    TODO(next): 
        - 支援 dummy nodes 以處理跨層邊
        - 實作交叉最小化演算法
        - 加入節點壓縮以減少空白
        - 支援節點大小考量
    """
    # 提取任務 ID 列表
    task_ids = []
    for _, row in wbs_df.iterrows():
        task_id = str(row.get("Task ID", f"Task_{_}"))
        task_ids.append(task_id)
    
    if not task_ids:
        return {}
    
    # 如果沒有邊，使用簡單網格佈局
    if not edges:
        return _simple_grid_layout(task_ids, node_spacing, layer_spacing, direction)
    
    # 建立有向圖
    graph = nx.DiGraph()
    for task_id in task_ids:
        graph.add_node(task_id)
    for src, dst in edges:
        if src in task_ids and dst in task_ids:
            graph.add_edge(src, dst)
    
    # 檢查是否有循環
    if not nx.is_directed_acyclic_graph(graph):
        print("警告：圖形包含循環，退回到簡單階層佈局")
        return _simple_hierarchical_fallback(task_ids, edges, layer_spacing, node_spacing, direction)
    
    # 計算每個節點的層級（Longest-Path）
    layers = _compute_layers_longest_path(graph)
    
    # 將節點按層級分組
    level_groups = {}
    for node, level in layers.items():
        if level not in level_groups:
            level_groups[level] = []
        level_groups[level].append(node)
    
    # 計算節點位置（考慮獨立節點層 -1）
    positions = {}
    
    # 獲取正常層級範圍
    normal_levels = [level for level in level_groups.keys() if level >= 0]
    max_normal_level = max(normal_levels) if normal_levels else -1
    
    for level, nodes in sorted(level_groups.items()):
        # 計算該層的實際位置
        if level == -1:
            # 獨立節點放在所有正常層級之後
            actual_level = max_normal_level + 2
        else:
            actual_level = level
            
        # 計算該層的位置
        if direction == "TB":  # Top-Bottom
            y = actual_level * layer_spacing
            start_x = -(len(nodes) - 1) * node_spacing / 2
            for i, node_id in enumerate(nodes):
                x = start_x + i * node_spacing
                positions[node_id] = (x, y)
        else:  # LR: Left-Right
            x = actual_level * layer_spacing
            start_y = -(len(nodes) - 1) * node_spacing / 2
            for i, node_id in enumerate(nodes):
                y = start_y + i * node_spacing
                positions[node_id] = (x, y)
    
    # 補充未在圖中的節點（完全不在邊集合中的節點）
    for task_id in task_ids:
        if task_id not in positions:
            # 放在獨立節點層
            isolated_level = max_normal_level + 2
            if direction == "TB":
                positions[task_id] = (0, isolated_level * layer_spacing)
            else:
                positions[task_id] = (isolated_level * layer_spacing, 0)
    
    return positions


def _compute_layers_longest_path(graph: nx.DiGraph) -> Dict[str, int]:
    """
    使用改良的 Longest-Path 演算法計算節點層級。
    
    改良版本區分兩種無前驅節點的情況：
    1. 源節點：有後繼節點但無前驅節點（提供依賴） → 第 0 層
    2. 獨立節點：既無前驅也無後繼節點（完全獨立） → 獨立層 (-1)
    
    Args:
        graph: NetworkX 有向無環圖
    
    Returns:
        節點層級字典 {node_id: layer}，其中 -1 表示獨立節點層
    """
    layers = {}
    
    # 拓撲排序
    try:
        topo_order = list(nx.topological_sort(graph))
    except nx.NetworkXError:
        # 如果有循環，返回空字典
        return {}
    
    # 預先識別獨立節點（既無前驅也無後繼）
    isolated_nodes = set()
    for node in graph.nodes():
        if graph.in_degree(node) == 0 and graph.out_degree(node) == 0:
            isolated_nodes.add(node)
    
    # 計算每個節點的最大路徑長度
    for node in topo_order:
        if node in isolated_nodes:
            # 獨立節點放在特殊層 (-1)
            layers[node] = -1
        else:
            predecessors = list(graph.predecessors(node))
            if not predecessors:
                # 源節點：有後繼但無前驅，放在第 0 層
                layers[node] = 0
            else:
                # 放在所有前驅節點的下一層
                layers[node] = max(layers[pred] for pred in predecessors) + 1
    
    return layers


def _simple_grid_layout(
    task_ids: List[str],
    node_spacing: int,
    layer_spacing: int,
    direction: str
) -> Dict[str, Tuple[float, float]]:
    """
    簡單網格佈局，用於沒有邊的情況。
    
    Args:
        task_ids: 任務 ID 列表
        node_spacing: 節點間距
        layer_spacing: 層間距
        direction: 佈局方向
    
    Returns:
        節點位置字典
    """
    positions = {}
    cols = 5  # 每行/列 5 個節點
    
    for i, task_id in enumerate(task_ids):
        row = i // cols
        col = i % cols
        
        if direction == "TB":
            x = (col - cols // 2) * node_spacing
            y = row * layer_spacing
        else:  # LR
            x = row * layer_spacing
            y = (col - cols // 2) * node_spacing
        
        positions[task_id] = (x, y)
    
    return positions


def _simple_hierarchical_fallback(
    task_ids: List[str],
    edges: Set[Tuple[str, str]],
    layer_spacing: int,
    node_spacing: int,
    direction: str
) -> Dict[str, Tuple[float, float]]:
    """
    簡單階層式佈局備用方案，用於有循環的圖。
    
    將節點分成幾層，盡量減少回邊。
    
    Args:
        task_ids: 任務 ID 列表
        edges: 邊的集合
        layer_spacing: 層間距
        node_spacing: 節點間距
        direction: 佈局方向
    
    Returns:
        節點位置字典
    """
    positions = {}
    nodes_per_level = 4
    
    for i, task_id in enumerate(task_ids):
        level = i // nodes_per_level
        pos_in_level = i % nodes_per_level
        
        if direction == "TB":
            start_x = -(nodes_per_level - 1) * node_spacing / 2
            x = start_x + pos_in_level * node_spacing
            y = level * layer_spacing
        else:  # LR
            start_y = -(nodes_per_level - 1) * node_spacing / 2
            x = level * layer_spacing
            y = start_y + pos_in_level * node_spacing
        
        positions[task_id] = (x, y)
    
    return positions


def optimize_crossing_reduction(
    positions: Dict[str, Tuple[float, float]],
    edges: Set[Tuple[str, str]],
    iterations: int = 10
) -> Dict[str, Tuple[float, float]]:
    """
    交叉最小化優化（骨架，尚未實作）。
    
    TODO(next): 實作基於重心法或中位數法的交叉最小化
    
    Args:
        positions: 現有節點位置
        edges: 邊的集合
        iterations: 迭代次數
    
    Returns:
        優化後的節點位置
    """
    # TODO: 實作交叉最小化演算法
    # 1. 按層分組節點
    # 2. 對每層計算節點順序以最小化與上/下層的交叉
    # 3. 迭代優化直到收斂或達到最大迭代次數
    
    return positions  # 暫時直接返回原始位置


def add_dummy_nodes(
    positions: Dict[str, Tuple[float, float]],
    edges: Set[Tuple[str, str]]
) -> Tuple[Dict[str, Tuple[float, float]], Set[Tuple[str, str]]]:
    """
    添加虛擬節點以處理跨層邊（骨架，尚未實作）。
    
    TODO(next): 實作虛擬節點插入演算法
    
    Args:
        positions: 節點位置
        edges: 原始邊集合
    
    Returns:
        (包含虛擬節點的位置字典, 更新後的邊集合)
    """
    # TODO: 實作虛擬節點演算法
    # 1. 檢測跨層邊（跨越多於一層的邊）
    # 2. 在中間層插入虛擬節點
    # 3. 將原始邊分割成多段
    
    return positions, edges  # 暫時直接返回原始資料


def compact_layout(
    positions: Dict[str, Tuple[float, float]],
    node_sizes: Dict[str, Tuple[float, float]] = None
) -> Dict[str, Tuple[float, float]]:
    """
    壓縮佈局以減少空白（骨架，尚未實作）。
    
    TODO(next): 實作佈局壓縮演算法
    
    Args:
        positions: 節點位置
        node_sizes: 節點大小字典 {node_id: (width, height)}
    
    Returns:
        壓縮後的節點位置
    """
    # TODO: 實作佈局壓縮
    # 1. 考慮節點實際大小
    # 2. 在不造成重疊的情況下移動節點
    # 3. 最小化總體佈局面積
    
    return positions  # 暫時直接返回原始位置
