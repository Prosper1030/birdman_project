"""視覺化相關函式"""
import networkx as nx
from matplotlib.figure import Figure


def create_dependency_graph_figure(
    G: nx.DiGraph,
    sccMap: dict,
    vizParams: dict,
) -> Figure:
    """建立任務依賴關係圖

    依據 ``sccMap`` 提供的 SCC_ID 上色，未屬於任何 SCC 的節點使用
    ``vizParams['node_color']``，其餘則循環套用 ``vizParams['scc_color_palette']``。
    回傳 Matplotlib ``Figure`` 物件，可嵌入至 PyQt5 介面。
    """
    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)

    palette = vizParams.get('scc_color_palette', [])
    default_color = vizParams.get('node_color', 'skyblue')
    font_size = vizParams.get('font_size', 8)

    colors = []
    for node in G.nodes:
        scc_id = sccMap.get(node, -1)
        if scc_id == -1 or scc_id is None:
            colors.append(default_color)
        else:
            if palette:
                colors.append(palette[scc_id % len(palette)])
            else:
                colors.append(default_color)

    pos = nx.spring_layout(G)
    nx.draw(G, pos, ax=ax, with_labels=True,
            node_color=colors, font_size=font_size)
    ax.axis('off')
    fig.tight_layout()
    return fig
