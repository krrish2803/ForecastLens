#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${1:-./data}"
MODEL_PATH="${2:-./pickle/model.pkl}"
OUTPUT_PATH="${3:-./output/predictions.csv}"
VENV_PY="${VENV_PYTHON:-./.venv/bin/python}"

mkdir -p "$(dirname "$OUTPUT_PATH")"

$VENV_PY -m src.generate_features \
  --data-dir "$DATA_DIR" \
  --out features.parquet

$VENV_PY -m src.predict \
  --features features.parquet \
  --model "$MODEL_PATH" \
  --output "$OUTPUT_PATH"

$VENV_PY -m src.reconciliation \
  --data-dir "$DATA_DIR" \
  --out ./output/reconciled.json

$VENV_PY -m src.scenarios \
  --features features.parquet \
  --horizon 30 \
  --out ./output/scenarios.json

$VENV_PY -m src.forecast_change \
  --features features.parquet \
  --predictions ./output/predictions.csv \
  --horizon 30 \
  --out ./output/forecast_change.json

$VENV_PY -m src.gating \
  --features features.parquet \
  --out ./output/gated_forecast.json

echo "Done. Predictions written to $OUTPUT_PATH"
echo "Reconciled forecast saved to ./output/reconciled.json"
echo "Scenarios saved to ./output/scenarios.json"
echo "Forecast change saved to ./output/forecast_change.json"
