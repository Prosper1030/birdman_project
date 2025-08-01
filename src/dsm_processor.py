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


def buildTaskMapping(
    original_wbs: pd.DataFrame, merged_wbs: pd.DataFrame
) -> dict[str, str]:
    """根據 SCC_ID 建立原始 Task ID 與合併後 Task ID 的對應關係"""
    mapping: dict[str, str] = {}
    for scc_id, grp in original_wbs.groupby("SCC_ID", sort=False):
        merged_row = merged_wbs[merged_wbs["SCC_ID"] == scc_id]
        if merged_row.empty:
            continue
        new_id = merged_row.iloc[0]["Task ID"]
        for tid in grp["Task ID"]:
            mapping[tid] = new_id
    return mapping


def buildMergedDsm(graph: nx.DiGraph, mapping: dict[str, str]) -> pd.DataFrame:
    """依照合併映射關係產生新的 DSM"""
    merged_tasks = sorted(set(mapping.values()))
    merged_dsm = pd.DataFrame(
        0, index=merged_tasks, columns=merged_tasks, dtype=int
    )
    for u, v in graph.edges():
        u_m = mapping.get(u)
        v_m = mapping.get(v)
        if u_m is None or v_m is None or u_m == v_m:
            continue
        merged_dsm.at[v_m, u_m] = 1
    return merged_dsm
