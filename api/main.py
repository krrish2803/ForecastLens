import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import shutil, json

from src.ingest import load_all
from src.generate_features import build_features
from src.forecast import forecast_all_channels
from src.budget_sim import simulate
from src.optimizer import optimize as run_optimizer
from src.reconciliation import reconcile as reconcile_forecast
from src.quality import scorecard as data_quality
from src.scenarios import generate as generate_scenarios
from src.drivers import decompose as run_drivers
from src.risks import detect as run_risks
from src.forecast_change import decompose as run_forecast_change
from src.gating import apply_gating as run_gating
from src.llm_summary import generate_summary, build_channel_stats

app = FastAPI(title="AIgnition Forecast API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR = "./data"
FEATURES_PATH = "./features.parquet"

@app.post("/api/upload")
async def upload_csvs(files: list[UploadFile] = File(...)):
    os.makedirs(DATA_DIR, exist_ok=True)
    for f in files:
        with open(f"{DATA_DIR}/{f.filename}", "wb") as out:
            shutil.copyfileobj(f.file, out)
    return {"status": "uploaded", "files": [f.filename for f in files]}

@app.post("/api/forecast")
def run_forecast(horizons: list[int] = [30, 60, 90]):
    combined = build_features(DATA_DIR)
    combined.to_parquet(FEATURES_PATH)
    results = forecast_all_channels(FEATURES_PATH)
    clean = {}
    for ch, h_dict in results.items():
        clean[ch] = {}
        for h, v in h_dict.items():
            clean[ch][h] = {k: v for k, v in v.items() if k != 'daily'}
    return {"status": "ok", "forecast": clean}

@app.post("/api/reconcile")
def run_reconciliation():
    try:
        result = reconcile_forecast(DATA_DIR)
        return {"status": "ok", "reconciled": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/drivers")
def run_decompose():
    try:
        result = run_drivers(DATA_DIR)
        return {"status": "ok", "drivers": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/risks")
def run_risk_detection():
    try:
        result = run_risks(DATA_DIR)
        return {"status": "ok", "risks": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/gating")
def get_gated_forecast(alpha: float = 1.5):
    try:
        from src.generate_features import build_features
        combined = build_features(DATA_DIR)
        combined.to_parquet(FEATURES_PATH)
        result = run_gating(FEATURES_PATH, alpha=alpha)
        return {"status": "ok", "gating": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/forecast-change")
def get_forecast_change(horizon: int = 30):
    try:
        from src.generate_features import build_features
        combined = build_features(DATA_DIR)
        combined.to_parquet(FEATURES_PATH)
        result = run_forecast_change(FEATURES_PATH, "./output/predictions.csv", horizon)
        return {"status": "ok", "forecast_change": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/quality")
def run_quality():
    try:
        result = data_quality(DATA_DIR)
        return {"status": "ok", "quality": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/scenarios")
def run_scenarios(horizon: int = 30, custom: str = "{}"):
    from src.generate_features import build_features
    import json as _json
    try:
        combined = build_features(DATA_DIR)
        combined.to_parquet(FEATURES_PATH)
        custom_dict = _json.loads(custom) if custom and custom != "{}" else None
        result = generate_scenarios(FEATURES_PATH, horizon, custom_dict)
        return {"status": "ok", "scenarios": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/optimize")
def run_optimization(total_budget: float, horizon: int = 30,
                     min_google: float = 0, min_bing: float = 0, min_meta: float = 0,
                     max_google: float = 1e9, max_bing: float = 1e9, max_meta: float = 1e9):
    try:
        from src.optimizer import load_channel_data
        spends, revenues = load_channel_data(DATA_DIR, horizon_days=horizon)
        channels = list(spends.keys())
        min_spends = {}
        max_spends = {}
        for ch in channels:
            var = ch.lower()
            min_spends[ch] = locals().get(f'min_{var}', 0.0)
            max_spends[ch] = locals().get(f'max_{var}', 1e9)
        result = run_optimizer(spends, revenues, total_budget, min_spends, max_spends)
        return {"status": "ok", "optimization": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/simulate")
def run_simulation(channel: str, current_spend: float,
                   new_spend: float, current_revenue_p50: float):
    return simulate(channel, current_spend, new_spend, current_revenue_p50)

@app.get("/api/summary")
def get_summary():
    daily = pd.read_parquet(FEATURES_PATH)
    results = forecast_all_channels(FEATURES_PATH)
    stats = build_channel_stats(daily)
    flags = {ch: {'flagged': bool(daily[daily['channel']==ch]['revenue_flagged'].any())}
             for ch in daily['channel'].unique()
             if 'revenue_flagged' in daily.columns}
    summary = generate_summary(stats, results, flags)
    return {"summary": summary}

@app.get("/")
async def serve_landing():
    path = os.path.join(os.path.dirname(__file__), '..', 'landing.html')
    if os.path.isfile(path):
        return FileResponse(path)
    return {"error": "Landing page not found"}

@app.get("/dashboard/{full_path:path}")
async def serve_dashboard(full_path: str = ""):
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    file_path = os.path.join(frontend_dir, full_path if full_path else "index.html")
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"error": "Dashboard not found"}
