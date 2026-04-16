#!/bin/bash

set -euo pipefail

projectRoot="$(cd "$(dirname "$0")" && pwd)"
cd "$projectRoot"

if [ ! -x "$projectRoot/.venv/bin/python" ]; then
  echo "尚未建立 .venv，先執行 macOS 安裝腳本..."
  "$projectRoot/scripts/setup_mac.sh"
fi

exec "$projectRoot/.venv/bin/python" -m src.gui_qt
