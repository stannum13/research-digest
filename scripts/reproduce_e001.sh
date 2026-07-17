#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-experiments/e001/configs/smoke.json}"
python3 scripts/e001_smoke.py "$CONFIG_PATH"
