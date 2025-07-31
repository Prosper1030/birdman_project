# -*- coding: utf-8 -*-
"""簡易 GUI 介面"""

import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd

from .dsm_processor import readDsm, buildGraph, topologicalSort, tarjanScc, computeLayers
from .wbs_processor import readWbs, validateIds, reorderWbs, mergeByScc


class BirdmanApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title('Birdman Project 工具')

        self.dsmPath = tk.StringVar()
        self.wbsPath = tk.StringVar()

        tk.Label(master, text='DSM 檔案').grid(row=0, column=0)
        tk.Entry(master, textvariable=self.dsmPath, width=50).grid(row=0, column=1)
        tk.Button(master, text='選擇', command=self.chooseDsm).grid(row=0, column=2)

        tk.Label(master, text='WBS 檔案').grid(row=1, column=0)
        tk.Entry(master, textvariable=self.wbsPath, width=50).grid(row=1, column=1)
        tk.Button(master, text='選擇', command=self.chooseWbs).grid(row=1, column=2)

        tk.Button(master, text='執行', command=self.run).grid(row=2, column=1)

    def chooseDsm(self):
        path = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if path:
            self.dsmPath.set(path)

    def chooseWbs(self):
        path = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if path:
            self.wbsPath.set(path)

    def run(self):
        try:
            dsm = readDsm(self.dsmPath.get())
            graph = buildGraph(dsm)
            order, hasCycle = topologicalSort(graph)
            if hasCycle:
                sccs, sccMap = tarjanScc(graph)
                msg = '\n'.join([f'SCC {i+1}: {s}' for i, s in enumerate(sccs)])
                messagebox.showinfo('存在循環依賴', msg)
            else:
                sccMap = {t: 0 for t in order}
            layers = computeLayers(order, graph)
            wbs = readWbs(self.wbsPath.get())
            validateIds(wbs, dsm)
            sortedWbs = reorderWbs(wbs, order, sccMap)
            sortedWbs['Layer'] = [layers[t] for t in order]
            sortedWbs.to_csv('sorted_wbs.csv', index=False)
            merged = mergeByScc(sortedWbs, sccMap)
            merged.to_csv('merged_wbs.csv', index=False)
            messagebox.showinfo('完成', '輸出檔已生成')
        except Exception as e:
            messagebox.showerror('錯誤', str(e))


def main():
    root = tk.Tk()
    app = BirdmanApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
