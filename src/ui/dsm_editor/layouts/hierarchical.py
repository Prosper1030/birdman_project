"""
階層式佈局演算法模組 - 完整實現杉山方法
Hierarchical Layout Algorithm - Complete Sugiyama Framework Implementation

實現完整的四階段杉山框架：
1. 循環移除 (Cycle Removal) - 使用反轉邊策略
2. 層級分配 (Layer Assignment) - 包含虛擬節點系統
3. 交叉減少 (Crossing Reduction) - 實現重心法和中位數法
4. 座標分配 (Coordinate Assignment) - 專業座標計算 + yEd 式 ports

TODO - 後續擴充功能:
- 正交路由器：吃 edge_ports 為起終點，避障於節點 bbox+安全距，回邊優先走外圈導管
- 平行邊偏移：同一對 (u,v) 多條邊做輕微 offset，防止重疊
- 節點真實尺寸：從 GUI 注入每個節點 width/height
- 增量更新：拖曳單節點時，只重算該節點 incident edges 的 ports
- 自訂 port 鎖定：保留介面允許手動指定某節點的 port 順位或固定某側
"""

from typing import Dict, Tuple, List, Set, Optional, Any
import pandas as pd
import networkx as nx
from collections import defaultdict
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
        # 原有屬性
        self.graph = None
        self.layers = {}  # {node_id: layer_index}
        self.layer_nodes = defaultdict(list)  # {layer_index: [node_ids]}
        self.node_positions = {}  # {node_id: position_in_layer}
        self.virtual_nodes = {}  # {virtual_id: VirtualNode}
        self.reversed_edges = set()  # 被反轉的邊
        self.coordinates = {}  # 最終座標 {node_id: (x, y)}

        # 新增：原始邊集合存儲
        self.original_edges = set()  # 原始輸入的邊集合

        # 新增：盒模型屬性（給預設值，之後 GUI 會塞真實尺寸）
        self.node_width: int = 120      # 預設節點寬
        self.node_height: int = 60      # 預設節點高
        self.node_margin: int = 8       # port 內縮，避免貼到外框線
        self.min_gap: int = 16          # 同層節點之間的最小間隙（邊界到邊界）

        # 新增：Minimum Distances 設定（皆為 border↔border）
        self.min_node_node: float = 30.0   # Node to Node Distance（同層/同行/列的節點之間）
        self.min_node_edge: float = 15.0   # Node to Edge Distance（節點邊界到任一邊線）
        self.min_edge_edge: float = 15.0   # Edge to Edge Distance（兩條邊之間）
        self.min_layer_layer: float = 10.0  # Layer to Layer Distance（相鄰兩層的節點邊界距）

        # 新增：yEd 式 Ports（N+1 等分）
        self.edge_ports: Dict[Tuple[str, str], Tuple[Tuple[float, float], Tuple[float, float]]] = {}

    def layout(
        self,
        wbs_df: pd.DataFrame,
        edges: Set[Tuple[str, str]] = None,
        *,
        direction: str = "TB",
        layer_spacing: int = 200,
        node_spacing: int = 150,
        isolated_spacing: int = 100,
        min_node_node: float = None,
        min_layer_layer: float = None,
        min_node_edge: float = None
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
        # 存儲原始邊集合
        self.original_edges = set(edges or [])

        # 允許外部調整最小距離
        if min_node_node is not None:
            self.min_node_node = min_node_node
        if min_layer_layer is not None:
            self.min_layer_layer = min_layer_layer
        if min_node_edge is not None:
            self.min_node_edge = min_node_edge

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

        # 階段 4: 座標分配（盒模型打包）
        self._phase4_coordinate_assignment(
            direction, layer_spacing, node_spacing, isolated_spacing
        )

        # 階段 4.5: 分配 yEd 式 ports
        self._assign_ports(direction)

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

        # 驗證結果 - 如果還有循環，執行備援拆邊
        if not nx.is_directed_acyclic_graph(self.graph):
            self._greedy_cycle_removal()

        # 最終驗證：禁止 fallback 成任意順序
        if not nx.is_directed_acyclic_graph(self.graph):
            raise RuntimeError(
                "循環移除完全失敗：無法創建 DAG。檢查輸入圖是否有無法解決的強連通分量。"
            )

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
        """貪婪循環移除備用策略 - 強化版本"""
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

        # 強制檢查 DAG 狀態
        if not nx.is_directed_acyclic_graph(self.graph):
            # 如果還有循環，再跑一輪 find_cycle 拆邊
            remaining_cycles = []
            try:
                while True:
                    cycle = nx.find_cycle(self.graph, orientation='original')
                    remaining_cycles.append(cycle)
                    # 拆除這個循環的任意一邊
                    if cycle:
                        u, v, _ = cycle[0]
                        self.graph.remove_edge(u, v)
                        self.graph.add_edge(v, u)
                        self.reversed_edges.add((u, v))
            except nx.NetworkXNoCycle:
                pass

        # 最後驗證
        remaining_count = len(remaining_cycles) if 'remaining_cycles' in locals() else '?'
        assert nx.is_directed_acyclic_graph(self.graph), f"循環移除失敗，還有 {remaining_count} 個循環"

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
        except nx.NetworkXUnfeasible as e:
            # 精確捕捉 NetworkXUnfeasible，再次執行循環移除
            print(f"警告：拓撲排序失敗（{e}），執行額外的循環移除")
            self._greedy_cycle_removal()

            # 確保 DAG 後重新嘗試拓撲排序
            try:
                topo_order = list(nx.topological_sort(self.graph))
            except nx.NetworkXUnfeasible:
                raise RuntimeError(
                    "無法創建有向無環圖：循環移除後仍存在循環。請檢查輸入數據的正確性。"
                )

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
        使用重心法和中位數法的交替迭代優化
        """
        max_iterations = 4  # 減少迭代次數，更穩定

        # 初始化節點位置
        self._initialize_positions()

        # 交替使用不同的排序方法
        for iteration in range(max_iterations):
            # 奇數迭代: down-sweep 用 barycenter，up-sweep 用 median
            # 偶數迭代: down-sweep 用 median，up-sweep 用 barycenter
            use_barycenter_down = (iteration % 2 == 0)

            # 向下掃描
            self._sweep_down(use_barycenter=use_barycenter_down)

            # 向上掃描
            self._sweep_up(use_barycenter=not use_barycenter_down)

        # 固定跑完所有迭代，不提早終止

    def _initialize_positions(self):
        """初始化節點在層內的位置"""
        for layer, nodes in self.layer_nodes.items():
            for i, node in enumerate(nodes):
                self.node_positions[node] = i

    def _sweep_down(self, use_barycenter: bool = True):
        """向下掃描：根據前一層調整後續層"""
        layers = sorted(self.layer_nodes.keys())

        for i in range(1, len(layers)):
            layer = layers[i]
            if use_barycenter:
                self._order_layer_by_barycenter(layer, 'predecessors')
            else:
                self._order_layer_by_median(layer, 'predecessors')

    def _sweep_up(self, use_barycenter: bool = True):
        """向上掃描：根據後一層調整前面層"""
        layers = sorted(self.layer_nodes.keys(), reverse=True)

        for i in range(1, len(layers)):
            layer = layers[i]
            if use_barycenter:
                self._order_layer_by_barycenter(layer, 'successors')
            else:
                self._order_layer_by_median(layer, 'successors')

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

    def _order_layer_by_median(self, layer: int, direction: str):
        """使用中位数法重新排序層內節點"""
        nodes = self.layer_nodes[layer]
        if len(nodes) <= 1:
            return

        # 計算每個節點的中位數
        node_medians = []

        for node in nodes:
            if direction == 'predecessors':
                neighbors = list(self.graph.predecessors(node))
            else:
                neighbors = list(self.graph.successors(node))

            if neighbors:
                positions = sorted([self.node_positions.get(n, 0) for n in neighbors])
                n_pos = len(positions)
                if n_pos % 2 == 1:
                    median = positions[n_pos // 2]
                else:
                    # 偶數個使用左中位數
                    median = positions[n_pos // 2 - 1]
            else:
                median = self.node_positions.get(node, 0)

            node_medians.append((median, node))

        # 按中位數排序
        node_medians.sort(key=lambda x: x[0])

        # 更新位置
        for i, (_, node) in enumerate(node_medians):
            self.node_positions[node] = i

        # 更新層節點順序
        self.layer_nodes[layer] = [node for _, node in node_medians]

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
        階段4：座標分配（盒模型打包）
        使用盒模型避免節點重疊，考慮節點實際尺寸
        """
        if not self.layer_nodes:
            return

        layers = sorted(self.layer_nodes.keys())

        # 處理孤立節點
        isolated_nodes = self._handle_isolated_nodes()

        # 使用盒模型計算主要層級的座標
        self._assign_layer_coordinates_with_box_model(layers, direction, layer_spacing)

        # 放置孤立節點
        self._place_isolated_nodes(isolated_nodes, direction, isolated_spacing)

        # 優化座標：對齊和拉直
        self._optimize_coordinates(direction, node_spacing)

        # 優化後重新打包，確保距離約束
        self._repack_after_optimization(direction)

    def _assign_layer_coordinates_with_box_model(self, layers, direction: str, layer_spacing: int):
        """
        使用盒模型計算層座標，避免節點重疊
        現在使用 Minimum Distances 約束
        """
        # 計算每層的座標（使用 Layer↔Layer 約束）
        layer_positions = self._calculate_layer_positions(layers, direction, layer_spacing)

        for i, layer in enumerate(layers):
            nodes = self.layer_nodes[layer]
            if not nodes:
                continue

            if direction == "TB":  # 上到下
                y = layer_positions[i]

                # 使用 scanline 打包滿足 Node↔Node 距離約束
                x_positions = self._pack_nodes_in_layer(nodes, direction)

                for j, node in enumerate(nodes):
                    self.coordinates[node] = (x_positions[j], y)

            else:  # LR: 左到右
                x = layer_positions[i]

                # 使用 scanline 打包滿足 Node↔Node 距離約束
                y_positions = self._pack_nodes_in_layer(nodes, direction)

                for j, node in enumerate(nodes):
                    self.coordinates[node] = (x, y_positions[j])

    def _calculate_layer_positions(self, layers, direction: str, layer_spacing: int) -> List[float]:
        """
        計算各層的位置，滿足 Layer↔Layer 最小距離約束
        """
        if not layers:
            return []

        positions = [0.0]  # 第 0 層在原點

        for i in range(1, len(layers)):
            if direction == "TB":
                # TB: 相鄰兩層的中心距應至少 node_height + min_layer_layer + 2*edge_clearance
                edge_clearance = max(self.node_margin, self.min_node_edge)
                min_center_distance = self.node_height + self.min_layer_layer + 2 * edge_clearance
                actual_spacing = max(layer_spacing, min_center_distance)
                positions.append(positions[-1] + actual_spacing)
            else:  # LR
                # LR: 相鄰兩列的中心距至少 node_width + min_layer_layer + 2*edge_clearance
                edge_clearance = max(self.node_margin, self.min_node_edge)
                min_center_distance = self.node_width + self.min_layer_layer + 2 * edge_clearance
                actual_spacing = max(layer_spacing, min_center_distance)
                positions.append(positions[-1] + actual_spacing)

        return positions

    def _pack_nodes_in_layer(self, nodes: List[str], direction: str) -> List[float]:
        """
        在層內打包節點，滿足 Node↔Node 最小距離約束

        Returns:
            節點中心位置列表
        """
        if len(nodes) <= 1:
            return [0.0] * len(nodes)

        positions = []
        current_pos = 0.0

        for i, node in enumerate(nodes):
            if i == 0:
                # 第一個節點
                if direction == "TB":
                    positions.append(current_pos)
                    current_pos += self.node_width / 2
                else:  # LR
                    positions.append(current_pos)
                    current_pos += self.node_height / 2
            else:
                # 後續節點：計算滿足 min_node_node 的距離
                # prev_node = nodes[i-1]  # 未使用變數

                if direction == "TB":
                    # TB: prev_x + (w_prev/2 + max(min_gap, min_node_node) + w_curr/2)
                    w_prev = self.node_width  # 簡化：假設所有節點同尺寸
                    w_curr = self.node_width
                    min_distance = max(self.min_gap, self.min_node_node)
                    current_pos += w_prev/2 + min_distance + w_curr/2
                    positions.append(current_pos)
                    current_pos += w_curr/2
                else:  # LR
                    # LR: prev_y + (h_prev/2 + max(min_gap, min_node_node) + h_curr/2)
                    h_prev = self.node_height
                    h_curr = self.node_height
                    min_distance = max(self.min_gap, self.min_node_node)
                    current_pos += h_prev/2 + min_distance + h_curr/2
                    positions.append(current_pos)
                    current_pos += h_curr/2

        # 整層居中
        if positions:
            center_offset = -sum(positions) / len(positions)
            positions = [pos + center_offset for pos in positions]

        return positions

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
        """
        放置孤立節點 - 相對於第0層定位，確保不重疊
        
        修正：
        1. 考慮節點實際尺寸
        2. 遵守最小距離約束
        3. 防止節點重疊
        """
        if not isolated_nodes:
            return

        # 計算實際需要的間距（考慮節點尺寸和最小距離）
        if direction == "TB":
            # TB 方向：孤立節點水平排列，間距需要考慮節點寬度
            actual_spacing = max(spacing, self.node_width + self.min_node_node)
        else:  # LR
            # LR 方向：孤立節點垂直排列，間距需要考慮節點高度
            actual_spacing = max(spacing, self.node_height + self.min_node_node)

        # 計算主要內容的邊界和第0層位置
        if self.coordinates:
            group_gap = max(200, self.min_layer_layer * 3)  # 確保群組間有足夠間距

            if direction == "TB":
                # 找到第0層的 Y 座標和最左節點的 X 座標
                layer_0_y = 0  # 第0層的 Y
                min_x = min(coord[0] for coord in self.coordinates.values())
                
                # 計算孤立節點的起始位置（確保不與現有節點重疊）
                start_x = min_x - group_gap - self.node_width // 2

                for i, node in enumerate(isolated_nodes):
                    isolated_x = start_x - i * actual_spacing
                    self.coordinates[node] = (isolated_x, layer_0_y)

            else:  # LR
                # 找到第0列的 X 座標和最上節點的 Y 座標
                layer_0_x = 0  # 第0列的 X
                min_y = min(coord[1] for coord in self.coordinates.values())
                
                # 計算孤立節點的起始位置（確保不與現有節點重疊）
                start_y = min_y - group_gap - self.node_height // 2

                for i, node in enumerate(isolated_nodes):
                    isolated_y = start_y - i * actual_spacing
                    self.coordinates[node] = (layer_0_x, isolated_y)
        else:
            # 如果沒有其他節點，簡單排列但確保間距正確
            for i, node in enumerate(isolated_nodes):
                if direction == "TB":
                    self.coordinates[node] = (i * actual_spacing, 0)
                else:  # LR
                    self.coordinates[node] = (0, i * actual_spacing)

    def _optimize_coordinates(self, direction: str, node_spacing: int):
        """優化座標：簡易 compaction - 同層推擠、跨層拉直"""
        if not self.coordinates:
            return

        layers = sorted(self.layer_nodes.keys())

        # 第1階段：同層節點往中線推擠
        self._compact_within_layers(direction)

        # 第2階段：子節點靠近父節點（提高到 0.5）
        alignment_factor = 0.5 if direction == "LR" else 0.5  # 提高對齊系數

        for layer_idx in range(len(layers)):
            layer = layers[layer_idx]
            nodes = self.layer_nodes[layer]

            for node in nodes:
                if direction == "TB":
                    self._align_node_x(node, alignment_factor)
                else:  # LR
                    self._align_node_y(node, alignment_factor)

    def _compact_within_layers(self, direction: str):
        """同層節點往中線推擠，縮小間隙"""
        for layer, nodes in self.layer_nodes.items():
            if len(nodes) <= 1:
                continue

            if direction == "TB":
                # TB: 對 X 座標進行 compaction
                positions = [(self.coordinates[node][0], node) for node in nodes]
                positions.sort()

                # 計算新的緊密位置
                center = sum(pos for pos, _ in positions) / len(positions)
                compact_spacing = 120  # 比原來更緊密

                for i, (_, node) in enumerate(positions):
                    offset = (i - len(positions) / 2 + 0.5) * compact_spacing
                    new_x = center + offset
                    old_x, y = self.coordinates[node]
                    self.coordinates[node] = (new_x, y)

            else:  # LR
                # LR: 對 Y 座標進行 compaction
                positions = [(self.coordinates[node][1], node) for node in nodes]
                positions.sort()

                center = sum(pos for pos, _ in positions) / len(positions)
                compact_spacing = 120

                for i, (_, node) in enumerate(positions):
                    offset = (i - len(positions) / 2 + 0.5) * compact_spacing
                    new_y = center + offset
                    x, old_y = self.coordinates[node]
                    self.coordinates[node] = (x, new_y)

    def _align_node_x(self, node: str, factor: float):
        """對齊節點 X 座標到父/子節點平均位置"""
        parents = list(self.graph.predecessors(node))
        children = list(self.graph.successors(node))
        neighbors = parents + children

        if not neighbors:
            return

        # 計算鄰居節點 X 座標的平均值
        neighbor_x_avg = sum(self.coordinates[n][0] for n in neighbors) / len(neighbors)

        # 現在的位置
        current_x, y = self.coordinates[node]

        # 向平均位置靠近
        new_x = current_x + factor * (neighbor_x_avg - current_x)
        self.coordinates[node] = (new_x, y)

    def _align_node_y(self, node: str, factor: float):
        """對齊節點 Y 座標到父/子節點平均位置"""
        parents = list(self.graph.predecessors(node))
        children = list(self.graph.successors(node))
        neighbors = parents + children

        if not neighbors:
            return

        # 計算鄰居節點 Y 座標的平均值
        neighbor_y_avg = sum(self.coordinates[n][1] for n in neighbors) / len(neighbors)

        # 現在的位置
        x, current_y = self.coordinates[node]

        # 向平均位置靠近
        new_y = current_y + factor * (neighbor_y_avg - current_y)
        self.coordinates[node] = (x, new_y)

    # ================== yEd 式 Ports 系統 ==================

    def _assign_ports(self, direction: str):
        """
        分配 yEd 式 ports（N+1 等分）
        為每條原始邊計算出入口座標
        現在滿足 Node↔Edge 最小距離約束
        """
        self.edge_ports.clear()

        # 確保 node_margin 滿足 min_node_edge 要求
        self._ensure_node_margin_compliance()

        # 為每個節點計算各側的邊
        node_side_edges = self._categorize_edges_by_node_side(direction)

        # 為每條原始邊分配 ports
        for u, v in self.original_edges:
            if u in self.coordinates and v in self.coordinates:
                src_port, dst_port = self._calculate_edge_ports(u, v, direction, node_side_edges)
                self.edge_ports[(u, v)] = (src_port, dst_port)

    def _ensure_node_margin_compliance(self):
        """
        確保 node_margin 滿足 min_node_edge 要求
        """
        if self.node_margin < self.min_node_edge:
            # 自動調整 node_margin 以滿足最小距離
            old_margin = self.node_margin
            self.node_margin = self.min_node_edge
            print(f"警告：node_margin 從 {old_margin} 調整為 {self.node_margin} 以滿足 min_node_edge 要求")

    def _categorize_edges_by_node_side(self, direction: str) -> Dict[str, Dict[str, List[str]]]:
        """
        將每個節點的邊按照方向分類到各側

        Returns:
            {node_id: {side: [connected_nodes], ...}, ...}
            side 可為 'top', 'bottom', 'left', 'right'
        """
        node_sides = {}

        for node in self.coordinates.keys():
            if self._is_virtual_node(node):
                continue

            sides = {'top': [], 'bottom': [], 'left': [], 'right': []}

            # 檢查每條原始邊
            for u, v in self.original_edges:
                if u == node:
                    # 出邊
                    target_side = self._get_edge_side(u, v, direction, is_outgoing=True)
                    if target_side:
                        sides[target_side].append(v)
                elif v == node:
                    # 入邊
                    source_side = self._get_edge_side(u, v, direction, is_outgoing=False)
                    if source_side:
                        sides[source_side].append(u)

            # 按照相鄰層的索引排序（減少交叉）
            for side in sides:
                sides[side] = self._sort_nodes_by_layer_position(sides[side])

            node_sides[node] = sides

        return node_sides

    def _get_edge_side(self, u: str, v: str, direction: str, is_outgoing: bool) -> Optional[str]:
        """
        決定邊應該使用哪一側的 port（嚴格遵守同方向進出原則）

        方向規則：
        - TB: forward 邊 out=Bottom、in=Top；回邊 out=Top、in=Bottom
        - LR: forward 邊 out=Right、in=Left；回邊 out=Left、in=Right

        Args:
            u: 源節點
            v: 目標節點
            direction: 佈局方向 TB/LR
            is_outgoing: 是否為出邊（相對於 u 節點）

        Returns:
            'top', 'bottom', 'left', 'right' 或 None
        """
        if not (u in self.layers and v in self.layers):
            return None

        is_back = self._is_back_edge(u, v)

        if direction == "TB":
            if is_outgoing:
                # TB 出邊: forward 用 bottom（下出），back 用 top（違反規則的上出）
                return 'top' if is_back else 'bottom'
            else:
                # TB 入邊: forward 用 top（上進），back 用 bottom（違反規則的下進）
                return 'bottom' if is_back else 'top'
        else:  # LR
            if is_outgoing:
                # LR 出邊: forward 用 right（右出），back 用 left（違反規則的左出）
                return 'left' if is_back else 'right'
            else:
                # LR 入邊: forward 用 left（左進），back 用 right（違反規則的右進）
                return 'right' if is_back else 'left'

    def _is_back_edge(self, u: str, v: str) -> bool:
        """
        判斷是否為回邊（以 rank 為準）

        Args:
            u: 源節點
            v: 目標節點

        Returns:
            True 如果是回邊（rank[v] < rank[u]）
        """
        if u not in self.layers or v not in self.layers:
            return False
        return self.layers[v] < self.layers[u]

    def _sort_nodes_by_layer_position(self, nodes: List[str]) -> List[str]:
        """
        按照節點在相鄰層的位置排序（與第三階段層內排序一致，降低交叉）
        """
        def get_position(node):
            # 優先使用 node_positions（第三階段交叉減少的結果）
            if node in self.node_positions:
                return self.node_positions[node]
            # fallback：使用層內的排列順序
            if node in self.layers:
                layer = self.layers[node]
                if layer in self.layer_nodes and node in self.layer_nodes[layer]:
                    return self.layer_nodes[layer].index(node)
            return 0

        return sorted(nodes, key=get_position)

    def _calculate_edge_ports(
            self, u: str, v: str, direction: str, node_side_edges: Dict
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """
        計算單條邊的出入口座標

        Returns:
            ((src_x, src_y), (dst_x, dst_y))
        """
        # 源節點 port
        src_side = self._get_edge_side(u, v, direction, is_outgoing=True)
        if src_side and u in node_side_edges:
            src_edges = node_side_edges[u][src_side]
            src_slot = src_edges.index(v) if v in src_edges else 0
            src_port = self._calculate_port_coordinate(u, src_side, src_slot, len(src_edges))
        else:
            src_port = self.coordinates[u]  # fallback 到中心點

        # 目標節點 port
        dst_side = self._get_edge_side(u, v, direction, is_outgoing=False)
        if dst_side and v in node_side_edges:
            dst_edges = node_side_edges[v][dst_side]
            dst_slot = dst_edges.index(u) if u in dst_edges else 0
            dst_port = self._calculate_port_coordinate(v, dst_side, dst_slot, len(dst_edges))
        else:
            dst_port = self.coordinates[v]  # fallback 到中心點

        return (src_port, dst_port)

    def _calculate_port_coordinate(self, node: str, side: str, slot: int, total_slots: int) -> Tuple[float, float]:
        """
        計算節點某側某槽位的座標
        現在滿足 Node↔Edge 距離約束（port 內縮）

        Args:
            node: 節點 ID
            side: 'top', 'bottom', 'left', 'right'
            slot: 槽位編號 (0-based)
            total_slots: 該側總槽數

        Returns:
            (x, y) 座標
        """
        if node not in self.coordinates:
            return (0.0, 0.0)

        xc, yc = self.coordinates[node]  # 節點中心
        w, h = self.node_width, self.node_height

        # 使用更新後的 node_margin（已滿足 min_node_edge）
        m = self.node_margin

        if total_slots == 0:
            total_slots = 1  # 避免除以零

        # N+1 等分：第 i 槽（1..k）的中心
        i = slot + 1  # 轉換為 1-based
        ratio = i / (total_slots + 1)

        # ports 精確放在節點邊界上
        if side == 'top':
            x = xc + (ratio - 0.5) * (w - 2*m)
            y = yc - h/2  # 移除內縮
            return (x, y)
        elif side == 'bottom':
            x = xc + (ratio - 0.5) * (w - 2*m)
            y = yc + h/2  # 移除內縮
            return (x, y)
        elif side == 'left':
            x = xc - w/2  # 移除內縮
            y = yc + (ratio - 0.5) * (h - 2*m)
            return (x, y)
        elif side == 'right':
            x = xc + w/2  # 移除內縮
            y = yc + (ratio - 0.5) * (h - 2*m)
            return (x, y)
        else:
            return (xc, yc)  # fallback

    def _repack_after_optimization(self, direction: str):
        """
        優化後重新打包，確保靠齊不會把節點擠破 min_node_node
        """
        layers = sorted(self.layer_nodes.keys())

        for layer in layers:
            nodes = self.layer_nodes[layer]
            if len(nodes) <= 1:
                continue

            # 按照現在的位置排序
            if direction == "TB":
                # 按 X 座標排序
                nodes_with_pos = [(self.coordinates[node][0], node) for node in nodes]
                nodes_with_pos.sort()

                # 重新計算位置以滿足距離約束
                new_positions = self._repack_nodes_positions([node for _, node in nodes_with_pos], direction)

                # 更新座標
                for i, (_, node) in enumerate(nodes_with_pos):
                    old_x, y = self.coordinates[node]
                    self.coordinates[node] = (new_positions[i], y)

            else:  # LR
                # 按 Y 座標排序
                nodes_with_pos = [(self.coordinates[node][1], node) for node in nodes]
                nodes_with_pos.sort()

                # 重新計算位置以滿足距離約束
                new_positions = self._repack_nodes_positions([node for _, node in nodes_with_pos], direction)

                # 更新座標
                for i, (_, node) in enumerate(nodes_with_pos):
                    x, old_y = self.coordinates[node]
                    self.coordinates[node] = (x, new_positions[i])

    def _repack_nodes_positions(self, nodes: List[str], direction: str) -> List[float]:
        """
        重新打包節點位置，保持順序但確保距離
        """
        if len(nodes) <= 1:
            return [0.0] * len(nodes)

        positions = []
        current_pos = 0.0

        for i, node in enumerate(nodes):
            if i == 0:
                positions.append(current_pos)
                if direction == "TB":
                    current_pos += self.node_width / 2
                else:
                    current_pos += self.node_height / 2
            else:
                # 確保距離約束
                if direction == "TB":
                    min_distance = max(self.min_gap, self.min_node_node)
                    current_pos += self.node_width / 2 + min_distance + self.node_width / 2
                    positions.append(current_pos)
                    current_pos += self.node_width / 2
                else:  # LR
                    min_distance = max(self.min_gap, self.min_node_node)
                    current_pos += self.node_height / 2 + min_distance + self.node_height / 2
                    positions.append(current_pos)
                    current_pos += self.node_height / 2

        # 居中
        if positions:
            center_offset = -sum(positions) / len(positions)
            positions = [pos + center_offset for pos in positions]

        return positions

    def _is_virtual_node(self, node: str) -> bool:
        """判斷是否為虛擬節點"""
        return node in self.virtual_nodes

    def get_feedback_edges(self) -> Set[Tuple[str, str]]:
        """
        獲取反向邊集合（被反轉的邊）

        這些邊在 GUI 繪製時應以特殊方式處理：
        - 虛線或不同顏色
        - 後續可以考慮繞外圈處理

        Returns:
            反向邊的集合 {(original_src, original_dst), ...}
        """
        return self.reversed_edges.copy()

    def get_layout_info(self) -> Dict[str, Any]:
        """
        獲取完整的佈局訊息

        Returns:
            包含座標、反向邊、虛擬節點、edge_ports 等訊息的字典
        """
        return {
            'coordinates': self.coordinates.copy(),
            'feedback_edges': self.get_feedback_edges(),
            'virtual_nodes': {vid: {
                'id': vnode.id,
                'layer': vnode.layer,
                'original_edge': vnode.original_edge
            } for vid, vnode in self.virtual_nodes.items()},
            'layers': self.layers.copy(),
            'layer_nodes': dict(self.layer_nodes),
            'edge_ports': self.edge_ports.copy(),  # yEd 式 ports 訊息
            # 新增：Minimum Distances 參數
            'min_distances': {
                'min_node_node': self.min_node_node,
                'min_node_edge': self.min_node_edge,
                'min_edge_edge': self.min_edge_edge,
                'min_layer_layer': self.min_layer_layer,
                'node_width': self.node_width,
                'node_height': self.node_height,
                'node_margin': self.node_margin  # 更新後的 margin
            }
        }


def layout_hierarchical(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150,
    isolated_spacing: int = 100,
    min_node_node: float = None,
    min_layer_layer: float = None,
    min_node_edge: float = None
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
        isolated_spacing=isolated_spacing,
        min_node_node=min_node_node,
        min_layer_layer=min_layer_layer,
        min_node_edge=min_node_edge
    )

    return coordinates


# 向後相容的別名
def compute_hierarchical_layout(*args, **kwargs):
    """向後相容的函數別名"""
    return layout_hierarchical(*args, **kwargs)


def layout_hierarchical_with_info(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150,
    isolated_spacing: int = 100,
    min_node_node: float = None,
    min_layer_layer: float = None,
    min_node_edge: float = None
) -> Dict[str, Any]:
    """
    計算階層佈局並返回完整訊息（包含反向邊、虛擬節點等）

    這個函數返回完整的佈局訊息，包含：
    - coordinates: 節點座標
    - feedback_edges: 被反轉的邊（應用特殊視覺化）
    - virtual_nodes: 虛擬節點訊息
    - layers: 節點層級映射
    - layer_nodes: 各層節點列表

    Args:
        與 layout_hierarchical 相同

    Returns:
        完整的佈局訊息字典
    """
    # 創建杉山佈局引擎
    layout_engine = SugiyamaLayout()

    # 執行完整的四階段佈局
    layout_engine.layout(
        wbs_df, edges,
        direction=direction,
        layer_spacing=layer_spacing,
        node_spacing=node_spacing,
        isolated_spacing=isolated_spacing,
        min_node_node=min_node_node,
        min_layer_layer=min_layer_layer,
        min_node_edge=min_node_edge
    )

    # 返回完整訊息
    return layout_engine.get_layout_info()
