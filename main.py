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
    processDsm,
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
from src.resource_processor import readResources
from src.racp_solver import solve_racp_basic
from src import visualizer
from matplotlib.figure import Figure
import matplotlib


def set_chinese_font():
    """設定 Matplotlib 支援中文的字型"""
    try:
        font_path = None
        common_paths = [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/System/Library/Fonts/STHeitiLight.ttc',  # macOS
            'C:/Windows/Fonts/msyh.ttc'  # Windows
        ]
        for p in common_paths:
            if Path(p).exists():
                font_path = p
                break

        if font_path:
            font_name = matplotlib.font_manager.FontProperties(
                fname=font_path).get_name()
            matplotlib.rc('font', family=font_name)
            # 解決負號顯示問題
            matplotlib.rcParams['axes.unicode_minus'] = False
        else:
            # 如果找不到特定字型，可以設定一個備用列表
            matplotlib.rcParams['font.sans-serif'] = [
                'Noto Sans CJK JP',
                'Microsoft JhengHei',
                'Heiti TC',
                'sans-serif'
            ]
            matplotlib.rcParams['axes.unicode_minus'] = False
    except Exception as e:
        print(f"字型設定時發生錯誤: {e}")


def saveFigure(fig: Figure, path: str) -> None:
    """以副檔名決定輸出格式"""
    ext = Path(path).suffix.lower()
    fmt = 'png' if ext != '.svg' else 'svg'
    if fmt == 'svg' and not path.lower().endswith('.svg'):
        path += '.svg'
    elif fmt == 'png' and not path.lower().endswith('.png'):
        path += '.png'
    fig.savefig(path, format=fmt, bbox_inches='tight', dpi=300)


def saveGanttChart(cpmDf, durations: dict[str, float], path: str) -> None:
    """根據 CPM 結果輸出甘特圖"""
    set_chinese_font()
    fig = Figure(figsize=(10, max(4, len(cpmDf) * 0.6)))
    ax = fig.add_subplot(111)
    fig.subplots_adjust(top=0.9, bottom=0.15, left=0.2, right=0.95)
    tasks = cpmDf.index.tolist()
    startTimes = cpmDf['ES'].tolist()
    taskDurations = [durations.get(t, 0) for t in tasks]
    yPos = range(len(tasks))
    colors = ['red' if cpmDf.at[t, 'Critical'] else 'skyblue' for t in tasks]
    ax.barh(
        yPos,
        taskDurations,
        left=startTimes,
        color=colors,
        alpha=0.8,
        height=0.6,
        edgecolor='black',
        linewidth=1,
        zorder=2,
    )
    ax.set_yticks(list(yPos))
    ax.set_yticklabels(tasks, fontsize=10, fontweight='bold')
    ax.grid(True, axis='x', linestyle='--', color='gray', alpha=0.3, zorder=1)
    ax.set_axisbelow(True)
    ax.set_xlabel('時間 (小時)', fontsize=11, fontweight='bold')
    ax.set_title('專案甘特圖 (紅色為關鍵路徑)', fontsize=14, pad=20)
    for i, (duration, start) in enumerate(zip(taskDurations, startTimes)):
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
    saveFigure(fig, path)


def saveRcpspGanttChart(
        scheduleDf, durationField, path: str, total_duration: float):
    """根據 RCPSP 結果輸出甘特圖"""
    set_chinese_font()
    df = scheduleDf.sort_values(by="Start").reset_index(drop=True)
    fig = Figure(figsize=(10, max(4, len(df) * 0.6)))
    ax = fig.add_subplot(111)
    fig.subplots_adjust(top=0.9, bottom=0.15, left=0.2, right=0.95)
    tasks = df['Task ID'].tolist()
    startTimes = df['Start'].tolist()
    taskDurations = df[durationField].tolist()
    yPos = range(len(tasks))
    ax.barh(
        yPos,
        taskDurations,
        left=startTimes,
        color='dodgerblue',
        alpha=0.8,
        height=0.6,
        edgecolor='black',
        linewidth=1,
        zorder=2,
    )
    ax.set_yticks(list(yPos))
    ax.set_yticklabels(tasks, fontsize=10, fontweight='bold')
    ax.grid(True, axis='x', linestyle='--', color='gray', alpha=0.3, zorder=1)
    ax.set_axisbelow(True)
    ax.set_xlabel('時間 (小時)', fontsize=11, fontweight='bold')
    title = f'專案甘特圖 (RCPSP 排程 - 總工時: {total_duration:.1f} 小時)'
    ax.set_title(title, fontsize=14, pad=20)
    for i, (duration, start) in enumerate(zip(taskDurations, startTimes)):
        if duration > 0:
            ax.text(
                start + duration + 0.1,
                i,
                f'{duration:.1f}h',
                va='center',
                fontsize=9,
                alpha=0.7,
            )
    ax.invert_yaxis()
    saveFigure(fig, path)


def parse_arguments():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(description="DSM 排序與專案管理工具")
    parser.add_argument("--dsm", required=True, help="DSM 檔案路徑")
    parser.add_argument("--wbs", required=True, help="WBS 檔案路徑")
    parser.add_argument("--config", default="config.json", help="設定檔路徑")
    parser.add_argument("--cpm", action="store_true", help="執行 CPM 分析")
    parser.add_argument(
        "--export-graph", metavar="PATH", help="匯出依賴關係圖 (SVG/PNG)")
    parser.add_argument(
        "--export-gantt", metavar="PATH", help="匯出 CPM 甘特圖 (SVG/PNG)")
    parser.add_argument(
        "--export-rcpsp-gantt", metavar="PATH", help="匯出 RCPSP 甘特圖 (SVG/PNG)")
    parser.add_argument(
        "--duration-field", dest="durationField", metavar="FIELD",
        help="指定工期欄位")
    parser.add_argument(
        "--resources", metavar="PATH", help="Resources 檔案路徑")
    parser.add_argument(
        "--resource-field", dest="resourceField", default="ResourceDemand",
        help="WBS 中資源欄位名稱 (預設 ResourceDemand)")
    parser.add_argument(
        "--demand-field", dest="demandField", default="ResourceDemand",
        help="WBS 中資源需求欄位名稱 (預設 ResourceDemand)")
    parser.add_argument(
        "--monte-carlo", metavar="N", type=int, default=0,
        help="執行蒙地卡羅模擬次數")
    parser.add_argument(
        "--mc-confidence", dest="mcConfidence", metavar="P",
        type=float, default=0.9, help="蒙地卡羅信心水準")
    parser.add_argument(
        "--rcpsp-opt", action="store_true", help="執行 RCPSP 資源優化排程")
    parser.add_argument(
        "--racp-opt", metavar="DEADLINE", type=int,
        help="執行 RACP 反推最小人力配置")
    return parser.parse_args()


def load_data(args):
    """載入所有輸入資料"""
    dsm = readDsm(args.dsm)
    wbs = readWbs(args.wbs)
    validateIds(wbs, dsm)
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return dsm, wbs, config


def process_project_data(dsm, wbs, config):
    """執行核心的資料處理與分析"""
    G = buildGraph(dsm)
    layers, scc_id = computeLayersAndScc(G)

    wbs["Layer"] = wbs["Task ID"].map(layers).fillna(-1).astype(int)
    wbs["SCC_ID"] = wbs["Task ID"].map(scc_id).fillna(-1).astype(int)
    wbs_sorted = wbs.sort_values(
        by=["Layer", "Task ID"]).reset_index(drop=True)

    sorted_dsm = reorderDsm(dsm, wbs_sorted["Task ID"].tolist())

    kParams = config.get('merge_k_params', {})
    merged = mergeByScc(wbs_sorted, kParams)

    task_mapping = buildTaskMapping(wbs_sorted, merged)
    merged_dsm_raw = buildMergedDsm(G, task_mapping)
    _, _, merged_graph = processDsm(merged_dsm_raw, merged)

    return G, wbs_sorted, sorted_dsm, merged, merged_graph


def generate_outputs(
        args, config, G, wbs_sorted, sorted_dsm, merged, merged_graph):
    """產生所有輸出檔案與圖表"""
    # 輸出基本分析檔案
    for path, df in [
            ("sorted_wbs.csv", wbs_sorted),
            ("sorted_dsm.csv", sorted_dsm),
            ("merged_wbs.csv", merged)]:
        df.to_csv(Path(path), index=False, encoding="utf-8-sig")
        print(f"已輸出 {Path(path).name}")

    # 執行 RCPSP
    if args.rcpsp_opt:
        if not args.resources:
            raise ValueError("使用 RCPSP 排程時必須提供 --resources 檔案")
        if args.resourceField not in merged.columns:
            raise ValueError(f'WBS 缺少資源欄位 {args.resourceField}')
        if args.demandField not in merged.columns:
            raise ValueError(f'WBS 缺少需求欄位 {args.demandField}')
        print("開始執行 RCPSP 排程...")
        cmp_params = config.get("cmp_params", {})
        durationField = args.durationField or cmp_params.get(
            "default_duration_field", "Te_newbie")
        resourceCap = readResources(args.resources, merged, durationField)
        schedule = solveRcpsp(
            merged_graph,
            merged,
            durationField=durationField,
            resourceField=args.resourceField,
            demandField=args.demandField,
            resourceCap=resourceCap,
        )
        merged["Start"] = merged["Task ID"].map(schedule).fillna(0)
        merged["Finish"] = merged["Start"] + merged[durationField].fillna(0)
        out_rcpsp = Path("rcpsp_schedule.csv")
        merged[["Task ID", "Start", "Finish"]].to_csv(
            out_rcpsp, index=False, encoding="utf-8-sig")
        total_duration = schedule["ProjectEnd"]
        print(f"最短完工時間：{total_duration:.1f} 小時")
        if args.export_rcpsp_gantt:
            saveRcpspGanttChart(
                merged, durationField, args.export_rcpsp_gantt, total_duration)
            print(f"已匯出 RCPSP 甘特圖至 {args.export_rcpsp_gantt}")

    if args.racp_opt is not None:
        if args.demandField not in merged.columns:
            raise ValueError(f'WBS 缺少需求欄位 {args.demandField}')
        if "Eligible_Groups" not in merged.columns:
            raise ValueError("WBS 缺少 Eligible_Groups 欄位")
        print("開始執行 RACP 分析...")
        cmp_params = config.get("cmp_params", {})
        durationField = args.durationField or cmp_params.get(
            "default_duration_field", "Te_newbie")
        cap = solve_racp_basic(
            merged_graph,
            merged,
            args.racp_opt,
            durationField=durationField,
            demandField=args.demandField,
        )
        print(f"最小人力配置：{cap}")

    # 匯出依賴圖
    if args.export_graph:
        viz_params = config.get('visualization_params', {})
        scc_map = dict(zip(wbs_sorted['Task ID'], wbs_sorted['SCC_ID']))
        layer_map = dict(zip(wbs_sorted['Task ID'], wbs_sorted['Layer']))
        fig = visualizer.create_dependency_graph_figure(
            G, scc_map, layer_map, viz_params)
        saveFigure(fig, args.export_graph)
        print(f"已匯出依賴關係圖至 {args.export_graph}")

    # 執行 CPM
    if args.cpm:
        run_cpm_analysis(args, config, merged, merged_graph)


def run_cpm_analysis(args, config, merged, merged_graph):
    """執行 CPM 分析與相關輸出"""
    print("開始執行 CPM 分析...")
    cmp_params = config.get('cmp_params', {})
    durationField = args.durationField or cmp_params.get(
        'default_duration_field', 'Te_newbie')

    durations_hours = extractDurationFromWbs(merged, durationField)

    if cycles := list(nx.simple_cycles(merged_graph)):
        cycle_str = ' -> '.join(cycles[0] + [cycles[0][0]])
        raise ValueError(f"發現循環依賴：{cycle_str}")

    forward_data = cpmForwardPass(merged_graph, durations_hours)
    project_end = max(ef for _, ef in forward_data.values())
    backward_data = cpmBackwardPass(
        merged_graph, durations_hours, project_end)
    cpm_result = calculateSlack(forward_data, backward_data, merged_graph)
    critical_path = findCriticalPath(cpm_result)

    wbs_with_cpm = merged.copy()
    for col in ['ES', 'EF', 'LS', 'LF', 'TF', 'FF', 'Critical']:
        wbs_with_cpm[col] = wbs_with_cpm['Task ID'].map(
            cpm_result[col].to_dict()).fillna(0)

    out_cpm = Path("cmp_analysis.csv")
    wbs_with_cpm.to_csv(out_cpm, index=False, encoding="utf-8-sig")
    print(f"已輸出 CPM 分析結果：{out_cpm.name}")
    print(f"專案總工時：{project_end:.1f} 小時")
    print(f"關鍵路徑：{' → '.join(critical_path)}")

    if args.export_gantt:
        saveGanttChart(cpm_result, durations_hours, args.export_gantt)
        print(f"已匯出甘特圖至 {args.export_gantt}")

    if args.monte_carlo > 0:
        run_monte_carlo_simulation(
            args, merged, merged_graph, durationField)


def run_monte_carlo_simulation(args, merged, merged_graph, durationField):
    """執行蒙地卡羅模擬"""
    base = durationField.replace("Te_", "")
    o_field, m_field, p_field = f"O_{base}", f"M_{base}", f"P_{base}"

    if not all(f in merged.columns for f in [o_field, m_field, p_field]):
        print("缺少 O/M/P 欄位，無法執行蒙地卡羅模擬")
        return

    o_dur = extractDurationFromWbs(merged, o_field)
    m_dur = extractDurationFromWbs(merged, m_field)
    p_dur = extractDurationFromWbs(merged, p_field)
    mc_result = monteCarloSchedule(
        merged_graph, o_dur, m_dur, p_dur,
        args.monte_carlo, args.mcConfidence)

    conf_pct = int(args.mcConfidence * 100)
    sample_arr = np.array(mc_result["samples"])
    prob = float(np.mean(sample_arr <= mc_result["confidence_value"]) * 100)

    print("蒙地卡羅模擬結果：")
    print(
        f"平均工期 {mc_result['average']:.1f}h，"
        f"標準差 {mc_result['std']:.1f}h")
    print(
        f"最短 {mc_result['min']:.1f}h，"
        f"最長 {mc_result['max']:.1f}h")
    print(f"{conf_pct}% 信心水準下工期 {mc_result['confidence_value']:.1f}h")
    print(
        f"完工時間在 {mc_result['confidence_value']:.1f}h 以內的"
        f"機率約 {prob:.1f}%")


def main():
    """主執行流程"""
    args = parse_arguments()
    dsm, wbs, config = load_data(args)
    G, wbs_sorted, sorted_dsm, merged, merged_graph = process_project_data(
        dsm, wbs, config)
    generate_outputs(
        args, config, G, wbs_sorted, sorted_dsm, merged, merged_graph)


if __name__ == "__main__":
    main()
