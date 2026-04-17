#!/bin/bash

set -euo pipefail

projectRoot="$(cd "$(dirname "$0")" && pwd)"
cd "$projectRoot"

if [ ! -x "$projectRoot/.venv/bin/python" ]; then
  echo "尚未建立 .venv，先執行 macOS 安裝腳本..."
  "$projectRoot/scripts/setup_mac.sh"
fi

cacheRoot="${TMPDIR:-/tmp}/birdman_project_cache"
mkdir -p "$cacheRoot/matplotlib" "$cacheRoot/xdg/fontconfig"
export MPLBACKEND="${MPLBACKEND:-Qt5Agg}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$cacheRoot/matplotlib}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$cacheRoot/xdg}"

exec "$projectRoot/.venv/bin/python" -m src.gui_qt
