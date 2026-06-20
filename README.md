# AIgnition Forecast

Probabilistic revenue intelligence for e-commerce marketing channels. Forecast, reconcile, optimize, and explain multi-channel ad performance with uncertainty quantification.

---

## Quick Start

```bash
# 1. Create virtual environment (Python 3.9+)
python3.9 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place CSV exports in ./data/
#    Supported files: google_ads.csv, bing.csv, meta.csv

# 4. Run the full pipeline
bash run.sh

# 5. Launch the API + dashboard
uvicorn api.main:app --reload --port 8000
#    → Dashboard: http://localhost:8000/dashboard/
#    → Landing:   http://localhost:8000/
```

---

## Data Requirements

Place CSVs with these columns in `./data/`:

| File | Key Columns |
|------|------------|
| `google_ads.csv` | `segments_date`, `metrics_cost_micros`, `metrics_conversions_value`, `metrics_clicks`, `metrics_impressions`, `metrics_conversions`, `campaign_advertising_channel_type`, `campaign_name` |
| `bing.csv` | `TimePeriod`, `Spend`, `Revenue`, `Clicks`, `Impressions`, `Conversions`, `CampaignType`, `CampaignName` |
| `meta.csv` | `date_start`, `spend`, `impressions`, `clicks`, `conversion`, `campaign_name` |

> **Demo mode**: If the API is unreachable, the dashboard falls back to realistic mock data so you can explore all features immediately.

---

## Features

### Forecasting Engine
- **Prophet-based** probabilistic forecasts with P10/P50/P90 bands per channel
- Log-transform for revenue (handles exponential growth), additive seasonality
- 30/60/90 day horizons with daily granularity

### Bottom-Up Reconciliation
- Forecasts at campaign-type granularity, sums to channel level, sums to blended total
- **Verified**: all levels internally consistent with zero discrepancy

### Budget Optimizer
- Marginal-ROAS equalization using water-filling algorithm
- Diminishing-returns log curve: `revenue = k × ln(spend + 1)`
- Per-channel min/max constraints, automatic budget redistribution

### Data Quality Scorecard
- 7 checks per channel: data volume, revenue attribution, date gaps, naming consistency, staleness, spend anomalies, ROAS outliers
- A–F grade with confidence penalty that widens forecast bands

### Scenario Planner
- Base / Conservative (CPC +15%, CVR −10%) / Aggressive (CPC −5%, CVR +10%, seasonal +15%)
- Custom scenario with user-defined CPC, CVR, and seasonal multipliers

### Driver Decomposition
- Fisher ideal decomposition: splits revenue change into **spend effect** + **efficiency effect**
- **Exact**: spend_effect + efficiency_effect = Δrevenue (zero residual)

### Forecast Change Decomposition
- Compares recent 30d actuals vs 30d forecast
- Same Fisher decomposition applied to the forward-looking delta

### Risk & Anomaly Alerts
- 7 detectors: spend-efficiency divergence, concentration risk, ROAS drift, spend spikes, tracking gaps, zero-return spend, naming instability
- Severity levels: error / warning / info with actionable recommendations

### Quality-Gated Confidence Bands
- Automatically widens P10/P90 bands based on data quality scorecard
- Toggle on/off in the dashboard to see the impact

### AI Causal Summary
- Claude API generates 3 bullet points explaining what drives the forecast
- Graceful fallback when API key is not configured

---

## Project Structure

```
aignition-forecast/
├── api/
│   └── main.py                  # FastAPI server — 11 endpoints
├── data/                        # Input CSV exports (gitignored)
├── frontend/
│   ├── index.html               # Dashboard HTML
│   ├── css/style.css            # Glassmorphism dark theme
│   └── js/app.js                # All frontend logic + mock data
├── output/                      # Pipeline outputs (gitignored)
├── pickle/                      # Trained models (gitignored)
├── src/
│   ├── ingest.py                # CSV loading, column mapping, revenue proxies
│   ├── generate_features.py     # Daily aggregation, features, blended channel
│   ├── forecast.py              # Prophet fitting with log-transform
│   ├── predict.py               # Writes predictions.csv
│   ├── train.py                 # Offline model training
│   ├── reconciliation.py        # Bottom-up campaign_type → channel → blended
│   ├── optimizer.py             # Water-filling marginal-ROAS equalization
│   ├── budget_sim.py            # What-if budget simulator
│   ├── quality.py               # 7-check data quality scorecard
│   ├── scenarios.py             # Multiplier-based scenario planner
│   ├── drivers.py               # Fisher ideal decomposition
│   ├── forecast_change.py       # Forecast vs actuals comparison
│   ├── risks.py                 # 7 anomaly/risk detectors
│   ├── gating.py                # Quality-based confidence band adjustment
│   ├── llm_summary.py          # Claude API causal summary
│   └── utils.py                 # Shared utilities
├── tests/
│   └── test_core.py             # 13 unit tests across 8 modules
├── landing.html                 # Premium SaaS landing page
├── run.sh                       # End-to-end pipeline script
├── Dockerfile                   # Multi-stage container build
├── requirements.txt
└── .env.example                 # Environment configuration
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload CSV files |
| POST | `/api/forecast` | Run probabilistic forecast |
| POST | `/api/reconcile` | Bottom-up reconciliation |
| POST | `/api/optimize` | Budget optimizer (marginal ROAS) |
| POST | `/api/simulate` | What-if budget simulation |
| POST | `/api/quality` | Data quality scorecard |
| POST | `/api/scenarios` | Scenario comparison |
| POST | `/api/drivers` | Spend/efficiency decomposition |
| POST | `/api/forecast-change` | Forecast vs actuals decomposition |
| POST | `/api/risks` | Risk & anomaly detection |
| POST | `/api/gating` | Quality-gated confidence bands |
| GET | `/api/summary` | AI causal summary |
| GET | `/` | Landing page |
| GET | `/dashboard/{path}` | Dashboard SPA |

---

## Pipeline (`run.sh`)

```bash
#!/usr/bin/env bash
# 1. Generate features from raw CSVs
# 2. Run Prophet forecasts → predictions.csv
# 3. Bottom-up reconciliation → reconciled.json
# 4. Scenario planner → scenarios.json
# 5. Forecast change decomposition → forecast_change.json
# 6. Quality-gated confidence bands → gated_forecast.json
```

---

## Key Design Decisions

- **Union `|` type syntax not used** — Python 3.9 compatibility; all type hints use `Optional[]` and `typing` imports
- **No internet calls at runtime** — Prophet runs locally; Claude API call is optional with fallback
- **Mock data in frontend** — every API feature has a `getMock*()` function so the dashboard works standalone
- **Fisher decomposition** — symmetric split of interaction term between spend and efficiency; exact with zero residual
- **Water-filling optimizer** — equalizes marginal ROAS (not average ROAS) across channels; handles min/max constraints

---

## Testing

```bash
# Run all unit tests
python -m pytest tests/ -v

# Expected: 13/13 passed
```

---

## License

MIT
