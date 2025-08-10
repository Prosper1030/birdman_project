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
        except nx.NetworkXUnfeasible:
            # 如果檢測到不可行（還有循環），再次執行循環移除
            print("警告：檢測到殘留循環，執行額外的循環移除")
            self._greedy_cycle_removal()

            # 確保 DAG 後重新嘗試拓撲排序
            if nx.is_directed_acyclic_graph(self.graph):
                topo_order = list(nx.topological_sort(self.graph))
            else:
                raise RuntimeError("無法創建有向無環圖，循環移除失敗")

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
        """放置孤立節點 - 相對於第0層定位"""
        if not isolated_nodes:
            return

        # 計算主要內容的邊界和第0層位置
        if self.coordinates:
            group_gap = 200  # 群組間距

            if direction == "TB":
                # 找到第0層的 Y 座標和最左節點的 X 座標
                layer_0_y = 0  # 第0層的 Y
                min_x = min(coord[0] for coord in self.coordinates.values())

                for i, node in enumerate(isolated_nodes):
                    isolated_x = min_x - group_gap - i * spacing
                    self.coordinates[node] = (isolated_x, layer_0_y)

            else:  # LR
                # 找到第0列的 X 座標和最上節點的 Y 座標
                layer_0_x = 0  # 第0列的 X
                min_y = min(coord[1] for coord in self.coordinates.values())

                for i, node in enumerate(isolated_nodes):
                    isolated_y = min_y - group_gap - i * spacing
                    self.coordinates[node] = (layer_0_x, isolated_y)
        else:
            # 如果沒有其他節點，簡單排列
            for i, node in enumerate(isolated_nodes):
                if direction == "TB":
                    self.coordinates[node] = (i * spacing, 0)
                else:
                    self.coordinates[node] = (0, i * spacing)

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
            包含座標、反向邊、虛擬節點等訊息的字典
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
            'layer_nodes': dict(self.layer_nodes)
        }


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


def layout_hierarchical_with_info(
    wbs_df: pd.DataFrame,
    edges: Set[Tuple[str, str]] = None,
    *,
    direction: str = "TB",
    layer_spacing: int = 200,
    node_spacing: int = 150,
    isolated_spacing: int = 100
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
        isolated_spacing=isolated_spacing
    )

    # 返回完整訊息
    return layout_engine.get_layout_info()
