"""專案路徑與執行環境輔助工具。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


projectRoot = Path(__file__).resolve().parents[1]
defaultConfigPath = projectRoot / "config.json"
sampleDataDir = projectRoot / "sample_data"


def loadProjectConfig(configPath: str | Path | None = None) -> dict[str, Any]:
    """讀取專案設定檔。"""
    targetPath = defaultConfigPath if configPath is None else Path(configPath).expanduser()
    with targetPath.open("r", encoding="utf-8") as configFile:
        return json.load(configFile)


def saveProjectConfig(
    config: dict[str, Any],
    configPath: str | Path | None = None,
) -> Path:
    """寫回專案設定檔。"""
    targetPath = defaultConfigPath if configPath is None else Path(configPath).expanduser()
    targetPath.parent.mkdir(parents=True, exist_ok=True)
    with targetPath.open("w", encoding="utf-8") as configFile:
        json.dump(config, configFile, indent=2, ensure_ascii=False)
        configFile.write("\n")
    return targetPath


def prepareQtApplication() -> None:
    """在建立 QApplication 前先套用跨平台與 macOS 友善設定。"""
    if sys.platform == "darwin":
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")

    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        return

    for attrName in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        attrValue = getattr(Qt, attrName, None)
        if attrValue is not None:
            QApplication.setAttribute(attrValue, True)
