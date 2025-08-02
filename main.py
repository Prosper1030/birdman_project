import argparse
from pathlib import Path
import json
import networkx as nx
from src.dsm_processor import (
    readDsm,
    buildGraph,
    computeLayersAndScc,
    reorderDsm,
    buildTaskMapping,
    buildMergedDsm,
    process_dsm,
)
from src.wbs_processor import readWbs, mergeByScc, validateIds
from src.cpm_processor import (
    cpmForwardPass,
    cpmBackwardPass,
    calculateSlack,
    findCriticalPath,
    extractDurationFromWbs,
    monteCarloSchedule,
)
import numpy as np
from src.rcpsp_solver import solveRcpsp
from src import visualizer
from matplotlib.figure import Figure


def _save_figure(fig: Figure, path: str) -> None:
    """以副檔名決定輸出格式"""
    ext = Path(path).suffix.lower()
    fmt = 'png' if ext != '.svg' else 'svg'
    if fmt == 'svg' and not path.lower().endswith('.svg'):
        path += '.svg'
    elif fmt == 'png' and not path.lower().endswith('.png'):
        path += '.png'
    fig.savefig(path, format=fmt, bbox_inches='tight', dpi=300)


def save_gantt_chart(cpm_df, durations: dict[str, float], path: str) -> None:
    """根據 CPM 結果輸出甘特圖"""
    fig = Figure(figsize=(10, max(4, len(cpm_df) * 0.6)))
    ax = fig.add_subplot(111)
    fig.subplots_adjust(top=0.9, bottom=0.15, left=0.2, right=0.95)
    tasks = cpm_df.index.tolist()
    start_times = cpm_df['ES'].tolist()
    task_durations = [durations.get(t, 0) for t in tasks]
    y_pos = range(len(tasks))
    colors = ['red' if cpm_df.at[t, 'Critical'] else 'skyblue' for t in tasks]
    ax.barh(
        y_pos,
        task_durations,
        left=start_times,
        color=colors,
        alpha=0.8,
        height=0.6,
        edgecolor='black',
        linewidth=1,
        zorder=2,
    )
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(tasks, fontsize=10, fontweight='bold')
    ax.grid(True, axis='x', linestyle='--', color='gray', alpha=0.3, zorder=1)
    ax.set_axisbelow(True)
    ax.set_xlabel('時間 (小時)', fontsize=11, fontweight='bold')
    ax.set_title('專案甘特圖 (紅色為關鍵路徑)', fontsize=14, pad=20)
    for i, (duration, start) in enumerate(zip(task_durations, start_times)):
        if duration > 0:
            ax.text(
                start + duration + 2,
                i,
                f'{duration:.1f}h',
                va='center',
                fontsize=9,
                alpha=0.7,
            )
    ax.invert_yaxis()
    _save_figure(fig, path)


def main():
    parser = argparse.ArgumentParser(description="DSM 排序工具")
    parser.add_argument("--dsm", required=True)
    parser.add_argument("--wbs", required=True)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--cmp", action="store_true", help="執行 CPM 分析")
    parser.add_argument(
        "--export-graph",
        metavar="PATH",
        help="匯出依賴關係圖 (SVG 或 PNG)"
    )
    parser.add_argument(
        "--export-gantt",
        metavar="PATH",
        help="匯出甘特圖 (SVG 或 PNG)，需同時啟用 --cmp"
    )
    parser.add_argument(
        "--duration-field",
        metavar="FIELD",
        help="指定 CPM 工期欄位，預設為設定檔值"
    )
    parser.add_argument(
        "--monte-carlo",
        metavar="N",
        type=int,
        default=0,
        help="執行蒙地卡羅模擬的次數",
    )
    parser.add_argument(
        "--mc-confidence",
        metavar="P",
        type=float,
        default=0.9,
        help="蒙地卡羅模擬信心水準，預設 0.9",
    )
    parser.add_argument(
        "--rcpsp-opt",
        action="store_true",
        help="使用 OR-Tools 求解 RCPSP",
    )
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

    # 依原始 Task ID 與 SCC 對應建立合併映射
    task_mapping = buildTaskMapping(wbs_sorted, merged)
    # 根據映射產生合併後的 DSM
    merged_dsm_raw = buildMergedDsm(G, task_mapping)
    # 重新計算層次並建立合併後的依賴圖
    merged_dsm, _merged_wbs_sorted, merged_graph = process_dsm(
        merged_dsm_raw,
        merged,
    )

    out_merged = Path("merged_wbs.csv")
    merged.to_csv(out_merged, index=False, encoding="utf-8-sig")
    print(f"已輸出 {out_merged}")
    if args.rcpsp_opt:
        print("開始執行 RCPSP 排程...")
        cmp_params = config.get("cmp_params", {})
        duration_field = args.duration_field or cmp_params.get(
            "default_duration_field", "Te_newbie"
        )
        schedule = solveRcpsp(merged_graph, merged, duration_field)
        merged["Start"] = merged["Task ID"].map(schedule).fillna(0)
        merged["Finish"] = merged["Start"] + merged[duration_field].fillna(0)
        out_rcpsp = Path("rcpsp_schedule.csv")
        merged[["Task ID", "Start", "Finish"]].to_csv(
            out_rcpsp,
            index=False,
            encoding="utf-8-sig",
        )
        print(f"最短完工時間：{schedule['ProjectEnd']:.1f} 小時")
    if args.export_graph:
        viz_params = config.get('visualization_params', {})
        scc_map = dict(zip(wbs_sorted['Task ID'], wbs_sorted['SCC_ID']))
        layer_map = dict(zip(wbs_sorted['Task ID'], wbs_sorted['Layer']))
        fig = visualizer.create_dependency_graph_figure(
            G, scc_map, layer_map, viz_params
        )
        _save_figure(fig, args.export_graph)
        print(f"已匯出依賴關係圖至 {args.export_graph}")

    if args.cmp:
        print("開始執行 CPM 分析...")
        cmp_params = config.get('cmp_params', {})
        duration_field = args.duration_field or cmp_params.get(
            'default_duration_field', 'Te_newbie'
        )

        # 以合併後的 WBS 取得工時
        durations_hours = extractDurationFromWbs(merged, duration_field)

        # 檢查合併後圖是否存在循環依賴
        cycles = list(nx.simple_cycles(merged_graph))
        if cycles:
            cycle_str = ' -> '.join(cycles[0] + [cycles[0][0]])
            raise ValueError(f'發現循環依賴：{cycle_str}')

        forward_data = cpmForwardPass(merged_graph, durations_hours)
        project_end = max(ef for _, ef in forward_data.values())
        backward_data = cpmBackwardPass(
            merged_graph,
            durations_hours,
            project_end,
        )
        cpm_result = calculateSlack(forward_data, backward_data, merged_graph)
        critical_path = findCriticalPath(cpm_result)

        wbs_with_cpm = merged.copy()
        for col in ['ES', 'EF', 'LS', 'LF', 'TF', 'FF', 'Critical']:
            wbs_with_cpm[col] = wbs_with_cpm['Task ID'].map(
                cpm_result[col].to_dict()).fillna(0)

        out_cpm = Path("cmp_analysis.csv")
        wbs_with_cpm.to_csv(out_cpm, index=False, encoding="utf-8-sig")
        print(f"已輸出 CPM 分析結果：{out_cpm}")
        print(f"專案總工時：{project_end:.1f} 小時")
        print(f"關鍵路徑：{' → '.join(critical_path)}")

        if args.export_gantt:
            save_gantt_chart(cpm_result, durations_hours, args.export_gantt)
            print(f"已匯出甘特圖至 {args.export_gantt}")

        if args.monte_carlo > 0:
            base = duration_field.replace("Te_", "")
            o_field = f"O_{base}"
            m_field = f"M_{base}"
            p_field = f"P_{base}"
            if (
                o_field in merged.columns
                and m_field in merged.columns
                and p_field in merged.columns
            ):
                o_dur = extractDurationFromWbs(merged, o_field)
                m_dur = extractDurationFromWbs(merged, m_field)
                p_dur = extractDurationFromWbs(merged, p_field)
                mc_result = monteCarloSchedule(
                    merged_graph,
                    o_dur,
                    m_dur,
                    p_dur,
                    args.monte_carlo,
                    args.mc_confidence,
                )
                conf_pct = int(args.mc_confidence * 100)
                sample_arr = np.array(mc_result["samples"])
                prob = float(
                    np.mean(sample_arr <= mc_result["confidence_value"]) * 100
                )
                print("蒙地卡羅模擬結果：")
                print(
                    f"平均工期 {mc_result['average']:.1f}h，"
                    f"標準差 {mc_result['std']:.1f}h"
                )
                print(
                    f"最短 {mc_result['min']:.1f}h，"
                    f"最長 {mc_result['max']:.1f}h"
                )
                print(
                    f"{conf_pct}% 信心水準下工期 {mc_result['confidence_value']:.1f}h"
                )
                print(
                    f"完工時間在 {mc_result['confidence_value']:.1f}h 以內的"
                    f"機率約 {prob:.1f}%"
                )
            else:
                print("缺少 O/M/P 欄位，無法執行蒙地卡羅模擬")


if __name__ == "__main__":
    main()
