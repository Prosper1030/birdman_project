# -*- coding: utf-8 -*-
"""Birdman Project 主程式"""

from __future__ import annotations

import argparse

from src.dsm_processor import readDsm, buildGraph, topologicalSort, tarjanScc, computeLayers
from src.wbs_processor import readWbs, validateIds, reorderWbs, mergeByScc


def process(dsmPath: str, wbsPath: str):
    dsm = readDsm(dsmPath)
    graph = buildGraph(dsm)
    order, hasCycle = topologicalSort(graph)
    if hasCycle:
        sccs, sccMap = tarjanScc(graph)
    else:
        sccMap = {t: 0 for t in order}
    layers = computeLayers(order, graph)
    wbs = readWbs(wbsPath)
    validateIds(wbs, dsm)
    sortedWbs = reorderWbs(wbs, order, sccMap)
    sortedWbs['Layer'] = [layers[t] for t in order]
    sortedWbs.to_csv('sorted_wbs.csv', index=False)
    merged = mergeByScc(sortedWbs, sccMap)
    merged.to_csv('merged_wbs.csv', index=False)
    print('排序與合併完成')


def main():
    parser = argparse.ArgumentParser(description='Birdman Project 工具')
    parser.add_argument('--dsm', required=True, help='DSM CSV 檔案路徑')
    parser.add_argument('--wbs', required=True, help='WBS CSV 檔案路徑')
    args = parser.parse_args()
    process(args.dsm, args.wbs)


if __name__ == '__main__':
    main()
