#!/usr/bin/env bash

set -euo pipefail

projectRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$projectRoot"

pythonBin="$projectRoot/.venv/bin/python"

if [ ! -x "$pythonBin" ]; then
  echo "尚未建立 .venv，先執行 macOS 安裝腳本..."
  "$projectRoot/scripts/setup_mac.sh"
fi

if ! "$pythonBin" -m pip show py2app >/dev/null 2>&1; then
  echo "==> 安裝 py2app"
  "$pythonBin" -m pip install py2app
fi

echo "==> 清理舊的 macOS app 產物"
rm -rf "$projectRoot/build" "$projectRoot/dist"

echo "==> 建立 Birdman Project.app（開發模式）"
"$pythonBin" "$projectRoot/scripts/birdman_app_setup.py" py2app -A

appPath="$projectRoot/dist/Birdman Project.app"
if [ ! -d "$appPath" ]; then
  echo "建立 Birdman Project.app 失敗" >&2
  exit 1
fi

echo ""
echo "已建立：$appPath"
echo "這是開發模式 app，會直接使用目前 repo 的原始碼。"
echo "如果之後搬動專案資料夾，請重新執行 scripts/build_birdman_app.sh。"
