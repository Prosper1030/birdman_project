#!/usr/bin/env bash

set -euo pipefail

projectRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$projectRoot"

pythonBin="${PYTHON_BIN:-$(command -v python3)}"

echo "==> 準備 Birdman Project 的 macOS 環境"

if [ ! -d ".venv" ]; then
  echo "==> 建立虛擬環境 .venv"
  if command -v uv >/dev/null 2>&1; then
    uv venv .venv --python "$pythonBin" --seed --no-managed-python --no-python-downloads
  else
    "$pythonBin" -m venv .venv
  fi
fi

if ! "$projectRoot/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "==> 補裝 pip"
  "$projectRoot/.venv/bin/python" -m ensurepip --upgrade
fi

echo "==> 安裝／更新必要套件"
"$projectRoot/.venv/bin/python" -m pip install --upgrade pip
"$projectRoot/.venv/bin/python" -m pip install -r "$projectRoot/requirements.txt"

echo ""
echo "安裝完成。"
echo "CLI 範例：$projectRoot/.venv/bin/python main.py --dsm sample_data/DSM.csv --wbs sample_data/WBS.csv"
echo "GUI 啟動：$projectRoot/.venv/bin/python -m src.gui_qt"
echo "DSM 編輯器：$projectRoot/.venv/bin/python run_dsm_editor.py"
