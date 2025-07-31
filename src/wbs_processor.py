
import pandas as pd


def readWbs(path: str) -> pd.DataFrame:
    """讀取 WBS CSV 並回傳資料框"""
    return pd.read_csv(path, encoding="utf-8-sig")
