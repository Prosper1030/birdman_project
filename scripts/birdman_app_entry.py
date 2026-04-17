#!/usr/bin/env python3
"""Birdman macOS app 的開發模式入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def prepareAppRuntime(projectRoot: Path) -> None:
    """套用 GUI 啟動所需的環境設定。"""
    cacheRoot = Path(os.environ.get("TMPDIR", "/tmp")) / "birdman_project_cache"
    matplotlibCache = cacheRoot / "matplotlib"
    xdgCache = cacheRoot / "xdg"

    matplotlibCache.mkdir(parents=True, exist_ok=True)
    (xdgCache / "fontconfig").mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MPLBACKEND", "Qt5Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlibCache))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdgCache))

    if str(projectRoot) not in sys.path:
        sys.path.insert(0, str(projectRoot))

    os.chdir(projectRoot)


def main() -> None:
    """啟動 Birdman 主 GUI。"""
    projectRoot = Path(__file__).resolve().parents[1]
    prepareAppRuntime(projectRoot)

    from src.gui_qt import main as launchGui

    launchGui()


if __name__ == "__main__":
    main()
