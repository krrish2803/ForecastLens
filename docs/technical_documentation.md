# Technical Documentation

## System Overview

AIgnition Forecast is a probabilistic revenue forecasting tool that ingests ad channel CSV data (Google Ads, Bing Ads, Meta Ads) and produces P10/P50/P90 revenue and ROAS forecasts using Facebook Prophet.

## Pipeline

### run.sh
The entry point accepts three positional arguments:
1. `DATA_DIR` — directory containing CSV files (default: `./data`)
2. `MODEL_PATH` — path to trained Prophet model pickle (default: `./pickle/model.pkl`)
3. `OUTPUT_PATH` — path for predictions CSV (default: `./output/predictions.csv`)

Steps:
1. `generate_features.py --data-dir DATA_DIR --out features.parquet`
2. `predict.py --features features.parquet --model MODEL_PATH --output OUTPUT_PATH`

### Data Ingestion (ingest.py)

| Channel | Key Transformation |
|---------|-------------------|
| Google Ads | `metrics_cost_micros` divided by 1,000,000 |
| Bing Ads | Revenue=0 auto-detection with click-based proxy |
| Meta Ads | Revenue derived from conversions * 120 or spend * 1.8 |

### Feature Engineering (generate_features.py)

Features generated per channel per day:
- ROAS (revenue / spend)
- CTR (clicks / impressions)
- Day of week, month, weekend flag, month-end flag
- Spend lag (7 days)
- ROAS rolling 14-day average
- Revenue rolling 7-day average
- Blended (cross-channel) total revenue and ROAS

### Forecasting (forecast.py)

- Model: Facebook Prophet 1.1.5
- Prediction interval: 80% (P10-P90)
- Seasonality: multiplicative, with weekly, monthly, yearly components
- Changepoint prior scale: 0.05
- Forecast horizons: 30, 60, 90 days

ROAS ranges are computed as:
- P10: revenue_p10 / spend_p90
- P50: revenue_p50 / spend_p50
- P90: revenue_p90 / spend_p10

### Budget Simulation (budget_sim.py)

Uses diminishing returns log curve:
- revenue = k * log(spend + 1), where k = base_revenue / log(base_spend + 1)
- Uncertainty grows with spend delta: 15% base + 10% per relative change
- Marginal ROAS used for recommendation

### LLM Summary (llm_summary.py)

Sends channel stats, forecast results, and data quality flags to Anthropic Claude API.
Returns 3 bullet points explaining causal factors behind the forecast.

## API Endpoints (api/main.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/upload | POST | Upload CSV files |
| /api/forecast | POST | Run forecast pipeline |
| /api/simulate | POST | Budget simulation |
| /api/summary | GET | LLM causal summary |
| / | GET | Serves frontend dashboard |

## Output Format (predictions.csv)

```
channel,horizon_days,revenue_p10,revenue_p50,revenue_p90,roas_p10,roas_p50,roas_p90
google,30,28000.0,35000.0,43000.0,2.8,3.5,4.2
...
```
