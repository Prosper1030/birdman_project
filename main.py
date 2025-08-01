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
from src.cpm_processor import (
    cpmForwardPass,
    cpmBackwardPass,
    calculateSlack,
    findCriticalPath,
    extractDurationFromWbs,
    convertHoursToDays,
)


def main():
    parser = argparse.ArgumentParser(description="DSM 排序工具")
    parser.add_argument("--dsm", required=True)
    parser.add_argument("--wbs", required=True)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--cmp", action="store_true", help="執行 CPM 分析")
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

    if args.cmp:
        print("開始執行 CPM 分析...")
        cmp_params = config.get('cmp_params', {})
        duration_field = cmp_params.get('default_duration_field', 'Te_expert')
        work_hours_per_day = cmp_params.get('work_hours_per_day', 8)

        durations_hours = extractDurationFromWbs(wbs_sorted, duration_field)
        durations_days = {
            tid: convertHoursToDays(hours, work_hours_per_day)
            for tid, hours in durations_hours.items()
        }

        forward_data = cpmForwardPass(G, durations_days)
        project_end = max(ef for _, ef in forward_data.values())
        backward_data = cpmBackwardPass(G, durations_days, project_end)
        cpm_result = calculateSlack(forward_data, backward_data, G)
        critical_path = findCriticalPath(cpm_result)

        wbs_with_cpm = wbs_sorted.copy()
        for col in ['ES', 'EF', 'LS', 'LF', 'TF', 'FF', 'Critical']:
            wbs_with_cpm[col] = wbs_with_cpm['Task ID'].map(
                cpm_result[col].to_dict()).fillna(0)

        out_cpm = Path("cmp_analysis.csv")
        wbs_with_cpm.to_csv(out_cpm, index=False, encoding="utf-8-sig")
        print(f"已輸出 CPM 分析結果：{out_cpm}")
        print(f"專案總工期：{project_end:.1f} 天")
        print(f"關鍵路徑：{' → '.join(critical_path)}")


if __name__ == "__main__":
    main()
