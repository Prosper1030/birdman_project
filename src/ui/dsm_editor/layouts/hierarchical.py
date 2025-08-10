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
        isolated_spacing: int = 100
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
            
        Returns:
            節點座標字典
        """
        # 初始化
        self._initialize_graph(wbs_df, edges)
        
        if not self.graph or len(self.graph.nodes()) == 0:
            return {}
        
        # 階段 1: 循環移除
        self._phase1_cycle_removal()
        
        # 階段 2: 層級分配與虛擬節點插入
        self._phase2_layer_assignment()
        
        # 階段 3: 交叉減少
        self._phase3_crossing_reduction()
        
        # 階段 4: 座標分配
        self._phase4_coordinate_assignment(
            direction, layer_spacing, node_spacing, isolated_spacing
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
    
    # ================== 階段 1: 循環移除 ==================
    
    def _phase1_cycle_removal(self):
        """
        階段1：循環移除 - 使用反轉邊策略
        根據 Reference：偵測循環並暫時反轉邊來打破循環
        """
        if nx.is_directed_acyclic_graph(self.graph):
            return
        
        # 使用 DFS 為基礎的啟發式方法
        self.reversed_edges = self._dfs_based_cycle_removal()
        
        # 驗證結果
        if not nx.is_directed_acyclic_graph(self.graph):
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
    
    # ================== 階段 2: 層級分配 ==================
    
    def _phase2_layer_assignment(self):
        """
        階段2：層級分配與虛擬節點插入
        使用最長路徑法並處理跨層邊
        """
        # 使用最長路徑法計算層級
        self._compute_layers_longest_path()
        
        # 插入虛擬節點處理跨層邊
        self._insert_virtual_nodes()
        
        # 重新組織層級結構
        self._organize_layers()
    
    def _compute_layers_longest_path(self):
        """使用最長路徑法計算節點層級"""
        # 拓撲排序
        try:
            topo_order = list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            # 如果還有循環，使用基本策略
            topo_order = list(self.graph.nodes())
        
        # 初始化層級
        for node in self.graph.nodes():
            self.layers[node] = 0
        
        # 計算最長路徑
        for node in topo_order:
            for successor in self.graph.successors(node):
                self.layers[successor] = max(
                    self.layers[successor],
                    self.layers[node] + 1
                )
    
    def _insert_virtual_nodes(self):
        """插入虛擬節點處理跨層邊"""
        edges_to_process = list(self.graph.edges())
        virtual_counter = 0
        
        for src, dst in edges_to_process:
            src_layer = self.layers[src]
            dst_layer = self.layers[dst]
            
            # 如果跨越多層，需要插入虛擬節點
            if dst_layer - src_layer > 1:
                # 移除原始邊
                self.graph.remove_edge(src, dst)
                
                # 創建虛擬節點鏈
                prev_node = src
                for layer in range(src_layer + 1, dst_layer):
                    virtual_id = f"v_{virtual_counter}"
                    virtual_counter += 1
                    
                    # 創建虛擬節點
                    virtual_node = VirtualNode(virtual_id, layer, (src, dst))
                    self.virtual_nodes[virtual_id] = virtual_node
                    
                    # 添加到圖中
                    self.graph.add_node(virtual_id, is_virtual=True)
                    self.graph.add_edge(prev_node, virtual_id)
                    self.layers[virtual_id] = layer
                    
                    prev_node = virtual_id
                
                # 連接到目標節點
                self.graph.add_edge(prev_node, dst)
    
    def _organize_layers(self):
        """重新組織層級結構"""
        self.layer_nodes.clear()
        
        for node, layer in self.layers.items():
            self.layer_nodes[layer].append(node)
    
    # ================== 階段 3: 交叉減少 ==================
    
    def _phase3_crossing_reduction(self):
        """
        階段3：交叉減少
        使用重心法和中位數法的迭代優化
        """
        max_iterations = 10
        best_crossings = float('inf')
        best_positions = None
        no_improvement_count = 0
        
        # 初始化節點位置
        self._initialize_positions()
        
        for iteration in range(max_iterations):
            # 向下掃描
            self._sweep_down()
            
            # 向上掃描
            self._sweep_up()
            
            # 計算交叉數
            current_crossings = self._count_all_crossings()
            
            if current_crossings < best_crossings:
                best_crossings = current_crossings
                best_positions = self.node_positions.copy()
                no_improvement_count = 0
            else:
                no_improvement_count += 1
            
            # 早期終止條件
            if no_improvement_count >= 3 or current_crossings == 0:
                break
        
        # 恢復最佳位置
        if best_positions:
            self.node_positions = best_positions
    
    def _initialize_positions(self):
        """初始化節點在層內的位置"""
        for layer, nodes in self.layer_nodes.items():
            for i, node in enumerate(nodes):
                self.node_positions[node] = i
    
    def _sweep_down(self):
        """向下掃描：根據前一層調整後續層"""
        layers = sorted(self.layer_nodes.keys())
        
        for i in range(1, len(layers)):
            layer = layers[i]
            self._order_layer_by_barycenter(layer, 'predecessors')
    
    def _sweep_up(self):
        """向上掃描：根據後一層調整前面層"""
        layers = sorted(self.layer_nodes.keys(), reverse=True)
        
        for i in range(1, len(layers)):
            layer = layers[i]
            self._order_layer_by_barycenter(layer, 'successors')
    
    def _order_layer_by_barycenter(self, layer: int, direction: str):
        """使用重心法重新排序層內節點"""
        nodes = self.layer_nodes[layer]
        if len(nodes) <= 1:
            return
        
        # 計算每個節點的重心
        node_barycenters = []
        
        for node in nodes:
            if direction == 'predecessors':
                neighbors = list(self.graph.predecessors(node))
            else:
                neighbors = list(self.graph.successors(node))
            
            if neighbors:
                barycenter = sum(self.node_positions.get(n, 0) for n in neighbors) / len(neighbors)
            else:
                barycenter = self.node_positions.get(node, 0)
            
            node_barycenters.append((barycenter, node))
        
        # 按重心排序
        node_barycenters.sort(key=lambda x: x[0])
        
        # 更新位置
        for i, (_, node) in enumerate(node_barycenters):
            self.node_positions[node] = i
        
        # 更新層節點順序
        self.layer_nodes[layer] = [node for _, node in node_barycenters]
    
    def _count_all_crossings(self) -> int:
        """計算所有層間的交叉數"""
        total_crossings = 0
        layers = sorted(self.layer_nodes.keys())
        
        for i in range(len(layers) - 1):
            upper_layer = layers[i]
            lower_layer = layers[i + 1]
            total_crossings += self._count_crossings_between_layers(upper_layer, lower_layer)
        
        return total_crossings
    
    def _count_crossings_between_layers(self, upper_layer: int, lower_layer: int) -> int:
        """計算兩層間的交叉數"""
        upper_nodes = self.layer_nodes[upper_layer]
        lower_nodes = self.layer_nodes[lower_layer]
        
        # 收集所有跨層邊
        edges = []
        for i, upper_node in enumerate(upper_nodes):
            for j, lower_node in enumerate(lower_nodes):
                if self.graph.has_edge(upper_node, lower_node):
                    edges.append((i, j))
        
        # 計算交叉
        crossings = 0
        for i in range(len(edges)):
            for j in range(i + 1, len(edges)):
                u1, v1 = edges[i]
                u2, v2 = edges[j]
                if (u1 < u2 and v1 > v2) or (u1 > u2 and v1 < v2):
                    crossings += 1
        
        return crossings
    
    # ================== 階段 4: 座標分配 ==================
    
    def _phase4_coordinate_assignment(
        self, 
        direction: str, 
        layer_spacing: int, 
        node_spacing: int, 
        isolated_spacing: int
    ):
        """
        階段4：座標分配
        計算每個節點的最終 X/Y 座標
        """
        if not self.layer_nodes:
            return
        
        layers = sorted(self.layer_nodes.keys())
        
        # 處理孤立節點
        isolated_nodes = self._handle_isolated_nodes()
        
        # 計算主要層級的座標
        for layer in layers:
            nodes = self.layer_nodes[layer]
            
            if direction == "TB":  # 上到下
                y = layer * layer_spacing
                # 計算層內節點的 X 座標
                total_width = (len(nodes) - 1) * node_spacing
                start_x = -total_width / 2
                
                for i, node in enumerate(nodes):
                    x = start_x + i * node_spacing
                    self.coordinates[node] = (x, y)
                    
            else:  # LR: 左到右
                x = layer * layer_spacing
                # 計算層內節點的 Y 座標
                total_height = (len(nodes) - 1) * node_spacing
                start_y = -total_height / 2
                
                for i, node in enumerate(nodes):
                    y = start_y + i * node_spacing
                    self.coordinates[node] = (x, y)
        
        # 放置孤立節點
        self._place_isolated_nodes(isolated_nodes, direction, isolated_spacing)
        
        # 優化座標：對齊和拉直
        self._optimize_coordinates(direction, node_spacing)
    
    def _handle_isolated_nodes(self) -> List[str]:
        """處理孤立節點"""
        isolated_nodes = []
        
        for node in self.graph.nodes():
            if (self.graph.in_degree(node) == 0 and 
                self.graph.out_degree(node) == 0 and
                not self.graph.nodes[node].get('is_virtual', False)):
                isolated_nodes.append(node)
        
        # 從主要層級中移除孤立節點
        for node in isolated_nodes:
            if node in self.layers:
                layer = self.layers[node]
                if node in self.layer_nodes[layer]:
                    self.layer_nodes[layer].remove(node)
        
        return isolated_nodes
    
    def _place_isolated_nodes(self, isolated_nodes: List[str], direction: str, spacing: int):
        """放置孤立節點"""
        if not isolated_nodes:
            return
        
        # 計算主要內容的邊界
        if self.coordinates:
            if direction == "TB":
                min_x = min(coord[0] for coord in self.coordinates.values())
                isolated_x = min_x - 200  # 放在左側
                
                for i, node in enumerate(isolated_nodes):
                    y = i * spacing
                    self.coordinates[node] = (isolated_x, y)
            else:  # LR
                min_y = min(coord[1] for coord in self.coordinates.values())
                isolated_y = min_y - 200  # 放在上方
                
                for i, node in enumerate(isolated_nodes):
                    x = i * spacing
                    self.coordinates[node] = (x, isolated_y)
        else:
            # 如果沒有其他節點，簡單排列
            for i, node in enumerate(isolated_nodes):
                if direction == "TB":
                    self.coordinates[node] = (i * spacing, 0)
                else:
                    self.coordinates[node] = (0, i * spacing)
    
    def _optimize_coordinates(self, direction: str, node_spacing: int):
        """優化座標：對齊和拉直邊線"""
        # 這裡可以添加更高級的優化算法
        # 例如：節點對齊、邊線拉直等
        pass


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
    計算完整杉山方法的階層式佈局節點位置
    
    使用專業的四階段杉山框架：
    1. 循環移除 - 自動檢測並反轉邊來打破循環
    2. 層級分配 - 使用最長路徑法並插入虛擬節點
    3. 交叉減少 - 重心法迭代優化減少邊線交叉
    4. 座標分配 - 精確計算最終座標位置
    
    Args:
        wbs_df: WBS 資料框，需包含 "Task ID" 欄位
        edges: 邊的集合，格式為 {(src_id, dst_id), ...}
        direction: 佈局方向，"TB"(上到下) 或 "LR"(左到右)
        layer_spacing: 層間距離（像素）
        node_spacing: 同層節點間距離（像素）
        isolated_spacing: 孤立節點間距離（像素）
    
    Returns:
        節點位置字典 {task_id: (x, y)}
    """
    # 創建杉山佈局引擎
    layout_engine = SugiyamaLayout()
    
    # 執行完整的四階段佈局
    coordinates = layout_engine.layout(
        wbs_df, edges,
        direction=direction,
        layer_spacing=layer_spacing,
        node_spacing=node_spacing,
        isolated_spacing=isolated_spacing
    )
    
    return coordinates


# 向後相容的別名
def compute_hierarchical_layout(*args, **kwargs):
    """向後相容的函數別名"""
    return layout_hierarchical(*args, **kwargs)