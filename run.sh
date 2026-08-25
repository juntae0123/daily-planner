#!/usr/bin/env bash
# 일해라 김준태 서버 - bash run.sh
set -e
cd "$(dirname "$0")"
CANDIDATES=(
  "$HOME/miniforge3/envs/dev_daily/python.exe"
  "$HOME/Miniforge3/envs/dev_daily/python.exe"
  "/c/Users/SSAFY/miniforge3/envs/dev_daily/python.exe"
  "/c/ProgramData/miniforge3/envs/dev_daily/python.exe"
)
PYTHON=""
for p in "${CANDIDATES[@]}"; do
  [ -f "$p" ] && PYTHON="$p" && break
done
if [ -z "$PYTHON" ]; then
  PYTHON=$(find /c/Users/SSAFY /c/ProgramData -maxdepth 4 \
    -path "*envs/dev_daily/python.exe" 2>/dev/null | head -1)
fi
if [ -z "$PYTHON" ]; then
  echo "FAIL: dev_daily python.exe 못 찾음 -> conda env list 출력 가져와라"
  exit 1
fi
echo "python: $PYTHON"
exec "$PYTHON" -m uvicorn server.main:app --port 8177 --reload
