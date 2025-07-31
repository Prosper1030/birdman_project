import argparse
from pathlib import Path
import json
from src.dsm_processor import (
    readDsm,
    buildGraph,
    computeLayersAndScc,
    reorderDsm,
)
from src.wbs_processor import readWbs, mergeByScc, validateIds


def main():
    parser = argparse.ArgumentParser(description="DSM 排序工具")
    parser.add_argument("--dsm", required=True)
    parser.add_argument("--wbs", required=True)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()

    dsm = readDsm(args.dsm)
    G = buildGraph(dsm)

    layers, scc_id = computeLayersAndScc(G)

    wbs = readWbs(args.wbs)
    validateIds(wbs, dsm)

    wbs["Layer"] = wbs["Task ID"].map(layers).fillna(-1).astype(int)
    wbs["SCC_ID"] = wbs["Task ID"].map(scc_id).fillna(-1).astype(int)
    wbs_sorted = wbs.sort_values(
        by=["Layer", "Task ID"]).reset_index(drop=True)

    out_sorted = Path("sorted_wbs.csv")
    wbs_sorted.to_csv(out_sorted, index=False, encoding="utf-8-sig")
    print(f"已輸出 {out_sorted}")

    sorted_dsm = reorderDsm(dsm, wbs_sorted["Task ID"].tolist())
    out_dsm = Path("sorted_dsm.csv")
    sorted_dsm.to_csv(out_dsm, encoding="utf-8-sig")
    print(f"已輸出 {out_dsm}")

    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    k_params = config.get('merge_k_params', {})
    merged = mergeByScc(wbs_sorted, k_params)
    out_merged = Path("merged_wbs.csv")
    merged.to_csv(out_merged, index=False, encoding="utf-8-sig")
    print(f"已輸出 {out_merged}")


if __name__ == "__main__":
    main()
