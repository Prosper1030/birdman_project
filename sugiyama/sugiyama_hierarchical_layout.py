"""
階層式佈局演算法模組 - 完整實現杉山方法
Hierarchical Layout Algorithm - Complete Sugiyama Framework Implementation

實現完整的四階段杉山框架：
1. 循環移除 (Cycle Removal) - 使用反轉邊策略
2. 層級分配 (Layer Assignment) - 包含虛擬節點系統
3. 交叉減少 (Crossing Reduction) - 實現重心法和中位數法
4. 座標分配 (Coordinate Assignment) - 專業座標計算
"""

from typing import Dict, Tuple, List, Set, Optional, Any
import pandas as pd
import networkx as nx
import math
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class VirtualNode:
    """虛擬節點 - 用於處理跨層邊"""
    id: str
    layer: int
    original_edge: Tuple[str, str]
    is_virtual: bool = True
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        return self.id == other.id if isinstance(other, VirtualNode) else False


class SugiyamaLayout:
    """
    完整實現杉山方法的階層式佈局引擎
    """
    
    def __init__(self):
        self.graph = None
        self.layers = {}  # {node_id: layer_index}
        self.layer_nodes = defaultdict(list)  # {layer_index: [node_ids]}
        self.node_positions = {}  # {node_id: position_in_layer}
        self.virtual_nodes = {}  # {virtual_id: VirtualNode}
        self.reversed_edges = set()  # 被反轉的邊
        self.coordinates = {}  # 最終座標 {node_id: (x, y)}
        
    def layout(
        self,
        wbs_df: pd.DataFrame,
        edges: Set[Tuple[str, str]] = None,
        *,
        direction: str = "TB",
        layer_spacing: int = 200,
        node_spacing: int = 150,
        isolated_spacing: int = 100,
        node_sizes: Dict[str, Dict[str, float]] = None
    ) -> Dict[str, Tuple[float, float]]:
        """
        執行完整的杉山方法佈局
        
        Args:
            wbs_df: WBS 資料框
            edges: 邊的集合
            direction: 佈局方向
            layer_spacing: 層間距
            node_spacing: 節點間距
            isolated_spacing: 孤立節點間距
            node_sizes: 節點尺寸字典 {'node_id': {'width': w, 'height': h}}
            
        Returns:
            節點座標字典
        """
        # 初始化
        self._initialize_graph(wbs_df, edges)
        
        if not self.graph or len(self.graph.nodes()) == 0:
            return {}
        
        # 初始化節點尺寸資訊
        self._initialize_node_sizes(node_sizes)
        
        # 階段 1: 循環移除
        self._phase1_cycle_removal()
        
        # 階段 2: 層級分配與虛擬節點插入
        self._phase2_layer_assignment()
        
        # 階段 3: 交叉減少
        self._phase3_crossing_reduction()
        
        # 階段 4: 座標分配
        self._phase4_coordinate_assignment(
            direction, layer_spacing, node_spacing, isolated_spacing, node_sizes
        )
        
        return self.coordinates
    
    def _initialize_graph(self, wbs_df: pd.DataFrame, edges: Set[Tuple[str, str]]):
        """初始化圖形結構"""
        self.graph = nx.DiGraph()
        
        # 添加節點
        for _, row in wbs_df.iterrows():
            task_id = str(row.get("Task ID", f"Task_{_}"))
            self.graph.add_node(task_id, is_virtual=False)
        
        # 添加邊
        if edges:
            for src, dst in edges:
                if src in self.graph.nodes() and dst in self.graph.nodes():
                    self.graph.add_edge(src, dst)
    
    def _initialize_node_sizes(self, node_sizes: Dict[str, Dict[str, float]] = None):
        """初始化節點尺寸資訊"""
        self.node_sizes = {}
        
        # 預設尺寸
        default_size = {'width': 120, 'height': 60}
        
        for node_id in self.graph.nodes():
            if node_sizes and node_id in node_sizes:
                self.node_sizes[node_id] = node_sizes[node_id].copy()
            else:
                self.node_sizes[node_id] = default_size.copy()
    
    # ================== 階段 1: 循環移除 ==================
    
    def _phase1_cycle_removal(self):
        """
        階段1：循環移除 - 使用反轉邊策略
        根據 Reference：偵測循環並暫時反轉邊來打破循環
        """
        print("階段1：循環移除開始...")
        
        if nx.is_directed_acyclic_graph(self.graph):
            print("  圖已經是 DAG，無需處理")
            return
        
        # 使用 DFS 為基礎的啟發式方法
        self.reversed_edges = self._dfs_based_cycle_removal()
        
        print(f"  反轉了 {len(self.reversed_edges)} 條邊")
        
        # 驗證結果
        if not nx.is_directed_acyclic_graph(self.graph):
            print("  警告：仍有循環，使用備用策略")
            self._greedy_cycle_removal()
    
    def _dfs_based_cycle_removal(self) -> Set[Tuple[str, str]]:
        """基於 DFS 的循環移除演算法"""
        reversed_edges = set()
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in list(self.graph.neighbors(node)):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # 找到回邊，反轉它
                    self.graph.remove_edge(node, neighbor)
                    self.graph.add_edge(neighbor, node)
                    reversed_edges.add((node, neighbor))
                    print(f"    反轉邊: {node} -> {neighbor}")
            
            rec_stack.remove(node)
        
        for node in list(self.graph.nodes()):
            if node not in visited:
                dfs(node)
        
        return reversed_edges
    
    def _greedy_cycle_removal(self):
        """貪婪循環移除備用策略"""
        max_iterations = 100
        iteration = 0
        
        while not nx.is_directed_acyclic_graph(self.graph) and iteration < max_iterations:
            iteration += 1
            
            try:
                cycle = nx.find_cycle(self.graph, orientation='original')
                if cycle:
                    # 選擇最佳邊來反轉
                    edge = self._select_edge_to_reverse(cycle)
                    if edge:
                        src, dst = edge
                        self.graph.remove_edge(src, dst)
                        self.graph.add_edge(dst, src)
                        self.reversed_edges.add(edge)
                        print(f"    額外反轉邊: {src} -> {dst}")
            except nx.NetworkXNoCycle:
                break
    
    def _select_edge_to_reverse(self, cycle) -> Optional[Tuple[str, str]]:
        """選擇最佳的邊來反轉"""
        edges = [(u, v) for u, v, _ in cycle]
        if not edges:
            return None
        
        # 選擇連接度數最高節點的邊
        best_edge = None
        best_score = -1
        
        for src, dst in edges:
            score = (self.graph.in_degree(src) + self.graph.out_degree(src) +
                    self.graph.in_degree(dst) + self.graph.out_degree(dst))
            if score > best_score:
                best_score = score
                best_edge = (src, dst)
        
        return best_edge
    
    # ================== 階段 2: 層級分配與虛擬節點 ==================
    
    def _phase2_layer_assignment(self):
        """
        階段2：層級分配 - 包含虛擬節點插入
        使用最長路徑法、層級向下壓縮並插入虛擬節點處理跨層邊
        """
        print("階段2：層級分配開始...")
        
        # 計算初始層級（最長路徑法）
        self._compute_longest_path_layers()
        
        # 執行層級向下壓縮 (Sinking) 以最大化緊密度
        self._perform_layer_sinking()
        
        # 插入虛擬節點處理跨層邊
        self._insert_virtual_nodes()
        
        # 建立層級到節點的映射
        self._build_layer_mapping()
        
        print(f"  分配了 {len(set(self.layers.values()))} 層")
        print(f"  插入了 {len(self.virtual_nodes)} 個虛擬節點")
    
    def _compute_longest_path_layers(self):
        """使用最長路徑法計算層級"""
        # 拓撲排序
        try:
            topo_order = list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            print("  警告：圖中仍有循環，使用備用方法")
            topo_order = list(self.graph.nodes())
        
        # 初始化層級
        self.layers = {}
        
        for node in topo_order:
            predecessors = list(self.graph.predecessors(node))
            if not predecessors:
                # 源節點在第0層
                self.layers[node] = 0
            else:
                # 在所有前驅的最大層級 + 1
                self.layers[node] = max(self.layers.get(pred, 0) 
                                      for pred in predecessors) + 1
    
    def _perform_layer_sinking(self):
        """
        執行層級向下壓縮 (Sinking) 優化
        倒序遍歷拓撲排序結果，將每個節點向下移動到最低可能層級
        """
        print("  執行層級向下壓縮...")
        
        try:
            # 獲取倒序拓撲排序
            topo_order = list(reversed(list(nx.topological_sort(self.graph))))
        except nx.NetworkXError:
            print("    警告：圖中仍有循環，跳過壓縮優化")
            return
        
        sinking_count = 0
        
        for node in topo_order:
            successors = list(self.graph.successors(node))
            
            if successors:
                # 計算可移動到的最低層級：所有子節點的最小層級 - 1
                min_successor_layer = min(self.layers.get(succ, float('inf')) 
                                        for succ in successors)
                target_layer = min_successor_layer - 1
                
                # 如果目標層級高於當前層級，則移動節點
                current_layer = self.layers[node]
                if target_layer > current_layer:
                    self.layers[node] = target_layer
                    sinking_count += 1
        
        print(f"    壓縮了 {sinking_count} 個節點到更低層級")
    
    def _insert_virtual_nodes(self):
        """插入虛擬節點處理跨層邊"""
        edges_to_process = list(self.graph.edges())
        virtual_counter = 0
        
        for src, dst in edges_to_process:
            src_layer = self.layers.get(src, 0)
            dst_layer = self.layers.get(dst, 0)
            
            # 檢查是否為跨層邊
            if dst_layer > src_layer + 1:
                # 需要插入虛擬節點
                self.graph.remove_edge(src, dst)
                
                # 插入一系列虛擬節點
                prev_node = src
                for layer in range(src_layer + 1, dst_layer):
                    virtual_id = f"__virtual_{virtual_counter}__"
                    virtual_counter += 1
                    
                    # 創建虛擬節點
                    virtual = VirtualNode(
                        id=virtual_id,
                        layer=layer,
                        original_edge=(src, dst)
                    )
                    
                    self.virtual_nodes[virtual_id] = virtual
                    self.graph.add_node(virtual_id, is_virtual=True)
                    self.layers[virtual_id] = layer
                    
                    # 連接邊
                    self.graph.add_edge(prev_node, virtual_id)
                    prev_node = virtual_id
                
                # 連接最後一段
                self.graph.add_edge(prev_node, dst)
    
    def _build_layer_mapping(self):
        """建立層級到節點的映射"""
        self.layer_nodes = defaultdict(list)
        for node, layer in self.layers.items():
            self.layer_nodes[layer].append(node)
        
        # 每層內初始化位置
        for layer, nodes in self.layer_nodes.items():
            for i, node in enumerate(nodes):
                self.node_positions[node] = i
    
    # ================== 階段 3: 交叉減少 ==================
    
    def _phase3_crossing_reduction(self):
        """
        階段3：交叉減少 - 實現重心法和中位數法
        這是杉山方法的核心，透過調整每層節點順序來最小化邊線交叉
        """
        print("階段3：交叉減少開始...")
        
        max_iterations = 10
        improvement_threshold = 0.01
        
        previous_crossings = self._count_all_crossings()
        print(f"  初始交叉數: {previous_crossings}")
        
        for iteration in range(max_iterations):
            # 向下掃描（從上到下優化）
            self._sweep_down()
            
            # 向上掃描（從下到上優化）
            self._sweep_up()
            
            # 計算當前交叉數
            current_crossings = self._count_all_crossings()
            
            # 檢查改進幅度
            if previous_crossings > 0:
                improvement = (previous_crossings - current_crossings) / previous_crossings
                print(f"  迭代 {iteration + 1}: 交叉數 = {current_crossings} "
                      f"(改進 {improvement:.1%})")
                
                if improvement < improvement_threshold:
                    print("  收斂，停止迭代")
                    break
            else:
                print(f"  迭代 {iteration + 1}: 交叉數 = {current_crossings}")
                if current_crossings == 0:
                    break
            
            previous_crossings = current_crossings
        
        print(f"  最終交叉數: {current_crossings}")
    
    def _sweep_down(self):
        """向下掃描：固定上層，優化下層"""
        layers = sorted(self.layer_nodes.keys())
        
        for i in range(len(layers) - 1):
            upper_layer = layers[i]
            lower_layer = layers[i + 1]
            
            # 使用重心法優化下層順序
            self._barycenter_ordering(upper_layer, lower_layer, direction='down')
    
    def _sweep_up(self):
        """向上掃描：固定下層，優化上層"""
        layers = sorted(self.layer_nodes.keys(), reverse=True)
        
        for i in range(len(layers) - 1):
            lower_layer = layers[i]
            upper_layer = layers[i + 1]
            
            # 使用重心法優化上層順序
            self._barycenter_ordering(lower_layer, upper_layer, direction='up')
    
    def _barycenter_ordering(self, fixed_layer: int, free_layer: int, direction: str):
        """
        重心法排序 - 杉山方法的核心演算法
        將節點放置在其鄰居的重心位置
        """
        free_nodes = self.layer_nodes[free_layer].copy()
        barycenters = {}
        
        for node in free_nodes:
            if direction == 'down':
                # 計算上層鄰居的重心
                neighbors = list(self.graph.predecessors(node))
            else:
                # 計算下層鄰居的重心
                neighbors = list(self.graph.successors(node))
            
            # 過濾出在固定層的鄰居
            fixed_neighbors = [n for n in neighbors if self.layers.get(n) == fixed_layer]
            
            if fixed_neighbors:
                # 計算重心（平均位置）
                positions = [self.node_positions[n] for n in fixed_neighbors]
                barycenters[node] = sum(positions) / len(positions)
            else:
                # 沒有鄰居，保持原位置
                barycenters[node] = self.node_positions[node]
        
        # 根據重心排序
        sorted_nodes = sorted(free_nodes, key=lambda n: (barycenters[n], n))
        
        # 更新位置
        self.layer_nodes[free_layer] = sorted_nodes
        for i, node in enumerate(sorted_nodes):
            self.node_positions[node] = i
    
    def _median_ordering(self, fixed_layer: int, free_layer: int, direction: str):
        """
        中位數法排序 - 另一種交叉減少演算法
        將節點放置在其鄰居的中位數位置
        """
        free_nodes = self.layer_nodes[free_layer].copy()
        medians = {}
        
        for node in free_nodes:
            if direction == 'down':
                neighbors = list(self.graph.predecessors(node))
            else:
                neighbors = list(self.graph.successors(node))
            
            fixed_neighbors = [n for n in neighbors if self.layers.get(n) == fixed_layer]
            
            if fixed_neighbors:
                positions = sorted([self.node_positions[n] for n in fixed_neighbors])
                # 計算中位數
                n = len(positions)
                if n % 2 == 1:
                    medians[node] = positions[n // 2]
                else:
                    medians[node] = (positions[n // 2 - 1] + positions[n // 2]) / 2
            else:
                medians[node] = self.node_positions[node]
        
        # 根據中位數排序
        sorted_nodes = sorted(free_nodes, key=lambda n: (medians[n], n))
        
        # 更新位置
        self.layer_nodes[free_layer] = sorted_nodes
        for i, node in enumerate(sorted_nodes):
            self.node_positions[node] = i
    
    def _count_all_crossings(self) -> int:
        """計算所有層之間的總交叉數"""
        total_crossings = 0
        layers = sorted(self.layer_nodes.keys())
        
        for i in range(len(layers) - 1):
            upper_layer = layers[i]
            lower_layer = layers[i + 1]
            crossings = self._count_crossings_between_layers(upper_layer, lower_layer)
            total_crossings += crossings
        
        return total_crossings
    
    def _count_crossings_between_layers(self, upper_layer: int, lower_layer: int) -> int:
        """計算兩層之間的交叉數"""
        crossings = 0
        upper_nodes = self.layer_nodes[upper_layer]
        lower_nodes = self.layer_nodes[lower_layer]
        
        # 獲取所有從上層到下層的邊
        edges = []
        for u in upper_nodes:
            for v in self.graph.successors(u):
                if self.layers.get(v) == lower_layer:
                    u_pos = self.node_positions[u]
                    v_pos = self.node_positions[v]
                    edges.append((u_pos, v_pos))
        
        # 計算交叉數（使用簡單的 O(n²) 演算法）
        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                u1, v1 = edges[i]
                u2, v2 = edges[j]
                
                # 檢查是否交叉
                if (u1 < u2 and v1 > v2) or (u1 > u2 and v1 < v2):
                    crossings += 1
        
        return crossings
    
    # ================== 階段 4: 座標分配 ==================
    
    def _phase4_coordinate_assignment(
        self,
        direction: str,
        layer_spacing: int,
        node_spacing: int,
        isolated_spacing: int,
        node_sizes: Dict[str, Dict[str, float]] = None
    ):
        """
        階段4：尺寸感知座標分配 - 專業座標計算
        基於真實節點尺寸分配無重疊的座標，並計算精確的邊線端口
        """
        print("階段4：尺寸感知座標分配開始...")
        
        # 識別孤立節點
        isolated_nodes = self._identify_isolated_nodes()
        
        # 使用尺寸感知算法分配座標
        self.coordinates = {}
        self._assign_size_aware_coordinates(direction, layer_spacing, node_spacing)
        
        # 處理孤立節點
        self._assign_isolated_coordinates_with_sizes(
            isolated_nodes, direction, isolated_spacing
        )
        
        # 計算精確的邊線端口
        self._calculate_edge_ports(direction)
        
        # 優化座標（拉直邊線、對齊節點）
        self._optimize_coordinates_with_sizes(direction)
        
        print(f"  分配了 {len(self.coordinates)} 個節點座標")
    
    def _identify_isolated_nodes(self) -> Set[str]:
        """識別孤立節點"""
        isolated = set()
        for node in self.graph.nodes():
            if (self.graph.in_degree(node) == 0 and 
                self.graph.out_degree(node) == 0 and
                node not in self.virtual_nodes):
                isolated.add(node)
        return isolated
    
    def _compute_layer_widths(self, node_spacing: int) -> Dict[int, float]:
        """計算每層的寬度"""
        widths = {}
        for layer, nodes in self.layer_nodes.items():
            # 過濾掉虛擬節點
            real_nodes = [n for n in nodes if n not in self.virtual_nodes]
            widths[layer] = len(real_nodes) * node_spacing
        return widths
    
    def _compute_node_coordinate(
        self, node: str, layer: int, position: int,
        direction: str, layer_spacing: int, node_spacing: int,
        layer_widths: Dict[int, float]
    ) -> Tuple[float, float]:
        """計算節點座標"""
        # 獲取該層的實際節點數（排除虛擬節點）
        real_nodes = [n for n in self.layer_nodes[layer] 
                     if n not in self.virtual_nodes]
        real_position = real_nodes.index(node) if node in real_nodes else position
        
        if direction == "TB":
            # 上到下佈局
            layer_width = layer_widths[layer]
            x = (real_position - (len(real_nodes) - 1) / 2) * node_spacing
            y = layer * layer_spacing
        else:  # LR
            # 左到右佈局
            layer_width = layer_widths[layer]
            x = layer * layer_spacing
            y = (real_position - (len(real_nodes) - 1) / 2) * node_spacing
        
        return (x, y)
    
    def _assign_isolated_coordinates(
        self, isolated_nodes: Set[str], 
        direction: str, isolated_spacing: int
    ):
        """分配孤立節點座標"""
        if not isolated_nodes:
            return
        
        # 計算主佈局的邊界
        if self.coordinates:
            x_coords = [pos[0] for pos in self.coordinates.values()]
            y_coords = [pos[1] for pos in self.coordinates.values()]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
        else:
            min_x = max_x = min_y = max_y = 0
        
        # 將孤立節點放在側邊
        for i, node in enumerate(sorted(isolated_nodes)):
            if direction == "TB":
                # 放在左側
                x = min_x - 200 - i * isolated_spacing
                y = 0
            else:  # LR
                # 放在上方
                x = 0
                y = min_y - 200 - i * isolated_spacing
            
            self.coordinates[node] = (x, y)
    
    def _optimize_coordinates(self, direction: str, node_spacing: int):
        """
        優化座標 - 拉直邊線、對齊節點
        使用優先級方法：
        1. 嘗試拉直長邊
        2. 對齊有共同父節點的節點
        3. 最小化邊線總長度
        """
        # 簡單的優化：調整節點位置使其對齊父節點
        for layer in sorted(self.layer_nodes.keys()):
            if layer == 0:
                continue
            
            nodes = [n for n in self.layer_nodes[layer] 
                    if n not in self.virtual_nodes]
            
            for node in nodes:
                if node not in self.coordinates:
                    continue
                
                # 獲取所有父節點
                parents = [p for p in self.graph.predecessors(node)
                          if p not in self.virtual_nodes and p in self.coordinates]
                
                if parents:
                    # 計算父節點的平均 X 座標
                    if direction == "TB":
                        avg_x = sum(self.coordinates[p][0] for p in parents) / len(parents)
                        old_y = self.coordinates[node][1]
                        # 微調 X 座標向父節點對齊
                        current_x = self.coordinates[node][0]
                        new_x = current_x * 0.7 + avg_x * 0.3  # 部分對齊
                        self.coordinates[node] = (new_x, old_y)
                    else:  # LR
                        avg_y = sum(self.coordinates[p][1] for p in parents) / len(parents)
                        old_x = self.coordinates[node][0]
                        current_y = self.coordinates[node][1]
                        new_y = current_y * 0.7 + avg_y * 0.3
                        self.coordinates[node] = (old_x, new_y)
    
    # ================== 新增：尺寸感知座標分配 ==================
    
    def _assign_size_aware_coordinates(self, direction: str, layer_spacing: int, node_spacing: int):
        """尺寸感知座標分配 - 基於實際節點尺寸避免重疊"""
        min_node_gap = 30  # 節點邊界到邊界的最小距離
        
        for layer_idx in sorted(self.layer_nodes.keys()):
            nodes = [n for n in self.layer_nodes[layer_idx] 
                    if n not in self.virtual_nodes]
            
            if not nodes:
                continue
                
            # 計算每個節點在該層的位置
            if direction == "TB":
                y = layer_idx * layer_spacing
                x_positions = self._pack_nodes_in_layer_tb(nodes, min_node_gap)
                
                for node, x in zip(nodes, x_positions):
                    self.coordinates[node] = (x, y)
            else:  # LR
                x = layer_idx * layer_spacing
                y_positions = self._pack_nodes_in_layer_lr(nodes, min_node_gap)
                
                for node, y in zip(nodes, y_positions):
                    self.coordinates[node] = (x, y)
    
    def _pack_nodes_in_layer_tb(self, nodes: List[str], min_gap: float) -> List[float]:
        """TB方向：在一層中打包節點，避免水平重疊"""
        if not nodes:
            return []
        
        # 按照當前排序順序處理節點
        positions = []
        current_x = 0
        
        for i, node in enumerate(nodes):
            node_width = self.node_sizes.get(node, {}).get('width', 120)
            
            if i == 0:
                # 第一個節點居中放置
                positions.append(0)
                current_x = node_width / 2
            else:
                # 後續節點考慮前一個節點的寬度和間隙
                prev_node = nodes[i-1]
                prev_width = self.node_sizes.get(prev_node, {}).get('width', 120)
                
                # 計算下一個位置：前一個節點右邊界 + 間隙 + 當前節點半寬
                next_x = current_x + prev_width/2 + min_gap + node_width/2
                positions.append(next_x)
                current_x = next_x
        
        # 居中整個層
        if positions:
            total_width = positions[-1] - positions[0] if len(positions) > 1 else 0
            offset = -total_width / 2
            positions = [pos + offset for pos in positions]
        
        return positions
    
    def _pack_nodes_in_layer_lr(self, nodes: List[str], min_gap: float) -> List[float]:
        """LR方向：在一層中打包節點，避免垂直重疊"""
        if not nodes:
            return []
        
        positions = []
        current_y = 0
        
        for i, node in enumerate(nodes):
            node_height = self.node_sizes.get(node, {}).get('height', 60)
            
            if i == 0:
                positions.append(0)
                current_y = node_height / 2
            else:
                prev_node = nodes[i-1]
                prev_height = self.node_sizes.get(prev_node, {}).get('height', 60)
                
                next_y = current_y + prev_height/2 + min_gap + node_height/2
                positions.append(next_y)
                current_y = next_y
        
        # 居中整個層
        if positions:
            total_height = positions[-1] - positions[0] if len(positions) > 1 else 0
            offset = -total_height / 2
            positions = [pos + offset for pos in positions]
        
        return positions
    
    def _assign_isolated_coordinates_with_sizes(
        self, isolated_nodes: Set[str], direction: str, isolated_spacing: int
    ):
        """為孤立節點分配尺寸感知座標"""
        if not isolated_nodes:
            return
        
        # 計算主佈局的邊界
        if self.coordinates:
            x_coords = [pos[0] for pos in self.coordinates.values()]
            y_coords = [pos[1] for pos in self.coordinates.values()]
            
            # 考慮節點尺寸計算真實邊界
            min_x = min(x_coords) - max(self.node_sizes.get(node, {}).get('width', 120)/2 
                                       for node in self.coordinates.keys())
            max_x = max(x_coords) + max(self.node_sizes.get(node, {}).get('width', 120)/2 
                                       for node in self.coordinates.keys())
            min_y = min(y_coords) - max(self.node_sizes.get(node, {}).get('height', 60)/2 
                                       for node in self.coordinates.keys())
            max_y = max(y_coords) + max(self.node_sizes.get(node, {}).get('height', 60)/2 
                                       for node in self.coordinates.keys())
        else:
            min_x = max_x = min_y = max_y = 0
        
        # 將孤立節點排列在主佈局外側
        current_offset = 0
        for node in sorted(isolated_nodes):
            node_width = self.node_sizes.get(node, {}).get('width', 120)
            node_height = self.node_sizes.get(node, {}).get('height', 60)
            
            if direction == "TB":
                # 放在左側
                x = min_x - 200 - current_offset - node_width/2
                y = 0
                current_offset += node_width + isolated_spacing
            else:  # LR
                # 放在上方
                x = 0
                y = min_y - 200 - current_offset - node_height/2
                current_offset += node_height + isolated_spacing
            
            self.coordinates[node] = (x, y)
    
    def _calculate_edge_ports(self, direction: str):
        """計算精確的邊線端口座標"""
        self.edge_ports = {}
        
        for src, dst in self.graph.edges():
            # 跳過虛擬節點
            if src in self.virtual_nodes or dst in self.virtual_nodes:
                continue
            
            if src not in self.coordinates or dst not in self.coordinates:
                continue
                
            src_pos = self.coordinates[src]
            dst_pos = self.coordinates[dst]
            
            src_size = self.node_sizes.get(src, {'width': 120, 'height': 60})
            dst_size = self.node_sizes.get(dst, {'width': 120, 'height': 60})
            
            # 計算最佳端口位置
            src_port = self._calculate_optimal_port(src_pos, src_size, dst_pos, direction, 'out')
            dst_port = self._calculate_optimal_port(dst_pos, dst_size, src_pos, direction, 'in')
            
            self.edge_ports[(src, dst)] = (src_port, dst_port)
    
    def _calculate_optimal_port(
        self, node_pos: Tuple[float, float], node_size: Dict[str, float],
        target_pos: Tuple[float, float], direction: str, port_type: str
    ) -> Tuple[float, float]:
        """計算節點的最佳端口位置"""
        x, y = node_pos
        width = node_size['width']
        height = node_size['height']
        
        # 端口內縮，避免貼到邊框
        margin = 8
        
        if direction == "TB":
            if port_type == 'out':
                # 出邊從底部出去
                return (x, y + height/2 - margin)
            else:
                # 入邊從頂部進來
                return (x, y - height/2 + margin)
        else:  # LR
            if port_type == 'out':
                # 出邊從右側出去
                return (x + width/2 - margin, y)
            else:
                # 入邊從左側進來
                return (x - width/2 + margin, y)
    
    def _optimize_coordinates_with_sizes(self, direction: str):
        """基於尺寸的座標優化"""
        # 簡化版優化：確保節點間距合理
        min_gap = 30
        
        for layer_idx in sorted(self.layer_nodes.keys()):
            nodes = [n for n in self.layer_nodes[layer_idx] 
                    if n not in self.virtual_nodes and n in self.coordinates]
            
            if len(nodes) <= 1:
                continue
            
            # 檢查並調整間距
            self._ensure_minimum_spacing(nodes, direction, min_gap)
    
    def _ensure_minimum_spacing(self, nodes: List[str], direction: str, min_gap: float):
        """確保節點間的最小間距"""
        if len(nodes) <= 1:
            return
        
        # 按位置排序節點
        if direction == "TB":
            nodes.sort(key=lambda n: self.coordinates[n][0])
        else:
            nodes.sort(key=lambda n: self.coordinates[n][1])
        
        # 調整間距
        for i in range(1, len(nodes)):
            prev_node = nodes[i-1]
            curr_node = nodes[i]
            
            prev_pos = self.coordinates[prev_node]
            curr_pos = self.coordinates[curr_node]
            
            if direction == "TB":
                prev_width = self.node_sizes.get(prev_node, {}).get('width', 120)
                curr_width = self.node_sizes.get(curr_node, {}).get('width', 120)
                
                required_distance = prev_width/2 + curr_width/2 + min_gap
                actual_distance = curr_pos[0] - prev_pos[0]
                
                if actual_distance < required_distance:
                    adjustment = required_distance - actual_distance
                    new_x = curr_pos[0] + adjustment
                    self.coordinates[curr_node] = (new_x, curr_pos[1])
            else:  # LR
                prev_height = self.node_sizes.get(prev_node, {}).get('height', 60)
                curr_height = self.node_sizes.get(curr_node, {}).get('height', 60)
                
                required_distance = prev_height/2 + curr_height/2 + min_gap
                actual_distance = curr_pos[1] - prev_pos[1]
                
                if actual_distance < required_distance:
                    adjustment = required_distance - actual_distance
                    new_y = curr_pos[1] + adjustment
                    self.coordinates[curr_node] = (prev_pos[0], new_y)


def layout_hierarchical(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150,
    isolated_spacing: int = 100,
    node_sizes: Dict[str, Dict[str, float]] = None
) -> Dict[str, Tuple[float, float]]:
    """
    計算完整杉山方法的階層式佈局
    
    Args:
        wbs_df: WBS 資料框
        edges: 邊的集合
        direction: 佈局方向
        layer_spacing: 層間距
        node_spacing: 節點間距
        isolated_spacing: 孤立節點間距
        node_sizes: 節點尺寸字典 {'node_id': {'width': w, 'height': h}}
        
    Returns:
        節點座標字典
    """
    layout_engine = SugiyamaLayout()
    return layout_engine.layout(
        wbs_df, edges,
        direction=direction,
        layer_spacing=layer_spacing,
        node_spacing=node_spacing,
        isolated_spacing=isolated_spacing,
        node_sizes=node_sizes
    )


# 保留原有的輔助函數以確保相容性
def _simple_grid_layout(
    task_ids: List[str],
    node_spacing: int,
    layer_spacing: int,
    direction: str
) -> Dict[str, Tuple[float, float]]:
    """簡單網格佈局"""
    positions = {}
    cols = 5
    
    for i, task_id in enumerate(task_ids):
        row = i // cols
        col = i % cols
        
        if direction == "TB":
            x = (col - cols // 2) * node_spacing
            y = row * layer_spacing
        else:
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
    """簡單階層式備用方案"""
    positions = {}
    nodes_per_level = 4
    
    for i, task_id in enumerate(task_ids):
        level = i // nodes_per_level
        pos_in_level = i % nodes_per_level
        
        if direction == "TB":
            start_x = -(nodes_per_level - 1) * node_spacing / 2
            x = start_x + pos_in_level * node_spacing
            y = level * layer_spacing
        else:
            start_x = -(nodes_per_level - 1) * node_spacing / 2
            x = level * layer_spacing
            y = start_y + pos_in_level * node_spacing
        
        positions[task_id] = (x, y)
    
    return positions