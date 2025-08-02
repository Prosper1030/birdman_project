"""視覺化相關函式，使用分層佈局"""
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import networkx as nx


def layered_layout(G, layer_map):
    """
    根據節點的 'Layer' 屬性計算分層佈局位置。
    """
    pos = {}
    layers = defaultdict(list)
    for node, layer_idx in layer_map.items():
        # 確保 layer_idx 是有效的數字
        if layer_idx is not None and isinstance(layer_idx, (int, float)):
            layers[int(layer_idx)].append(node)

    for layer_idx, nodes in sorted(layers.items()):
        node_count_in_layer = len(nodes)
        for i, node in enumerate(nodes):
            x = layer_idx
            y = (i - (node_count_in_layer - 1) / 2.0) * 1.5
            pos[node] = (x, y)

    return pos


def create_dependency_graph_figure(
    G: nx.DiGraph,
    scc_map: dict,
    layer_map: dict,
    viz_params: dict,
    critical_path_edges: set = None,
) -> Figure:
    """建立任務依賴關係圖 (使用分層佈局)"""

    # 嘗試設定支援中文的字體
    try:
        plt.rcParams['font.sans-serif'] = [
            'Microsoft JhengHei',
            'Heiti TC',
            'Arial Unicode MS',
        ]
        plt.rcParams['axes.unicode_minus'] = False
    except Exception as e:  # pylint: disable=broad-except
        # 不同環境下可能因字體名稱或 matplotlib 設定產生例外
        print(f"警告：設定中文字體時發生錯誤: {e}")

    # 確保使用 Agg backend 避免創建額外視窗
    import matplotlib
    matplotlib.use('Agg')

    fig = Figure(figsize=(18, 20), dpi=100)
    ax = fig.add_subplot(111)

    # --- 依照當前主題設定背景色 ---
    fig.patch.set_facecolor(plt.rcParams['figure.facecolor'])
    ax.set_facecolor(plt.rcParams['axes.facecolor'])

    # --- 使用新的分層佈局 ---
    pos = layered_layout(G, layer_map)

    # 依節點類型設定顏色
    palette = viz_params.get('scc_color_palette', [])
    default_color = viz_params.get('node_color', 'skyblue')
    merged_color = viz_params.get('merged_node_color', 'lightcoral')
    node_colors = []

    scc_counts = defaultdict(int)
    for scc_id in scc_map.values():
        if scc_id != -1 and scc_id is not None:
            scc_counts[scc_id] += 1

    for node in G.nodes():
        # 合併後節點的 Task ID 會包含 "M"，以特殊顏色顯示
        if isinstance(node, str) and node.startswith('M'):
            node_colors.append(merged_color)
            continue

        scc_id = scc_map.get(node, -1)
        if scc_id != -1 and scc_counts[scc_id] > 1:
            if palette:
                node_colors.append(palette[scc_id % len(palette)])
            else:
                node_colors.append('orange')  # 備用顏色
        else:
            node_colors.append(default_color)

    # 1. 繪製節點
    node_size = 2500
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=node_size,
    )

    # 2. 繪製邊線
    if critical_path_edges:
        # 分別繪製關鍵路徑和非關鍵路徑的邊線
        critical_edges = [(u, v) for u, v in G.edges() if (u, v) in critical_path_edges]
        non_critical_edges = [(u, v) for u, v in G.edges() if (u, v) not in critical_path_edges]
        
        # 繪製非關鍵路徑邊線（使用預設顏色）
        if non_critical_edges:
            nx.draw_networkx_edges(
                G,
                pos,
                ax=ax,
                edgelist=non_critical_edges,
                edge_color=plt.rcParams['grid.color'],
                arrows=True,
                arrowstyle='->',
                arrowsize=20,
                width=1.2,
                connectionstyle='arc3,rad=0.1',
                node_size=node_size,
            )
        
        # 繪製關鍵路徑邊線（紅色）
        if critical_edges:
            nx.draw_networkx_edges(
                G,
                pos,
                ax=ax,
                edgelist=critical_edges,
                edge_color='red',
                arrows=True,
                arrowstyle='->',
                arrowsize=20,
                width=2.0,  # 關鍵路徑線條稍微粗一點
                connectionstyle='arc3,rad=0.1',
                node_size=node_size,
            )
    else:
        # 沒有關鍵路徑資訊時，使用預設繪製方式
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color=plt.rcParams['grid.color'],
            arrows=True,
            arrowstyle='->',
            arrowsize=20,
            width=1.2,
            connectionstyle='arc3,rad=0.1',
            node_size=node_size,
        )

    # 3. 繪製標籤
    nx.draw_networkx_labels(
        G,
        pos,
        ax=ax,
        font_size=viz_params.get('font_size', 9),
        font_color=plt.rcParams['text.color'],
        font_weight='bold',
    )

    for spine in ax.spines.values():
        spine.set_edgecolor(plt.rcParams['axes.edgecolor'])

    ax.set_title(
        '任務依賴關係分層圖',
        fontsize=18,
        color=plt.rcParams['axes.labelcolor'],
    )
    fig.tight_layout()
    return fig
