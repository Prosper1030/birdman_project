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

    fig = Figure(figsize=(18, 20), dpi=100)
    ax = fig.add_subplot(111)

    # --- 使用新的分層佈局 ---
    pos = layered_layout(G, layer_map)

    # 根據 SCC_ID 為節點上色
    palette = viz_params.get('scc_color_palette', [])
    default_color = viz_params.get('node_color', 'skyblue')
    node_colors = []

    scc_counts = defaultdict(int)
    for scc_id in scc_map.values():
        if scc_id != -1 and scc_id is not None:
            scc_counts[scc_id] += 1

    for node in G.nodes():
        scc_id = scc_map.get(node, -1)
        if scc_id != -1 and scc_counts[scc_id] > 1:
            if palette:
                node_colors.append(palette[scc_id % len(palette)])
            else:
                node_colors.append('orange')    # 備用顏色
        else:
            node_colors.append(default_color)

    # 繪製圖形
    nx.draw(
        G,
        pos,
        ax=ax,
        with_labels=True,
        node_size=2500,
        node_color=node_colors,
        font_size=viz_params.get('font_size', 9),
        font_color='black',
        font_weight='bold',
        width=1.2,
        edge_color='gray',
        arrowsize=20,
        connectionstyle='arc3,rad=0.1'
    )

    ax.set_title("任務依賴關係分層圖", fontsize=18)
    fig.tight_layout()
    return fig
