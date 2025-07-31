import pandas as pd
import networkx as nx


def readDsm(path: str) -> pd.DataFrame:
    """讀取 DSM CSV 並檢查方陣"""
    dsm = pd.read_csv(path, index_col=0, encoding="utf-8-sig")
    # 檢查列數與欄數是否相等
    if dsm.shape[0] != dsm.shape[1]:
        raise ValueError("DSM 必須為方陣，請檢查檔案內容")
    return dsm


def buildGraph(dsm: pd.DataFrame) -> nx.DiGraph:
    """根據 DSM 建立依賴圖

    DSM 內若某格為 1，代表列任務必須等待欄任務完成，
    因此在圖中視為「欄任務 -> 列任務」的有向邊。
    """
    G = nx.DiGraph()
    tasks = dsm.columns.tolist()
    G.add_nodes_from(tasks)
    for row_task in dsm.index:
        for col_task in dsm.columns:
            if dsm.at[row_task, col_task] == 1:
                G.add_edge(col_task, row_task)
    return G


def assignLayer(G: nx.DiGraph) -> dict:
    """依拓撲排序結果計算各節點層次"""
    order = list(nx.topological_sort(G))

    layer = {node: 0 for node in G.nodes}
    for node in order:
        preds = list(G.predecessors(node))
        if preds:
            layer[node] = max(layer[p] for p in preds) + 1
    return layer


def computeLayersAndScc(G: nx.DiGraph) -> tuple[dict, dict]:
    """回傳節點層次與所屬 SCC_ID"""
    sccs = list(nx.strongly_connected_components(G))
    condensed = nx.condensation(G, sccs)
    cond_layers = assignLayer(condensed)
    layer_map = {}
    scc_map = {}
    for idx, comp in enumerate(sccs):
        for node in comp:
            scc_map[node] = idx
            layer_map[node] = cond_layers[idx]
    return layer_map, scc_map

