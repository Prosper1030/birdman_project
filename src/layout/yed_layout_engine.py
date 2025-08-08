#!/usr/bin/env python3
"""
yEd 風格布局引擎 - 完整實現
支援階層式、正交、樹狀、環形等多種布局
"""

import math
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum
from collections import defaultdict, deque

import networkx as nx
from PyQt5.QtCore import QPointF, QRectF


class LayoutStyle(Enum):
    """布局風格枚舉"""
    HIERARCHICAL = "hierarchical"      # 階層式（Sugiyama）
    ORTHOGONAL = "orthogonal"          # 正交布局
    TREE = "tree"                      # 樹狀布局
    CIRCULAR = "circular"              # 環形布局
    RADIAL = "radial"                  # 放射狀布局
    FORCE_DIRECTED = "force_directed"  # 力導向布局
    GRID = "grid"                      # 網格布局
    ORGANIC = "organic"                # 有機布局


class NodeAlignment(Enum):
    """節點對齊方式"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class YEdLayoutEngine:
    """yEd 風格布局引擎"""
    
    def __init__(self):
        # 布局參數
        self.node_spacing_horizontal = 80
        self.node_spacing_vertical = 120
        self.layer_spacing = 200
        self.node_size = QPointF(120, 60)
        self.margin = 50
        
        # 進階參數
        self.edge_routing_style = "orthogonal"
        self.minimize_crossings = True
        self.center_nodes = True
        self.compact_layout = False
        
        # 布局快取
        self._layout_cache = {}
    
    def layout(self, nodes: Dict, edges: List[Tuple], style: LayoutStyle) -> Dict:
        """
        執行布局算法
        
        Args:
            nodes: {node_id: node_object} 字典
            edges: [(src_id, dst_id), ...] 邊列表
            style: 布局風格
            
        Returns:
            {node_id: QPointF} 節點位置字典
        """
        # 建立圖
        graph = self._build_graph(nodes, edges)
        
        # 根據風格選擇算法
        if style == LayoutStyle.HIERARCHICAL:
            return self._hierarchical_layout(graph, nodes)
        elif style == LayoutStyle.ORTHOGONAL:
            return self._orthogonal_layout(graph, nodes)
        elif style == LayoutStyle.TREE:
            return self._tree_layout(graph, nodes)
        elif style == LayoutStyle.CIRCULAR:
            return self._circular_layout(graph, nodes)
        elif style == LayoutStyle.RADIAL:
            return self._radial_layout(graph, nodes)
        elif style == LayoutStyle.FORCE_DIRECTED:
            return self._force_directed_layout(graph, nodes)
        elif style == LayoutStyle.GRID:
            return self._grid_layout(graph, nodes)
        elif style == LayoutStyle.ORGANIC:
            return self._organic_layout(graph, nodes)
        else:
            return self._simple_layout(nodes)
    
    def _build_graph(self, nodes: Dict, edges: List[Tuple]) -> nx.DiGraph:
        """建立 NetworkX 圖"""
        graph = nx.DiGraph()
        
        for node_id in nodes:
            graph.add_node(node_id)
        
        for src, dst in edges:
            graph.add_edge(src, dst)
        
        return graph
    
    def _hierarchical_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """
        階層式布局 - Sugiyama 演算法
        1. 循環移除
        2. 層級分配
        3. 交叉最小化
        4. 座標分配
        """
        positions = {}
        
        # 步驟1：循環移除（如果需要）
        if not nx.is_directed_acyclic_graph(graph):
            # 找到並移除反饋邊
            feedback_edges = self._find_feedback_edges(graph)
            temp_graph = graph.copy()
            temp_graph.remove_edges_from(feedback_edges)
        else:
            temp_graph = graph
            feedback_edges = []
        
        # 步驟2：層級分配
        layers = self._assign_layers(temp_graph)
        
        # 步驟3：交叉最小化
        if self.minimize_crossings:
            layers = self._minimize_crossings_barycenter(temp_graph, layers)
        
        # 步驟4：座標分配
        for layer_idx, layer_nodes in enumerate(layers):
            layer_width = len(layer_nodes) * self.node_spacing_horizontal
            start_x = -layer_width / 2 + self.node_spacing_horizontal / 2
            
            for node_idx, node_id in enumerate(layer_nodes):
                x = start_x + node_idx * self.node_spacing_horizontal
                y = layer_idx * self.layer_spacing
                positions[node_id] = QPointF(x, y)
        
        # 處理未分配的節點
        for node_id in nodes:
            if node_id not in positions:
                positions[node_id] = QPointF(0, 0)
        
        return positions
    
    def _find_feedback_edges(self, graph: nx.DiGraph) -> List[Tuple]:
        """找到反饋邊（造成循環的邊）"""
        # 使用簡單的 DFS 方法
        feedback_edges = []
        
        try:
            # 嘗試拓樸排序，如果失敗則有循環
            list(nx.topological_sort(graph))
        except nx.NetworkXError:
            # 找到所有強連通分量
            sccs = list(nx.strongly_connected_components(graph))
            for scc in sccs:
                if len(scc) > 1:
                    # 在 SCC 內找到一條邊作為反饋邊
                    subgraph = graph.subgraph(scc)
                    for edge in subgraph.edges():
                        feedback_edges.append(edge)
                        break
        
        return feedback_edges
    
    def _assign_layers(self, graph: nx.DiGraph) -> List[List]:
        """分配節點到層級"""
        layers = []
        layer_dict = {}
        
        # 計算每個節點的層級
        for node in nx.topological_sort(graph):
            predecessors = list(graph.predecessors(node))
            if not predecessors:
                layer_dict[node] = 0
            else:
                layer_dict[node] = max(layer_dict.get(pred, 0) for pred in predecessors) + 1
        
        # 組織層級
        max_layer = max(layer_dict.values()) if layer_dict else 0
        for i in range(max_layer + 1):
            layer_nodes = [n for n, l in layer_dict.items() if l == i]
            layers.append(layer_nodes)
        
        return layers
    
    def _minimize_crossings_barycenter(self, graph: nx.DiGraph, layers: List[List]) -> List[List]:
        """使用重心法最小化交叉"""
        if len(layers) <= 1:
            return layers
        
        # 多次迭代優化
        for _ in range(3):
            # 從上到下掃描
            for i in range(1, len(layers)):
                layers[i] = self._order_layer_by_barycenter(
                    graph, layers[i-1], layers[i], direction='down'
                )
            
            # 從下到上掃描
            for i in range(len(layers) - 2, -1, -1):
                layers[i] = self._order_layer_by_barycenter(
                    graph, layers[i+1], layers[i], direction='up'
                )
        
        return layers
    
    def _order_layer_by_barycenter(self, graph: nx.DiGraph, fixed_layer: List, 
                                   free_layer: List, direction: str) -> List:
        """根據重心排序層級中的節點"""
        # 計算每個節點的重心
        barycenters = {}
        
        for node in free_layer:
            if direction == 'down':
                neighbors = [n for n in graph.predecessors(node) if n in fixed_layer]
            else:
                neighbors = [n for n in graph.successors(node) if n in fixed_layer]
            
            if neighbors:
                positions = [fixed_layer.index(n) for n in neighbors]
                barycenters[node] = sum(positions) / len(positions)
            else:
                barycenters[node] = len(fixed_layer) / 2
        
        # 根據重心排序
        return sorted(free_layer, key=lambda n: barycenters.get(n, 0))
    
    def _orthogonal_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """正交布局 - 網格對齊"""
        positions = {}
        
        # 使用階層式布局作為基礎
        base_positions = self._hierarchical_layout(graph, nodes)
        
        # 對齊到網格
        grid_size = min(self.node_spacing_horizontal, self.node_spacing_vertical) / 2
        
        for node_id, pos in base_positions.items():
            x = round(pos.x() / grid_size) * grid_size
            y = round(pos.y() / grid_size) * grid_size
            positions[node_id] = QPointF(x, y)
        
        return positions
    
    def _tree_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """樹狀布局"""
        positions = {}
        
        # 找到根節點
        roots = [n for n in graph.nodes() if graph.in_degree(n) == 0]
        if not roots:
            roots = [list(graph.nodes())[0]] if graph.nodes() else []
        
        # 對每個根節點進行布局
        y_offset = 0
        for root in roots:
            tree_positions = self._layout_tree_recursive(graph, root, 0, 0)
            
            # 調整位置
            for node_id, pos in tree_positions.items():
                positions[node_id] = QPointF(pos[0], pos[1] + y_offset)
            
            # 計算下一棵樹的偏移
            if tree_positions:
                max_y = max(p[1] for p in tree_positions.values())
                y_offset += max_y + self.layer_spacing
        
        # 處理未訪問的節點
        for node_id in nodes:
            if node_id not in positions:
                positions[node_id] = QPointF(0, y_offset)
                y_offset += self.node_spacing_vertical
        
        return positions
    
    def _layout_tree_recursive(self, graph: nx.DiGraph, node, x: float, y: float, 
                              visited: Optional[Set] = None) -> Dict:
        """遞歸布局樹"""
        if visited is None:
            visited = set()
        
        if node in visited:
            return {}
        
        visited.add(node)
        positions = {node: (x, y)}
        
        children = [n for n in graph.successors(node) if n not in visited]
        if children:
            # 計算子節點的總寬度
            child_width = len(children) * self.node_spacing_horizontal
            start_x = x - child_width / 2 + self.node_spacing_horizontal / 2
            
            for i, child in enumerate(children):
                child_x = start_x + i * self.node_spacing_horizontal
                child_y = y + self.layer_spacing
                
                child_positions = self._layout_tree_recursive(
                    graph, child, child_x, child_y, visited
                )
                positions.update(child_positions)
        
        return positions
    
    def _circular_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """環形布局"""
        positions = {}
        node_list = list(nodes.keys())
        n = len(node_list)
        
        if n == 0:
            return positions
        
        # 計算半徑
        radius = max(100, n * 20)
        
        # 均勻分布節點
        for i, node_id in enumerate(node_list):
            angle = 2 * math.pi * i / n
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            positions[node_id] = QPointF(x, y)
        
        return positions
    
    def _radial_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """放射狀布局"""
        positions = {}
        
        # 找到中心節點（度數最高的節點）
        if graph.nodes():
            center = max(graph.nodes(), key=lambda n: graph.degree(n))
            positions[center] = QPointF(0, 0)
            
            # BFS 分層
            visited = {center}
            current_layer = [center]
            layer_radius = 150
            
            while current_layer:
                next_layer = []
                
                for node in current_layer:
                    neighbors = [n for n in graph.neighbors(node) if n not in visited]
                    next_layer.extend(neighbors)
                    visited.update(neighbors)
                
                if next_layer:
                    # 在當前半徑上均勻分布節點
                    n = len(next_layer)
                    for i, node_id in enumerate(next_layer):
                        angle = 2 * math.pi * i / n
                        x = layer_radius * math.cos(angle)
                        y = layer_radius * math.sin(angle)
                        positions[node_id] = QPointF(x, y)
                    
                    layer_radius += 150
                    current_layer = next_layer
                else:
                    break
        
        # 處理未訪問的節點
        for node_id in nodes:
            if node_id not in positions:
                positions[node_id] = QPointF(layer_radius, 0)
        
        return positions
    
    def _force_directed_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """力導向布局 - 使用 NetworkX 的 spring_layout"""
        positions = {}
        
        if graph.nodes():
            # 使用 NetworkX 的 spring 布局
            nx_positions = nx.spring_layout(graph, k=2, iterations=50, scale=300)
            
            for node_id, (x, y) in nx_positions.items():
                positions[node_id] = QPointF(x * 300, y * 300)
        
        return positions
    
    def _grid_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """網格布局"""
        positions = {}
        node_list = list(nodes.keys())
        n = len(node_list)
        
        if n == 0:
            return positions
        
        # 計算網格大小
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        
        # 分配位置
        for i, node_id in enumerate(node_list):
            row = i // cols
            col = i % cols
            
            x = col * self.node_spacing_horizontal - (cols - 1) * self.node_spacing_horizontal / 2
            y = row * self.node_spacing_vertical - (rows - 1) * self.node_spacing_vertical / 2
            
            positions[node_id] = QPointF(x, y)
        
        return positions
    
    def _organic_layout(self, graph: nx.DiGraph, nodes: Dict) -> Dict:
        """有機布局 - 結合力導向和層級概念"""
        # 先使用力導向布局
        positions = self._force_directed_layout(graph, nodes)
        
        # 然後根據層級調整 y 座標
        if nx.is_directed_acyclic_graph(graph):
            layers = self._assign_layers(graph)
            
            for layer_idx, layer_nodes in enumerate(layers):
                y = layer_idx * self.layer_spacing
                for node_id in layer_nodes:
                    if node_id in positions:
                        pos = positions[node_id]
                        positions[node_id] = QPointF(pos.x(), y)
        
        return positions
    
    def _simple_layout(self, nodes: Dict) -> Dict:
        """簡單布局 - 後備方案"""
        positions = {}
        node_list = list(nodes.keys())
        
        for i, node_id in enumerate(node_list):
            x = (i % 5) * self.node_spacing_horizontal
            y = (i // 5) * self.node_spacing_vertical
            positions[node_id] = QPointF(x, y)
        
        return positions
    
    def apply_layout_with_animation(self, nodes: Dict, target_positions: Dict, 
                                   duration: int = 500) -> List:
        """
        應用布局並生成動畫數據
        
        Returns:
            動畫幀列表
        """
        animation_frames = []
        steps = 20  # 動畫步數
        
        for step in range(steps + 1):
            t = step / steps
            frame = {}
            
            for node_id, node in nodes.items():
                if node_id in target_positions:
                    current_pos = node.pos()
                    target_pos = target_positions[node_id]
                    
                    # 插值計算
                    x = current_pos.x() + (target_pos.x() - current_pos.x()) * t
                    y = current_pos.y() + (target_pos.y() - current_pos.y()) * t
                    
                    frame[node_id] = QPointF(x, y)
            
            animation_frames.append(frame)
        
        return animation_frames
    
    def optimize_layout(self, positions: Dict, graph: nx.DiGraph) -> Dict:
        """優化布局 - 減少重疊和改善美觀"""
        optimized = dict(positions)
        
        # 檢測並解決重疊
        node_ids = list(positions.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                pos1 = optimized[node_ids[i]]
                pos2 = optimized[node_ids[j]]
                
                # 計算距離
                dx = pos2.x() - pos1.x()
                dy = pos2.y() - pos1.y()
                distance = math.sqrt(dx * dx + dy * dy)
                
                # 如果太近則分開
                min_distance = self.node_spacing_horizontal
                if distance < min_distance and distance > 0:
                    # 計算排斥力
                    factor = (min_distance - distance) / distance / 2
                    offset_x = dx * factor
                    offset_y = dy * factor
                    
                    optimized[node_ids[i]] = QPointF(
                        pos1.x() - offset_x,
                        pos1.y() - offset_y
                    )
                    optimized[node_ids[j]] = QPointF(
                        pos2.x() + offset_x,
                        pos2.y() + offset_y
                    )
        
        return optimized