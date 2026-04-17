#!/usr/bin/env python3
"""Birdman macOS app 的 py2app 設定。"""

from __future__ import annotations

from pathlib import Path

from setuptools import setup


projectRoot = Path(__file__).resolve().parents[1]

app = [str(projectRoot / "scripts" / "birdman_app_entry.py")]
resources = [
    str(projectRoot / "config.json"),
    str(projectRoot / "sample_data"),
]

py2appOptions = {
    "argv_emulation": False,
    "alias": True,
    "site_packages": True,
    "packages": [
        "src",
        "PyQt5",
        "pandas",
        "networkx",
        "numpy",
        "scipy",
        "matplotlib",
        "qdarkstyle",
        "ortools",
    ],
    "includes": [
        "sip",
        "PyQt5.sip",
        "matplotlib.backends.backend_qt5agg",
        "matplotlib.backends.backend_agg",
        "qdarkstyle",
    ],
    "plist": {
        "CFBundleDisplayName": "Birdman Project",
        "CFBundleExecutable": "Birdman Project",
        "CFBundleIdentifier": "com.linyuan.birdman-project",
        "CFBundleName": "Birdman Project",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
    },
}


setup(
    app=app,
    data_files=resources,
    options={"py2app": py2appOptions},
)
