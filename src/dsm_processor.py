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


def reorderDsm(dsm: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    """依指定順序重新排列 DSM 的列與欄"""
    if set(order) != set(dsm.index):
        raise ValueError("指定的順序與 DSM 任務不符")
    # 檢查排序陣列是否有重複值
    if len(order) != len(set(order)):
        raise ValueError("排序陣列含有重複 Task ID")
    return dsm.loc[order, order]


def process_dsm(
    dsm: pd.DataFrame,
    wbs: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, nx.DiGraph]:
    """整合 DSM 與 WBS，回傳排序後的 DSM、WBS 以及依賴圖"""
    G = buildGraph(dsm)
    layers, scc_map = computeLayersAndScc(G)

    wbs_sorted = wbs.copy()
    wbs_sorted["Layer"] = wbs_sorted["Task ID"].map(
        layers).fillna(-1).astype(int)
    wbs_sorted["SCC_ID"] = wbs_sorted["Task ID"].map(
        scc_map).fillna(-1).astype(int)
    wbs_sorted = wbs_sorted.sort_values(
        by=["Layer", "Task ID"]).reset_index(drop=True)

    sorted_dsm = reorderDsm(dsm, wbs_sorted["Task ID"].tolist())
    return sorted_dsm, wbs_sorted, G


def create_merged_graph(
    G: nx.DiGraph, scc_map: dict, merged_wbs: pd.DataFrame
) -> nx.DiGraph:
    """以濃縮圖 (Condensation) 為基礎，建立合併後的任務依賴圖

    此方法可確保合併後的圖為 DAG (無循環)。
    """
    sccs = list(nx.strongly_connected_components(G))
    condensation = nx.condensation(G, sccs)

    scc_id_to_merged_id = {}
    for scc_id, grp in merged_wbs.groupby("SCC_ID"):
        scc_id_to_merged_id[scc_id] = grp.iloc[0]["Task ID"]

    # 建立 scc 節點索引與 scc_id 的對應
    node_to_scc_id = {
        node: scc_map.get(node) for node in G.nodes()
    }
    scc_index_map = {
        i: scc_id_to_merged_id[node_to_scc_id[list(scc)[0]]]
        for i, scc in enumerate(sccs)
        if node_to_scc_id[list(scc)[0]] in scc_id_to_merged_id
    }

    merged_graph = nx.relabel_nodes(condensation, scc_index_map, copy=True)
    return merged_graph
