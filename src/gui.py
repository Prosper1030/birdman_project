# -*- coding: utf-8 -*-
"""簡易 GUI 介面"""

import tkinter as tk
from tkinter import filedialog, messagebox
from .dsm_processor import readDsm, buildGraph, computeLayersAndScc
from .wbs_processor import readWbs, mergeByScc, validateIds


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

            # 依照圖計算層次與強連通分量
            layers, scc_map = computeLayersAndScc(graph)

            wbs = readWbs(self.wbsPath.get())
            validateIds(wbs, dsm)

            # 新增 Layer 與 SCC_ID 欄位並依層次排序
            wbs["Layer"] = wbs["Task ID"].map(layers).fillna(-1).astype(int)
            wbs["SCC_ID"] = wbs["Task ID"].map(scc_map).fillna(-1).astype(int)
            sorted_wbs = wbs.sort_values(by=["Layer", "Task ID"]).reset_index(drop=True)

            sorted_wbs.to_csv("sorted_wbs.csv", index=False, encoding="utf-8-sig")

            merged = mergeByScc(sorted_wbs)
            merged.to_csv("merged_wbs.csv", index=False, encoding="utf-8-sig")

            messagebox.showinfo('完成', '輸出檔已生成')
        except Exception as e:
            messagebox.showerror('錯誤', str(e))


def main():
    root = tk.Tk()
    app = BirdmanApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
