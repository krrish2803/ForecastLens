"""Unit tests for core modules — no Prophet/IO dependency."""

import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import pandas as pd

# ─── 1. OPTIMIZER ──────────────────────────────────────────

from src.optimizer import optimize

def test_optimizer_convergence():
    spends = {'google': 5000.0, 'meta': 3800.0}
    revenues = {'google': 15500.0, 'meta': 10000.0}
    result = optimize(spends, revenues, total_budget=10000)
    assert result['summary']['marginal_roas_converged'], "Marginal ROAS must converge"
    assert result['summary']['marginal_roas_spread'] < 0.01, "Spread must be near zero"

def test_optimizer_budget_exhausted():
    spends = {'google': 5000.0, 'meta': 3800.0}
    revenues = {'google': 15500.0, 'meta': 10000.0}
    result = optimize(spends, revenues, total_budget=50000)
    total_opt = sum(c['optimal_spend'] for c in result['channels'].values())
    assert abs(total_opt - 50000) < 1, f"Budget must be fully allocated (got {total_opt})"

def test_optimizer_constraints():
    spends = {'google': 5000.0, 'meta': 3800.0}
    revenues = {'google': 15500.0, 'meta': 10000.0}
    result = optimize(spends, revenues, total_budget=10000,
                      min_spends={'google': 3000, 'meta': 2000})
    assert result['channels']['google']['optimal_spend'] >= 3000, "Min constraint not respected"

# ─── 2. RECONCILIATION ─────────────────────────────────────

from src.reconciliation import reconcile

def _write_mock_csv(data_dir, filename, rows, google_style=False, meta_style=False):
    """Write mock CSV with column names matching each ingest function."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, filename)
    df = pd.DataFrame(rows)
    # Ensure required columns exist
    for col in ['campaign_id', 'conversions']:
        if col not in df.columns:
            df[col] = 1
    if google_style:
        df = df.rename(columns={
            'date': 'segments_date', 'spend': 'metrics_cost_micros',
            'revenue': 'metrics_conversions_value', 'clicks': 'metrics_clicks',
            'impressions': 'metrics_impressions', 'conversions': 'metrics_conversions',
            'campaign_type': 'campaign_advertising_channel_type',
            'campaign_name': 'campaign_name', 'campaign_id': 'campaign_id',
        })
    if meta_style:
        df = df.rename(columns={'date': 'date_start', 'conversions': 'conversion',
                                 'campaign_name': 'campaign_name', 'campaign_id': 'campaign_id'})
    df.to_csv(path, index=False)
    return path

def test_reconciliation_bottom_up():
    with tempfile.TemporaryDirectory() as tmp:
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        np.random.seed(42)
        for ch, fname, ct, gs, ms in [('google', 'google_ads.csv', 'SEARCH', True, False),
                                       ('meta', 'meta.csv', 'SOCIAL', False, True)]:
            spend = np.random.uniform(50, 200, 100)
            data = {
                'date': dates.strftime('%Y-%m-%d'),
                'campaign_name': [f'{ch}_{ct}_{i}' for i in range(100)],
                'campaign_type': [ct] * 100,
                'spend': spend,
                'impressions': np.random.randint(5000, 50000, 100),
                'clicks': np.random.randint(100, 2000, 100),
            }
            if gs:
                data['revenue'] = spend * np.random.uniform(1.5, 4.0, 100)
            _write_mock_csv(tmp, fname, data, google_style=gs, meta_style=ms)

        result = reconcile(tmp)
        assert result['verification']['all_levels_consistent']
        assert result['verification']['max_discrepancy_p50'] == 0.0

# ─── 3. QUALITY SCORECARD ──────────────────────────────────

from src.quality import scorecard

def test_quality_perfect_data():
    with tempfile.TemporaryDirectory() as tmp:
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        _write_mock_csv(tmp, 'google_ads.csv', {
            'date': dates.strftime('%Y-%m-%d'),
            'campaign_name': ['google_SEARCH_1'] * 180,
            'campaign_type': ['SEARCH'] * 180,
            'spend': np.random.uniform(100, 300, 180),
            'impressions': np.random.randint(10000, 50000, 180),
            'clicks': np.random.randint(200, 3000, 180),
            'revenue': np.random.uniform(200, 1200, 180),
        }, google_style=True)
        # Add a second channel for diversity bonus
        dates2 = pd.date_range('2025-01-01', periods=180, freq='D')
        _write_mock_csv(tmp, 'meta.csv', {
            'date': dates2.strftime('%Y-%m-%d'),
            'campaign_name': ['meta_SOCIAL_1'] * 180,
            'campaign_type': ['SOCIAL'] * 180,
            'spend': np.random.uniform(100, 300, 180),
            'impressions': np.random.randint(10000, 50000, 180),
            'clicks': np.random.randint(200, 3000, 180),
        }, meta_style=True)
        q = scorecard(tmp)
        assert q['overall_grade'] in ('A', 'B', 'C'), f"Expected A/B/C, got {q['overall_grade']}"
        assert q['confidence_penalty'] < 0.3

def test_quality_zero_revenue_penalty():
    with tempfile.TemporaryDirectory() as tmp:
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        _write_mock_csv(tmp, 'meta.csv', {
            'date': dates.strftime('%Y-%m-%d'),
            'campaign_name': ['meta_SOCIAL_1'] * 180,
            'campaign_type': ['SOCIAL'] * 180,
            'spend': np.random.uniform(100, 300, 180),
            'impressions': np.random.randint(10000, 50000, 180),
            'clicks': np.random.randint(200, 3000, 180),
            'conversions': [0] * 180,
        }, meta_style=True)
        q = scorecard(tmp)
        assert q['confidence_penalty'] > 0.3, "Zero revenue should lower score"

def test_quality_sparse_data_penalty():
    with tempfile.TemporaryDirectory() as tmp:
        dates = pd.date_range('2025-01-01', periods=10, freq='D')
        _write_mock_csv(tmp, 'google_ads.csv', {
            'date': dates.strftime('%Y-%m-%d'),
            'campaign_name': ['google_SEARCH_1'] * 10,
            'campaign_type': ['SEARCH'] * 10,
            'spend': np.random.uniform(100, 300, 10),
            'impressions': np.random.randint(10000, 50000, 10),
            'clicks': np.random.randint(200, 3000, 10),
            'revenue': np.random.uniform(200, 1200, 10),
        }, google_style=True)
        q = scorecard(tmp)
        assert q['overall_grade'] in ('D', 'F'), f"Sparse data should get D/F, got {q['overall_grade']}"
        assert q['confidence_penalty'] > 0.5

# ─── 4. SCENARIOS ──────────────────────────────────────────

from src.scenarios import generate, PREDEFINED

def test_scenarios_all_present():
    with tempfile.TemporaryDirectory() as tmp:
        sc_parquet = os.path.join(tmp, 'features.parquet')
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        df = pd.DataFrame({
            'ds': dates,
            'channel': 'meta',
            'revenue': np.random.uniform(100, 500, 180),
            'spend': np.random.uniform(30, 150, 180),
            'clicks': np.random.randint(100, 1000, 180),
            'impressions': np.random.randint(5000, 30000, 180),
            'conversions': np.random.uniform(1, 20, 180),
            'revenue_flagged': False,
            'roas': np.random.uniform(1.0, 5.0, 180),
            'ctr': np.random.uniform(0.01, 0.05, 180),
            'day_of_week': dates.dayofweek,
            'month': dates.month,
            'is_weekend': (dates.dayofweek >= 5).astype(int),
            'is_month_end': (dates.is_month_end).astype(int),
            'spend_lag_7d': np.random.uniform(30, 150, 180),
            'roas_rolling_14d': np.random.uniform(1.0, 5.0, 180),
            'revenue_rolling_7d': np.random.uniform(100, 500, 180),
        })
        df.to_parquet(sc_parquet)
        result = generate(sc_parquet, horizon=30)
        assert 'base' in result
        assert 'conservative' in result
        assert 'aggressive' in result
        assert result['conservative']['blended']['revenue_p50'] < result['base']['blended']['revenue_p50']
        assert result['aggressive']['blended']['revenue_p50'] > result['base']['blended']['revenue_p50']

def test_scenarios_custom():
    with tempfile.TemporaryDirectory() as tmp:
        sc_parquet = os.path.join(tmp, 'features.parquet')
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        df = pd.DataFrame({
            'ds': dates, 'channel': 'meta',
            'revenue': np.random.uniform(100, 500, 180),
            'spend': np.random.uniform(30, 150, 180),
            'clicks': np.random.randint(100, 1000, 180),
            'impressions': np.random.randint(5000, 30000, 180),
            'conversions': np.random.uniform(1, 20, 180),
            'revenue_flagged': False,
            'roas': np.random.uniform(1.0, 5.0, 180),
            'ctr': np.random.uniform(0.01, 0.05, 180),
            'day_of_week': dates.dayofweek, 'month': dates.month,
            'is_weekend': (dates.dayofweek >= 5).astype(int),
            'is_month_end': (dates.is_month_end).astype(int),
            'spend_lag_7d': np.random.uniform(30, 150, 180),
            'roas_rolling_14d': np.random.uniform(1.0, 5.0, 180),
            'revenue_rolling_7d': np.random.uniform(100, 500, 180),
        })
        df.to_parquet(sc_parquet)
        result = generate(sc_parquet, horizon=30,
                          custom={'cpc_change': 0.1, 'cvr_change': -0.05})
        custom_p50 = result['custom']['blended']['revenue_p50']
        base_p50 = result['base']['blended']['revenue_p50']
        assert custom_p50 < base_p50, "CPC up + CVR down should reduce revenue"

# ─── 5. DRIVER DECOMPOSITION ───────────────────────────────

from src.drivers import decompose

def test_drivers_fisher_exact():
    """Verify spend_effect + efficiency_effect = Δrevenue exactly."""
    with tempfile.TemporaryDirectory() as tmp:
        dates = pd.date_range('2025-06-01', periods=90, freq='D')
        np.random.seed(42)
        spend = np.linspace(100, 150, 90) + np.random.normal(0, 10, 90)
        rev = (spend * (2.5 + np.sin(np.arange(90) * 0.1) * 0.5))
        _write_mock_csv(tmp, 'meta.csv', {
            'date': dates.strftime('%Y-%m-%d'),
            'campaign_name': ['meta_SOCIAL_1'] * 90,
            'campaign_type': ['SOCIAL'] * 90,
            'spend': spend,
            'impressions': np.random.randint(5000, 30000, 90),
            'clicks': np.random.randint(100, 2000, 90),
            'conversions': rev / 50,
        }, meta_style=True)
        result = decompose(tmp)
        bl = result['blended']
        total_effect = round(bl['spend_effect'] + bl['efficiency_effect'], 1)
        change = round(bl['change_abs'], 1)
        assert total_effect == change, f"{total_effect} != {change}"
        # Check per-channel too
        for ch, cd in result['channels'].items():
            total = round(cd['drivers']['spend_effect'] + cd['drivers']['efficiency_effect'], 1)
            delta = round(cd['change_abs'], 1)
            assert total == delta, f"Channel {ch}: {total} != {delta}"

# ─── 6. RISK DETECTION ─────────────────────────────────────

from src.risks import detect

def test_risks_returns_alerts():
    with tempfile.TemporaryDirectory() as tmp:
        dates = pd.date_range('2025-01-01', periods=120, freq='D')
        rev = np.random.uniform(100, 500, 120)
        rev[-14:] = rev[-14:] * 0.3
        _write_mock_csv(tmp, 'google_ads.csv', {
            'date': dates.strftime('%Y-%m-%d'),
            'campaign_name': ['google_SEARCH_1'] * 120,
            'campaign_type': ['SEARCH'] * 120,
            'spend': np.random.uniform(50, 200, 120),
            'impressions': np.random.randint(5000, 50000, 120),
            'clicks': np.random.randint(100, 2000, 120),
            'revenue': rev,
        }, google_style=True)
        result = detect(tmp)
        assert 'alerts' in result
        assert result['alert_count'] >= 0
        for a in result['alerts']:
            for field in ['channel', 'type', 'severity', 'title', 'message', 'recommendation']:
                assert field in a, f"Missing field: {field}"

# ─── 7. GATING ─────────────────────────────────────────────

from src.gating import apply_gating

def test_gating_widens_bands():
    with tempfile.TemporaryDirectory() as tmp:
        sc_parquet = os.path.join(tmp, 'features.parquet')
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        df = pd.DataFrame({
            'ds': dates, 'channel': 'meta',
            'revenue': np.random.uniform(100, 500, 180),
            'spend': np.random.uniform(30, 150, 180),
            'clicks': np.random.randint(100, 1000, 180),
            'impressions': np.random.randint(5000, 30000, 180),
            'conversions': np.random.uniform(1, 20, 180),
            'revenue_flagged': False,
            'roas': np.random.uniform(1.0, 5.0, 180),
            'ctr': np.random.uniform(0.01, 0.05, 180),
            'day_of_week': dates.dayofweek, 'month': dates.month,
            'is_weekend': (dates.dayofweek >= 5).astype(int),
            'is_month_end': (dates.is_month_end).astype(int),
            'spend_lag_7d': np.random.uniform(30, 150, 180),
            'roas_rolling_14d': np.random.uniform(1.0, 5.0, 180),
            'revenue_rolling_7d': np.random.uniform(100, 500, 180),
        })
        df.to_parquet(sc_parquet)
        result = apply_gating(sc_parquet, alpha=2.0)
        for ch in result['gated']:
            for h in result['gated'][ch]:
                raw_p10 = result['raw'][ch][h]['revenue_p10']
                gate_p10 = result['gated'][ch][h]['revenue_p10']
                raw_p90 = result['raw'][ch][h]['revenue_p90']
                gate_p90 = result['gated'][ch][h]['revenue_p90']
                assert gate_p10 <= raw_p10, f"Gated P10 should be <= raw P10 for {ch} {h}d"
                assert gate_p90 >= raw_p90, f"Gated P90 should be >= raw P90 for {ch} {h}d"

# ─── 8. FORECAST CHANGE ────────────────────────────────────

from src.forecast_change import decompose as fc_decompose

def test_fc_decompose_structure():
    with tempfile.TemporaryDirectory() as tmp:
        sc_parquet = os.path.join(tmp, 'features.parquet')
        pred_csv = os.path.join(tmp, 'predictions.csv')
        dates = pd.date_range('2025-01-01', periods=180, freq='D')
        np.random.seed(42)
        df = pd.DataFrame({
            'ds': dates, 'channel': 'meta',
            'revenue': np.random.uniform(100, 500, 180),
            'spend': np.random.uniform(30, 150, 180),
            'clicks': np.random.randint(100, 1000, 180),
            'impressions': np.random.randint(5000, 30000, 180),
            'conversions': np.random.uniform(1, 20, 180),
            'revenue_flagged': False,
            'roas': np.random.uniform(1.0, 5.0, 180),
            'ctr': np.random.uniform(0.01, 0.05, 180),
            'day_of_week': dates.dayofweek, 'month': dates.month,
            'is_weekend': (dates.dayofweek >= 5).astype(int),
            'is_month_end': (dates.is_month_end).astype(int),
            'spend_lag_7d': np.random.uniform(30, 150, 180),
            'roas_rolling_14d': np.random.uniform(1.0, 5.0, 180),
            'revenue_rolling_7d': np.random.uniform(100, 500, 180),
        })
        df.to_parquet(sc_parquet)
        pd.DataFrame({
            'channel': ['meta', 'blended'],
            'horizon_days': [30, 30],
            'revenue_p10': [2000, 2000],
            'revenue_p50': [5000, 5000],
            'revenue_p90': [12000, 12000],
            'spend_p10': [500, 500],
            'spend_p50': [1000, 1000],
            'spend_p90': [2000, 2000],
            'roas_p10': [1.0, 1.0],
            'roas_p50': [5.0, 5.0],
            'roas_p90': [24.0, 24.0],
        }).to_csv(pred_csv, index=False)
        result = fc_decompose(sc_parquet, pred_csv, horizon=30)
        assert 'blended' in result
        assert 'channels' in result
        bl = result['blended']
        for key in ['actual', 'forecast', 'delta', 'drivers']:
            assert key in bl
        d = bl['drivers']
        total = round(d['spend_effect'] + d['efficiency_effect'], 1)
        change = round(bl['delta']['revenue'], 1)
        assert total == change, f"Fisher exactness: {total} != {change}"

# ─── RUN ───────────────────────────────────────────────────

if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
