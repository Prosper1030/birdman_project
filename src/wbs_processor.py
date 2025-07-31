
import pandas as pd
import re


def validateTrf(wbs: pd.DataFrame) -> None:
    """檢查 TRF 欄位不可為負數"""
    if "TRF" not in wbs.columns:
        raise ValueError("WBS 缺少 TRF 欄位")
    if (wbs["TRF"].astype(float) < 0).any():
        raise ValueError("TRF 不能為負數")


def readWbs(path: str) -> pd.DataFrame:
    """讀取 WBS CSV 並回傳資料框"""
    return pd.read_csv(path, encoding="utf-8-sig")


def validateIds(wbs: pd.DataFrame, dsm: pd.DataFrame) -> None:
    """確認 WBS 的 Task ID 存在於 DSM，並檢查 TRF"""
    validateTrf(wbs)
    if "Task ID" not in wbs.columns:
        raise ValueError("WBS 缺少 Task ID 欄位")
    dsm_ids = set(dsm.index.tolist()) | set(dsm.columns.tolist())
    missing = [tid for tid in wbs["Task ID"] if tid not in dsm_ids]
    if missing:
        raise ValueError(f"下列 Task ID 未在 DSM 中找到：{', '.join(missing)}")



def _extract_year(task_id: str) -> str:
    """從 Task ID 解析年份兩碼"""
    m = re.search(r"\D(\d{2})-\d+$", task_id)
    if not m:
        raise ValueError(f"無法從 {task_id} 解析年份")
    return m.group(1)


def mergeByScc(wbs: pd.DataFrame) -> pd.DataFrame:
    """依據 SCC_ID 合併任務並計算新工時

    若同一 SCC 中的任務年份不一致則報錯。
    """
    time_cols = [
        "M",
        "O_expert",
        "P_expert",
        "Te_expert",
        "O_newbie",
        "M_newbie",
        "P_newbie",
        "Te_newbie",
    ]

    merged_rows = []
    serial = 1
    for scc_id, grp in wbs.groupby("SCC_ID", sort=False):
        if len(grp) == 1:
            merged_rows.append(grp.iloc[0])
            continue

        years = grp["Task ID"].apply(_extract_year).unique()
        if len(years) == 1:
            year = years[0]
        else:
            raise ValueError(f"SCC {scc_id} 包含不同年份的 Task ID: {years}")

        new_id = f"M{year}-{serial:03d}[{','.join(grp['Task ID'])}]"
        serial += 1

        new_row = grp.iloc[0].copy()
        new_row["Task ID"] = new_id
        if "Name" in new_row.index:
            new_row["Name"] = ""

        trf_sum = grp["TRF"].astype(float).sum()
        n = len(grp)
        k = 1 + ((trf_sum / n) * 10) ** 0.5 / 10 + 0.05 * (n - 1)

        for col in time_cols:
            if col in grp.columns:
                new_row[col] = grp[col].astype(float).sum() * k

        new_row["TRF"] = trf_sum
        merged_rows.append(new_row)

    return pd.DataFrame(merged_rows)

