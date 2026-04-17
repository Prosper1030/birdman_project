"""主 GUI 輸入與匯入服務。"""

from __future__ import annotations

from dataclasses import dataclass, field
import os

import pandas as pd

from ...dsm_processor import readDsm
from ...wbs_processor import readWbs
from .helpers import addNoColumn


@dataclass(slots=True)
class FolderImportBundle:
    """資料夾匯入結果。"""

    wbsPath: str
    dsmPath: str
    wbs: pd.DataFrame
    wbsDisplay: pd.DataFrame
    dsm: pd.DataFrame
    resourcePath: str = ""
    resources: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)


class FolderImportSelectionError(ValueError):
    """資料夾內檔案數量不符合匯入要求。"""


def loadDsmPreview(path: str) -> pd.DataFrame:
    """載入 DSM 預覽資料。"""
    return readDsm(path)


def loadWbsPreview(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """載入 WBS 原始資料與預覽資料。"""
    wbs = readWbs(path)
    return wbs, addNoColumn(wbs)


def loadResourcesPreview(path: str) -> pd.DataFrame:
    """載入 Resources 預覽資料。"""
    return pd.read_csv(path, encoding="utf-8-sig")


def loadOptionalDsmForEditor(dsmPath: str) -> pd.DataFrame | None:
    """若提供 DSM 路徑則載入，否則回傳 ``None``。"""
    if not dsmPath:
        return None
    return readDsm(dsmPath)


def _findMatchingFiles(folder: str, keyword: str) -> list[str]:
    """依關鍵字篩選資料夾內檔名。"""
    files = os.listdir(folder)
    return [name for name in files if keyword in name.lower()]


def loadFolderImportBundle(folder: str) -> FolderImportBundle:
    """從資料夾載入 WBS、DSM 與可選的 Resources。"""
    wbsFiles = _findMatchingFiles(folder, "wbs")
    dsmFiles = _findMatchingFiles(folder, "dsm")
    resourceFiles = _findMatchingFiles(folder, "resource")

    if len(wbsFiles) != 1 or len(dsmFiles) != 1:
        raise FolderImportSelectionError(
            "請選擇一個剛好包含一份 WBS 和一份 DSM 檔案的資料夾。"
        )

    wbsPath = os.path.join(folder, wbsFiles[0])
    dsmPath = os.path.join(folder, dsmFiles[0])
    wbs, wbsDisplay = loadWbsPreview(wbsPath)
    dsm = loadDsmPreview(dsmPath)

    bundle = FolderImportBundle(
        wbsPath=wbsPath,
        dsmPath=dsmPath,
        wbs=wbs,
        wbsDisplay=wbsDisplay,
        dsm=dsm,
    )

    if len(resourceFiles) > 1:
        bundle.warnings.append("資料夾中最多只能有一份 Resources 檔案，將忽略多餘檔案。")
        return bundle

    if len(resourceFiles) == 1:
        resourcePath = os.path.join(folder, resourceFiles[0])
        try:
            bundle.resources = loadResourcesPreview(resourcePath)
            bundle.resourcePath = resourcePath
        except (OSError, pd.errors.ParserError, ValueError):
            bundle.warnings.append("Resources 檔案格式不正確，將忽略。")

    return bundle
