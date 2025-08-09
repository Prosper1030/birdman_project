"""視覺化相關函式"""
import networkx as nx
from matplotlib.figure import Figure


def create_dependency_graph_figure(
    G: nx.DiGraph,
    sccMap: dict,
    layerMap: dict,
    vizParams: dict,
    critical_path_edges=None,
) -> Figure:
    """建立任務依賴關係圖

    依據 ``sccMap`` 提供的 SCC_ID 上色，未屬於任何 SCC 的節點使用
    ``vizParams['node_color']``，其餘則循環套用 ``vizParams['scc_color_palette']``。
    如果提供 ``critical_path_edges``，會以特殊樣式繪製關鍵路徑邊線。
    回傳 Matplotlib ``Figure`` 物件，可嵌入至 PyQt5 介面。
    
    Args:
        G: 有向圖
        sccMap: 強連通分量映射
        layerMap: 層級映射 (目前未使用，保留供未來擴展)
        vizParams: 視覺化參數
        critical_path_edges: 關鍵路徑邊線列表 (可選)
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
    
    # 繪製一般邊線
    if critical_path_edges:
        # 分離一般邊線和關鍵路徑邊線
        normal_edges = [(u, v) for u, v in G.edges() if (u, v) not in critical_path_edges]
        
        # 先繪製一般邊線
        if normal_edges:
            nx.draw_networkx_edges(G, pos, edgelist=normal_edges, ax=ax, 
                                 edge_color='gray', alpha=0.5)
        
        # 再繪製關鍵路徑邊線 (較粗、紅色)
        if critical_path_edges:
            nx.draw_networkx_edges(G, pos, edgelist=critical_path_edges, ax=ax,
                                 edge_color='red', width=2.0)
        
        # 最後繪製節點和標籤
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=colors)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=font_size)
    else:
        # 使用原有的簡單繪製方法
        nx.draw(G, pos, ax=ax, with_labels=True,
                node_color=colors, font_size=font_size)
    
    ax.axis('off')
    fig.tight_layout()
    return fig
