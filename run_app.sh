#!/usr/bin/env bash
cd "$(dirname "$0")"
for PY in "$HOME/miniforge3/envs/dev_daily/python.exe" \
          "/c/Users/SSAFY/miniforge3/envs/dev_daily/python.exe"; do
  [ -x "$PY" ] && exec "$PY" desktop.py
done
echo "dev_daily python.exe 못 찾음" >&2
exit 1
