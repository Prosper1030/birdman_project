"""Matplotlib 執行環境相容性設定。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _ensureWritableCacheDirs() -> None:
    """確保 Matplotlib 與 Fontconfig 有可寫入的快取目錄。"""
    cacheRoot = Path(tempfile.gettempdir()) / "birdman_project_cache"
    mplConfigDir = cacheRoot / "matplotlib"
    xdgCacheHome = cacheRoot / "xdg"
    fontconfigDir = xdgCacheHome / "fontconfig"

    for targetDir in (mplConfigDir, xdgCacheHome, fontconfigDir):
        targetDir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MPLCONFIGDIR", str(mplConfigDir))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdgCacheHome))


def prepareMatplotlibForQt() -> str:
    """在匯入 pyplot 前強制使用 Qt backend。"""
    _ensureWritableCacheDirs()

    import matplotlib

    backendName = os.environ.get("MPLBACKEND", "Qt5Agg")
    matplotlib.use(backendName, force=True)
    return str(matplotlib.get_backend())


__all__ = ["prepareMatplotlibForQt"]
