# -*- coding: utf-8 -*-
"""簡易 GUI 介面"""

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from tkinter import ttk
from .dsm_processor import (
    readDsm,
    buildGraph,
    computeLayersAndScc,
    reorderDsm,
)

from .wbs_processor import readWbs, mergeByScc, validateIds


class BirdmanApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title('Birdman Project 工具')

        self.font_size = 10
        self.font = tkfont.Font(family='TkFixedFont', size=self.font_size)

        self.sorted_wbs = None
        self.merged_wbs = None
        self.sorted_dsm = None

        self.dsmPath = tk.StringVar()
        self.wbsPath = tk.StringVar()

        tk.Label(master, text='DSM 檔案').grid(row=0, column=0)
        tk.Entry(master, textvariable=self.dsmPath, width=50).grid(row=0, column=1)
        tk.Button(master, text='選擇', command=self.chooseDsm).grid(row=0, column=2)

        tk.Label(master, text='WBS 檔案').grid(row=1, column=0)
        tk.Entry(master, textvariable=self.wbsPath, width=50).grid(row=1, column=1)
        tk.Button(master, text='選擇', command=self.chooseWbs).grid(row=1, column=2)

        tk.Button(master, text='執行', command=self.run).grid(row=2, column=1)


        # Treeview for DataFrame preview (Excel-like)
        self.tree = ttk.Treeview(master, show='headings')
        self.tree.grid(row=3, column=0, columnspan=3, sticky='nsew')
        # Add scrollbars
        self.vsb = ttk.Scrollbar(master, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(master, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        self.vsb.grid(row=3, column=3, sticky='ns')
        self.hsb.grid(row=4, column=0, columnspan=3, sticky='ew')

        # 讓 grid 可自動調整大小
        master.grid_rowconfigure(3, weight=1)
        master.grid_columnconfigure(1, weight=1)

        zoom_frame = tk.Frame(master)
        zoom_frame.grid(row=5, column=0, columnspan=3)
        tk.Button(zoom_frame, text='放大', command=self.zoomIn).pack(side=tk.LEFT)
        tk.Button(zoom_frame, text='縮小', command=self.zoomOut).pack(side=tk.LEFT)

        export_frame = tk.Frame(master)
        export_frame.grid(row=6, column=0, columnspan=3)
        tk.Button(export_frame, text='匯出排序 WBS', command=self.exportSortedWbs).pack(side=tk.LEFT)
        tk.Button(export_frame, text='匯出合併 WBS', command=self.exportMergedWbs).pack(side=tk.LEFT)
        tk.Button(export_frame, text='匯出排序 DSM', command=self.exportSortedDsm).pack(side=tk.LEFT)

    def chooseDsm(self):
        path = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if path:
            self.dsmPath.set(path)
            try:
                df = readDsm(path)
                self.preview(df)
            except Exception as e:
                messagebox.showerror('錯誤', str(e))

    def chooseWbs(self):
        path = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if path:
            self.wbsPath.set(path)
            try:
                df = readWbs(path)
                self.preview(df)
            except Exception as e:
                messagebox.showerror('錯誤', str(e))

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

            self.sorted_wbs = sorted_wbs
            self.sorted_dsm = reorderDsm(dsm, sorted_wbs["Task ID"].tolist())
            self.merged_wbs = mergeByScc(sorted_wbs)
            self.preview(self.sorted_wbs)
            self.merged_wbs.to_csv("merged_wbs.csv", index=False, encoding="utf-8-sig")


            messagebox.showinfo('完成', '分析完成，可點選下方按鈕匯出')
        except Exception as e:
            messagebox.showerror('錯誤', str(e))

    def preview(self, df):
        """在 Treeview 預覽 DataFrame 前幾列（像 Excel）"""
        # 清空欄位與內容
        self.tree.delete(*self.tree.get_children())
        self.tree['columns'] = list(df.columns)
        for col in df.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor='center')
        # 只顯示前 30 列，避免太多
        for _, row in df.head(30).iterrows():
            self.tree.insert('', 'end', values=list(row))

    def zoomIn(self):
        # ttk.Treeview 不支援直接改字體，需額外設計
        # 這裡可略過或用 style 設定
        pass

    def zoomOut(self):
        pass

    def exportSortedWbs(self):
        if self.sorted_wbs is None:
            messagebox.showwarning('警告', '請先執行分析')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv')
        if path:
            self.sorted_wbs.to_csv(path, index=False, encoding='utf-8-sig')
            messagebox.showinfo('完成', f'已匯出 {path}')

    def exportMergedWbs(self):
        if self.merged_wbs is None:
            messagebox.showwarning('警告', '請先執行分析')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv')
        if path:
            self.merged_wbs.to_csv(path, index=False, encoding='utf-8-sig')
            messagebox.showinfo('完成', f'已匯出 {path}')

    def exportSortedDsm(self):
        if self.sorted_dsm is None:
            messagebox.showwarning('警告', '請先執行分析')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv')
        if path:
            self.sorted_dsm.to_csv(path, encoding='utf-8-sig')
            messagebox.showinfo('完成', f'已匯出 {path}')


def main():
    root = tk.Tk()
    app = BirdmanApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
