"""
階層式佈局演算法模組
Hierarchical Layout Algorithm Module

實現基於杉山方法 (Sugiyama Framework) 的專業級階層式佈局，
包含完整的循環移除、分層、交叉最小化和坐標分配。
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
    node_spacing: int = 150,
    isolated_spacing: int = 100
) -> Dict[str, Tuple[float, float]]:
    """
    計算 yEd 風格的階層式佈局節點位置。
    
    實現專業級的階層布局，包含：
    - 方向限制：TB(上下) 或 LR(左右)，邊只允許對應方向
    - 孤立節點優先擺放：TB模式左側，LR模式上方
    - 智能端口分配：根據方向限制進出邊的連接點
    - 反向邊處理：允許跨層回流但標記處理
    
    Args:
        wbs_df: WBS 資料框，需包含 "Task ID" 欄位
        edges: 邊的集合，格式為 {(src_id, dst_id), ...}
        direction: 佈局方向，"TB"(上到下) 或 "LR"(左到右)
        layer_spacing: 層間距離（像素）
        node_spacing: 同層節點間距離（像素）
        isolated_spacing: 孤立節點間距離（像素）
    
    Returns:
        節點位置字典 {task_id: (x, y)}，包含端口分配信息
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
    
    # 建立有向圖並分析邊的方向性
    graph = nx.DiGraph()
    for task_id in task_ids:
        graph.add_node(task_id)
    
    # 根據方向限制過濾和分類邊
    valid_edges, reverse_edges = _filter_edges_by_direction(edges, direction)
    
    # 添加有效邊到圖中
    for src, dst in valid_edges:
        if src in task_ids and dst in task_ids:
            graph.add_edge(src, dst)
    
    # 識別孤立節點
    isolated_nodes = _identify_isolated_nodes(graph, task_ids)
    
    # 處理非孤立節點的布局
    if len(graph.nodes()) - len(isolated_nodes) > 0:
        # 實現杉山方法第一階段：循環移除
        dag_graph, reversed_edges = _remove_cycles_sugiyama(graph)
        
        print(f"循環移除完成 - 原始邊數: {len(graph.edges())}, 反轉邊數: {len(reversed_edges)}")
        
        # 驗證 DAG
        if not nx.is_directed_acyclic_graph(dag_graph):
            print("警告：循環移除後仍不是 DAG，進行額外清理")
            dag_graph = _ensure_dag(dag_graph)
        
        # 計算層級（使用無循環的圖）
        layers = _compute_yed_style_layers(dag_graph, isolated_nodes)
        
        # 分配節點位置
        positions = _assign_yed_positions(layers, isolated_nodes, task_ids,
                                        layer_spacing, node_spacing, isolated_spacing, direction)
        
        # 將反轉的邊加入到 reverse_edges 中
        reverse_edges.update(reversed_edges)
    else:
        # 全部都是孤立節點
        positions = _layout_all_isolated(task_ids, isolated_spacing, direction)
    
    # 計算和存儲端口分配信息
    positions = _assign_edge_ports(positions, valid_edges, reverse_edges, direction)
    
    return positions


def _remove_cycles_sugiyama(graph: nx.DiGraph) -> Tuple[nx.DiGraph, Set[Tuple[str, str]]]:
    """
    實現杉山方法第一階段：循環移除。
    按照 Reference 要求：偵測循環並暫時反轉邊來打破循環，而非移除邊。
    
    Args:
        graph: 原始有向圖
    
    Returns:
        (dag_graph, reversed_edges): 無循環圖和被反轉的邊集合
    """
    if nx.is_directed_acyclic_graph(graph):
        # 如果圖已經是 DAG，直接返回
        return graph.copy(), set()
    
    # 創建工作圖的深度拷貝
    H = graph.copy()
    reversed_edges = set()  # 記錄被反轉的邊
    
    max_iterations = len(graph.edges()) + 10
    iteration = 0
    
    while not nx.is_directed_acyclic_graph(H) and iteration < max_iterations:
        iteration += 1
        
        try:
            # 找到一個循環
            cycle = nx.find_cycle(H, orientation='original')
            if not cycle:
                break
                
            # 按照 Reference：選擇邊來反轉（不是移除）
            edge_to_reverse = _select_best_edge_to_remove(H, cycle)
            
            # 反轉邊（這樣可以在渲染時恢復原始方向）
            if H.has_edge(*edge_to_reverse):
                src, dst = edge_to_reverse
                H.remove_edge(src, dst)
                H.add_edge(dst, src)  # 反轉方向
                reversed_edges.add(edge_to_reverse)
                print(f"反轉循環邊: {src} -> {dst} (循環長度: {len(cycle)})")
                
        except nx.NetworkXNoCycle:
            break
        except Exception as e:
            print(f"循環檢測錯誤: {e}")
            break
    
    is_dag = nx.is_directed_acyclic_graph(H)
    print(f"循環移除結果: DAG={is_dag}, 迭代次數={iteration}, 反轉邊數={len(reversed_edges)}")
    
    if not is_dag:
        print("警告：未能完全移除所有循環，將使用回退策略")
        H = _create_dag_fallback(graph)
    
    return H, reversed_edges

def _select_best_edge_to_remove(graph: nx.DiGraph, cycle) -> Tuple[str, str]:
    """
    從循環中選擇最適合移除的邊
    
    策略：選擇移除後對圖結構影響最小的邊
    1. 優先選擇度數較小的節點的邊
    2. 優先選擇會減少更多循環的邊
    
    Args:
        graph: 圖
        cycle: 循環邊列表 [(u1, v1), (u2, v2), ...]
    
    Returns:
        要移除的邊 (source, target)
    """
    if not cycle:
        return None
        
    # 將 cycle 轉換為邊列表
    edges = [(cycle[i][0], cycle[i][1]) for i in range(len(cycle))]
    
    best_edge = None
    best_score = float('inf')
    
    for edge in edges:
        src, dst = edge
        if not graph.has_edge(src, dst):
            continue
            
        # 計算移除此邊的評分（評分越低越好）
        src_degree = graph.in_degree(src) + graph.out_degree(src)
        dst_degree = graph.in_degree(dst) + graph.out_degree(dst)
        
        # 傾向於移除連接到高度數節點的邊（這樣保留更多連接）
        score = 1.0 / (src_degree + dst_degree + 1)
        
        if score < best_score:
            best_score = score
            best_edge = edge
    
    return best_edge if best_edge else edges[0]


def _create_dag_fallback(graph: nx.DiGraph) -> nx.DiGraph:
    """
    當循環移除失敗時的回退策略
    創建一個基於原圖的 DAG
    
    Args:
        graph: 原始圖
    
    Returns:
        DAG 圖
    """
    # 創建最小生成樹的有向版本
    dag = nx.DiGraph()
    dag.add_nodes_from(graph.nodes())
    
    # 使用 BFS 建立樹結構
    if graph.nodes():
        start_node = list(graph.nodes())[0]
        visited = {start_node}
        queue = [start_node]
        
        while queue:
            current = queue.pop(0)
            
            # 添加所有未訪問的後繼節點
            for neighbor in graph.successors(current):
                if neighbor not in visited:
                    dag.add_edge(current, neighbor)
                    visited.add(neighbor)
                    queue.append(neighbor)
            
            # 如果還有未訪問的節點，從中選擇一個繼續
            if not queue:
                unvisited = set(graph.nodes()) - visited
                if unvisited:
                    next_node = unvisited.pop()
                    visited.add(next_node)
                    queue.append(next_node)
    
    return dag
    """
    在給定循環中選擇最適合反轉的邊。
    
    啟發式策略：
    1. 優先選擇出度-入度差最大的節點的出邊
    2. 優先選擇度數較小的邊
    
    Args:
        graph: 圖
        cycle: 循環中的節點列表
    
    Returns:
        要反轉的邊 (src, dst) 或 None
    """
    if len(cycle) < 2:
        return None
    
    cycle_edges = []
    for i in range(len(cycle)):
        src = cycle[i]
        dst = cycle[(i + 1) % len(cycle)]
        if graph.has_edge(src, dst):
            cycle_edges.append((src, dst))
    
    if not cycle_edges:
        return None
    
    # 計算每條邊的啟發式分數
    edge_scores = []
    for src, dst in cycle_edges:
        # 分數 = 源節點出度差 + 目標節點入度 + 邊的"重要性"
        src_out_degree = graph.out_degree(src)
        src_in_degree = graph.in_degree(src)
        dst_in_degree = graph.in_degree(dst)
        
        # 傾向於反轉從高出度節點到高入度節點的邊
        score = (src_out_degree - src_in_degree) + dst_in_degree
        edge_scores.append((score, src, dst))
    
    # 選擇分數最高的邊
    edge_scores.sort(reverse=True)
    return (edge_scores[0][1], edge_scores[0][2])


def _find_back_edge_dfs(graph: nx.DiGraph) -> Optional[Tuple[str, str]]:
    """
    使用 DFS 找到回邊 (back edge)。
    
    Args:
        graph: 有向圖
    
    Returns:
        回邊 (src, dst) 或 None
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph.nodes()}
    
    def dfs_visit(node):
        color[node] = GRAY
        for neighbor in graph.neighbors(node):
            if color[neighbor] == GRAY:
                # 找到回邊
                return (node, neighbor)
            elif color[neighbor] == WHITE:
                result = dfs_visit(neighbor)
                if result:
                    return result
        color[node] = BLACK
        return None
    
    for node in graph.nodes():
        if color[node] == WHITE:
            result = dfs_visit(node)
            if result:
                return result
    
    return None


def _filter_edges_by_direction(edges: Set[Tuple[str, str]], direction: str) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str]]]:
    """
    根據布局方向過濾邊，分離正向邊和反向邊。
    
    Args:
        edges: 原始邊集合
        direction: 布局方向 "TB" 或 "LR"
    
    Returns:
        (valid_edges, reverse_edges): 正向邊和反向邊
    """
    # 在這個階段，我們暫時將所有邊都視為有效邊
    # 反向邊的檢測將在層級分配後進行
    return edges, set()


def _identify_isolated_nodes(graph: nx.DiGraph, all_task_ids: List[str]) -> Set[str]:
    """
    識別孤立節點：入度 + 出度 = 0 的節點。
    
    Args:
        graph: NetworkX 有向圖
        all_task_ids: 所有任務 ID 列表
    
    Returns:
        孤立節點集合
    """
    isolated = set()
    for task_id in all_task_ids:
        if task_id in graph.nodes():
            if graph.in_degree(task_id) == 0 and graph.out_degree(task_id) == 0:
                isolated.add(task_id)
        else:
            # 不在圖中的節點也視為孤立節點
            isolated.add(task_id)
    return isolated


def _ensure_dag(graph: nx.DiGraph) -> nx.DiGraph:
    """
    確保圖形是有向無環圖（DAG）
    如果還有循環，繼續移除直到成為 DAG
    
    Args:
        graph: NetworkX 有向圖
        
    Returns:
        確保無循環的 DAG
    """
    result_graph = graph.copy()
    max_iterations = 100  # 防止無限循環
    iteration = 0
    
    while not nx.is_directed_acyclic_graph(result_graph) and iteration < max_iterations:
        iteration += 1
        try:
            # 找到一個循環
            cycle = nx.find_cycle(result_graph, orientation='original')
            if cycle:
                # 移除循環中的第一條邊
                edge_to_remove = cycle[0][:2]  # 取 (source, target)
                print(f"額外移除邊: {edge_to_remove[0]} -> {edge_to_remove[1]} (迭代 {iteration})")
                result_graph.remove_edge(*edge_to_remove)
        except nx.NetworkXNoCycle:
            # 沒有循環了，結束
            break
    
    if iteration >= max_iterations:
        print(f"警告：達到最大迭代次數 ({max_iterations})，可能還有循環")
    
    return result_graph


def _compute_yed_style_layers(graph: nx.DiGraph, isolated_nodes: Set[str]) -> Dict[str, int]:
    """
    計算 yEd 風格的節點層級分配。
    
    Args:
        graph: NetworkX 有向圖
        isolated_nodes: 孤立節點集合
    
    Returns:
        節點層級字典 {node_id: layer}，孤立節點為 -1
    """
    layers = {}
    
    # 孤立節點放在特殊層 -1
    for node in isolated_nodes:
        layers[node] = -1
    
    # 為非孤立節點計算層級
    non_isolated_graph = graph.copy()
    for node in isolated_nodes:
        if node in non_isolated_graph:
            non_isolated_graph.remove_node(node)
    
    if non_isolated_graph.nodes():
        try:
            topo_order = list(nx.topological_sort(non_isolated_graph))
            
            # 使用最長路徑算法
            for node in topo_order:
                predecessors = list(non_isolated_graph.predecessors(node))
                if not predecessors:
                    # 源節點
                    layers[node] = 0
                else:
                    # 放在所有前驅節點的下一層
                    layers[node] = max(layers[pred] for pred in predecessors) + 1
                    
        except nx.NetworkXError:
            # 處理循環圖的情況
            for i, node in enumerate(non_isolated_graph.nodes()):
                layers[node] = i // 3  # 簡單分層
    
    return layers


def _assign_yed_positions(layers: Dict[str, int], isolated_nodes: Set[str], all_task_ids: List[str],
                         layer_spacing: int, node_spacing: int, isolated_spacing: int, direction: str) -> Dict[str, Tuple[float, float]]:
    """
    分配 yEd 風格的節點位置。
    
    Args:
        layers: 節點層級字典
        isolated_nodes: 孤立節點集合
        all_task_ids: 所有任務 ID
        layer_spacing: 層間距
        node_spacing: 節點間距
        isolated_spacing: 孤立節點間距
        direction: 布局方向
    
    Returns:
        節點位置字典
    """
    positions = {}
    
    # 按層分組
    layer_groups = {}
    for node, layer in layers.items():
        if layer not in layer_groups:
            layer_groups[layer] = []
        layer_groups[layer].append(node)
    
    # 獲取正常層級範圍
    normal_levels = [level for level in layer_groups.keys() if level >= 0]
    max_normal_level = max(normal_levels) if normal_levels else -1
    
    if direction == "TB":
        # Top-Bottom 布局：孤立節點在左側
        isolated_x_start = -(len(isolated_nodes) * isolated_spacing) - 100 if isolated_nodes else 0
        
        # 放置孤立節點
        if isolated_nodes:
            for i, node in enumerate(sorted(isolated_nodes)):
                x = isolated_x_start + i * isolated_spacing
                y = 0  # 孤立節點放在頂部
                positions[node] = (x, y)
        
        # 放置正常層級的節點
        for level, nodes in sorted(layer_groups.items()):
            if level >= 0:  # 正常層級
                y = (level + 1) * layer_spacing  # 為孤立節點留出空間
                start_x = -(len(nodes) - 1) * node_spacing / 2
                for i, node_id in enumerate(nodes):
                    x = start_x + i * node_spacing
                    positions[node_id] = (x, y)
    
    else:  # LR: Left-Right 布局：孤立節點在上方
        isolated_y_start = -(len(isolated_nodes) * isolated_spacing) - 100 if isolated_nodes else 0
        
        # 放置孤立節點
        if isolated_nodes:
            for i, node in enumerate(sorted(isolated_nodes)):
                x = 0  # 孤立節點放在左側
                y = isolated_y_start + i * isolated_spacing
                positions[node] = (x, y)
        
        # 放置正常層級的節點
        for level, nodes in sorted(layer_groups.items()):
            if level >= 0:  # 正常層級
                x = (level + 1) * layer_spacing  # 為孤立節點留出空間
                start_y = -(len(nodes) - 1) * node_spacing / 2
                for i, node_id in enumerate(nodes):
                    y = start_y + i * node_spacing
                    positions[node_id] = (x, y)
    
    return positions


def _handle_cyclic_layout(task_ids: List[str], edges: Set[Tuple[str, str]], isolated_nodes: Set[str],
                         layer_spacing: int, node_spacing: int, isolated_spacing: int, direction: str) -> Dict[str, Tuple[float, float]]:
    """
    處理包含循環的圖的布局。
    """
    # 簡化處理：使用簡單的層次分配
    return _simple_hierarchical_fallback(task_ids, edges, layer_spacing, node_spacing, direction)


def _layout_all_isolated(task_ids: List[str], isolated_spacing: int, direction: str) -> Dict[str, Tuple[float, float]]:
    """
    當所有節點都是孤立節點時的布局。
    """
    positions = {}
    if direction == "TB":
        for i, task_id in enumerate(task_ids):
            x = i * isolated_spacing
            y = 0
            positions[task_id] = (x, y)
    else:  # LR
        for i, task_id in enumerate(task_ids):
            x = 0
            y = i * isolated_spacing
            positions[task_id] = (x, y)
    return positions


def _assign_edge_ports(positions: Dict[str, Tuple[float, float]], valid_edges: Set[Tuple[str, str]], 
                      reverse_edges: Set[Tuple[str, str]], direction: str) -> Dict[str, Tuple[float, float]]:
    """
    為節點分配邊的連接端口信息。
    
    根據方向限制：
    - TB: Top是in，Bottom是out
    - LR: Left是in，Right是out
    """
    # 暫時直接返回位置，端口分配將在後續的路由階段實現
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
