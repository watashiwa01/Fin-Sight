#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8140}"
export PORT
echo "Starting Fin-Sight on http://127.0.0.1:${PORT}"
python api.py

