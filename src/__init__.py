"""Birdman 專案核心套件。"""

from __future__ import annotations

from typing import Any


def readResources(*args: Any, **kwargs: Any) -> dict[str, int]:
    """延後載入資源處理器，避免套件初始化時就依賴 pandas。"""
    from .resource_processor import readResources as _readResources

    return _readResources(*args, **kwargs)


__all__ = ["readResources"]
