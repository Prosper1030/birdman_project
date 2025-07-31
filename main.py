import argparse
from pathlib import Path

from src.dsm_processor import readDsm, buildGraph, computeLayersAndScc
from src.wbs_processor import readWbs, mergeByScc


def main():
    parser = argparse.ArgumentParser(description="DSM 排序工具")
    parser.add_argument("--dsm", required=True)
    parser.add_argument("--wbs", required=True)
    parser.add_argument("--year", type=str, default="")
    args = parser.parse_args()

    dsm = readDsm(args.dsm)
    G = buildGraph(dsm)
    layers, scc_id = computeLayersAndScc(G)

    wbs = readWbs(args.wbs)
    if "Task ID" not in wbs.columns:
        raise ValueError("WBS 缺少 Task ID 欄位")

    wbs["Layer"] = wbs["Task ID"].map(layers).fillna(-1).astype(int)
    wbs["SCC_ID"] = wbs["Task ID"].map(scc_id).fillna(-1).astype(int)
    wbs_sorted = wbs.sort_values(by=["Layer", "Task ID"]).reset_index(drop=True)

    out_sorted = Path("sorted_wbs.csv")
    wbs_sorted.to_csv(out_sorted, index=False, encoding="utf-8-sig")
    print(f"已輸出 {out_sorted}")

    merged = mergeByScc(wbs_sorted, args.year)
    out_merged = Path("merged_wbs.csv")
    merged.to_csv(out_merged, index=False, encoding="utf-8-sig")
    print(f"已輸出 {out_merged}")


if __name__ == "__main__":
    main()
