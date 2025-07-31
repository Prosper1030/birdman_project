
import pandas as pd


def readWbs(path: str) -> pd.DataFrame:
    """讀取 WBS CSV 並回傳資料框"""
    return pd.read_csv(path, encoding="utf-8-sig")



def mergeByScc(wbs: pd.DataFrame, year: str) -> pd.DataFrame:
    """依據 SCC_ID 合併任務並計算新工時"""
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

        new_id = f"M{year}-{serial:03d}[{','.join(grp['Task ID'])}]"
        serial += 1

        new_row = grp.iloc[0].copy()
        new_row["Task ID"] = new_id

        trf_sum = grp["TRF"].astype(float).sum()
        n = len(grp)
        k = 1 + ((trf_sum / n) * 10) ** 0.5 / 10 + 0.05 * (n - 1)

        for col in time_cols:
            if col in grp.columns:
                new_row[col] = grp[col].astype(float).sum() * k

        new_row["TRF"] = trf_sum
        merged_rows.append(new_row)

    return pd.DataFrame(merged_rows)

