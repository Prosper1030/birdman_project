# -*- coding: utf-8 -*-
"""簡易 GUI 介面"""

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
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

        self.text = tk.Text(master, width=80, height=20, font=self.font)
        self.text.grid(row=3, column=0, columnspan=3)

        zoom_frame = tk.Frame(master)
        zoom_frame.grid(row=4, column=0, columnspan=3)
        tk.Button(zoom_frame, text='放大', command=self.zoomIn).pack(side=tk.LEFT)
        tk.Button(zoom_frame, text='縮小', command=self.zoomOut).pack(side=tk.LEFT)

        export_frame = tk.Frame(master)
        export_frame.grid(row=5, column=0, columnspan=3)
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

            messagebox.showinfo('完成', '分析完成，可點選下方按鈕匯出')
        except Exception as e:
            messagebox.showerror('錯誤', str(e))

    def preview(self, df):
        """在文字區塊顯示資料前幾列"""
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, df.head().to_string())

    def zoomIn(self):
        self.font_size += 1
        self.font.configure(size=self.font_size)

    def zoomOut(self):
        if self.font_size > 4:
            self.font_size -= 1
            self.font.configure(size=self.font_size)

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
