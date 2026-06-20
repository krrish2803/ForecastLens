import pandas as pd
import numpy as np
from prophet import Prophet
import warnings
warnings.filterwarnings('ignore')

np.random.seed(42)

HORIZONS = [30, 60, 90]

def fit_prophet(series: pd.DataFrame, metric: str = 'revenue') -> tuple:
    train = series[['ds', metric]].rename(columns={metric: 'y'})
    train = train.dropna().sort_values('ds')
    train['y'] = train['y'].clip(lower=0)
    use_log = metric == 'revenue'
    if use_log:
        train['y'] = np.log1p(train['y'])
    m = Prophet(
        interval_width=0.8,
        seasonality_mode='additive',
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
    )
    m.add_seasonality(name='monthly', period=30.5, fourier_order=5)
    m.fit(train)
    return m, use_log

def forecast_channel(m: Prophet, horizon_days: int, use_log: bool = False) -> dict:
    future = m.make_future_dataframe(periods=horizon_days)
    forecast = m.predict(future)
    future_only = forecast.tail(horizon_days)
    if use_log:
        daily_rev = np.expm1(future_only[['yhat_lower', 'yhat', 'yhat_upper']].values)
        return {
            'p10': max(0, daily_rev[:, 0].sum()),
            'p50': max(0, daily_rev[:, 1].sum()),
            'p90': max(0, daily_rev[:, 2].sum()),
            'daily': future_only[['ds', 'yhat_lower', 'yhat', 'yhat_upper']].to_dict('records'),
        }
    return {
        'p10': max(0, future_only['yhat_lower'].sum()),
        'p50': max(0, future_only['yhat'].sum()),
        'p90': max(0, future_only['yhat_upper'].sum()),
        'daily': future_only[['ds', 'yhat_lower', 'yhat', 'yhat_upper']].to_dict('records'),
    }

def forecast_all_channels(features_path: str) -> dict:
    daily = pd.read_parquet(features_path)
    results = {}

    for channel in daily['channel'].unique():
        ch_data = daily[daily['channel'] == channel].copy()
        results[channel] = {}

        rev_model, use_log = fit_prophet(ch_data, 'revenue')
        spend_model, _ = fit_prophet(ch_data, 'spend')

        for horizon in HORIZONS:
            rev_fc = forecast_channel(rev_model, horizon, use_log)
            spend_fc = forecast_channel(spend_model, horizon, False)

            floor_p10 = max(spend_fc['p50'] * 0.3, 1.0)
            safe_p10 = max(spend_fc['p10'], floor_p10)
            safe_p50 = max(spend_fc['p50'], 1.0)
            safe_p90 = max(spend_fc['p90'], 1.0)

            roas_p10 = rev_fc['p10'] / safe_p90
            roas_p50 = rev_fc['p50'] / safe_p50
            roas_p90 = rev_fc['p90'] / safe_p10

            results[channel][horizon] = {
                'revenue_p10': round(rev_fc['p10'], 2),
                'revenue_p50': round(rev_fc['p50'], 2),
                'revenue_p90': round(rev_fc['p90'], 2),
                'spend_p10': round(spend_fc['p10'], 2),
                'spend_p50': round(spend_fc['p50'], 2),
                'spend_p90': round(spend_fc['p90'], 2),
                'roas_p10': round(roas_p10, 2),
                'roas_p50': round(roas_p50, 2),
                'roas_p90': round(roas_p90, 2),
                'daily': rev_fc['daily'],
            }

    return results
