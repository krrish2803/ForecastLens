import argparse
import json
import numpy as np
import pandas as pd
from typing import Optional


def compute_k(spend: float, revenue: float) -> float:
    """Compute the log-curve scale factor k: revenue = k * ln(spend + 1)."""
    if spend > 0 and revenue > 0:
        return revenue / np.log(spend + 1)
    return 0.0


def optimize(
    current_spends: dict,
    current_revenues: dict,
    total_budget: float,
    min_spends: Optional[dict] = None,
    max_spends: Optional[dict] = None,
    tolerance: float = 0.01,
) -> dict:
    """
    Optimal budget allocation via marginal-ROAS equalization.

    Uses the diminishing-returns log-curve model:
        revenue_i = k_i * ln(spend_i + 1)
        marginal_ROAS_i = k_i / (spend_i + 1)

    The algorithm equalizes marginal ROAS across all channels (water-filling)
    subject to budget and per-channel min/max constraints.
    """
    channels = list(current_spends.keys())

    if min_spends is None:
        min_spends = {ch: 0.0 for ch in channels}
    if max_spends is None:
        max_spends = {ch: float('inf') for ch in channels}

    k = {ch: compute_k(current_spends[ch], current_revenues[ch]) for ch in channels}

    min_sum = sum(min_spends.get(ch, 0.0) for ch in channels)
    if total_budget < min_sum - 0.01:
        raise ValueError(
            f"Total budget ${total_budget:,.0f} < sum of minimum spends ${min_sum:,.0f}"
        )

    # Water-filling: iteratively allocate budget, fixing constrained channels
    remaining = total_budget
    active = set(channels)
    optimal = {}

    while active:
        lo = 1e-12
        hi = max(k[ch] for ch in active) + 1.0

        for _ in range(60):
            lam = (lo + hi) / 2.0
            total = 0.0
            for ch in active:
                raw = (k[ch] / lam - 1.0) if k[ch] > 0 else 0.0
                total += max(min_spends[ch], min(max_spends[ch], raw))
            if total > remaining:
                lo = lam
            else:
                hi = lam

        lam = (lo + hi) / 2.0

        new_spends = {}
        touched = set()
        for ch in active:
            raw = (k[ch] / lam - 1.0) if k[ch] > 0 else 0.0
            s = max(min_spends[ch], min(max_spends[ch], raw))
            new_spends[ch] = s
            if s <= min_spends[ch] or s >= max_spends[ch]:
                touched.add(ch)

        if not touched or len(active) == len(touched):
            optimal.update(new_spends)
            break

        for ch in touched:
            optimal[ch] = new_spends[ch]
            remaining -= new_spends[ch]
            active.remove(ch)

    # Round and compute derived metrics
    results = {}
    total_cur_spend = 0.0
    total_cur_rev = 0.0
    total_opt_spend = 0.0
    total_opt_rev = 0.0

    for ch in channels:
        cs = current_spends[ch]
        cr = current_revenues[ch]
        os_ = max(0.0, optimal[ch])
        or_ = k[ch] * np.log(os_ + 1.0) if k[ch] > 0 else 0.0

        cur_marg = (k[ch] / (cs + 1.0)) if k[ch] > 0 and cs > 0 else 0.0
        opt_marg = (k[ch] / (os_ + 1.0)) if k[ch] > 0 else 0.0

        results[ch] = {
            'current_spend': round(cs, 2),
            'optimal_spend': round(os_, 2),
            'spend_delta': round(os_ - cs, 2),
            'spend_delta_pct': round((os_ - cs) / max(cs, 0.01) * 100, 1),
            'current_revenue': round(cr, 2),
            'optimal_revenue': round(or_, 2),
            'revenue_delta': round(or_ - cr, 2),
            'current_marginal_roas': round(cur_marg, 4),
            'optimal_marginal_roas': round(opt_marg, 4),
            'k': round(k[ch], 4),
        }
        total_cur_spend += cs
        total_cur_rev += cr
        total_opt_spend += os_
        total_opt_rev += or_

    margs = [results[ch]['optimal_marginal_roas'] for ch in channels if results[ch]['optimal_spend'] > 0]
    spread = max(margs) - min(margs) if margs else 0.0

    # Convert numpy types to native Python for JSON serialization
    def pyfloat(v):
        return float(round(v, 2))
    def pyfloat1(v):
        return float(round(v, 1))

    return {
        'channels': results,
        'summary': {
            'total_current_spend': pyfloat(total_cur_spend),
            'total_optimal_spend': pyfloat(total_opt_spend),
            'total_current_revenue': pyfloat(total_cur_rev),
            'total_optimal_revenue': pyfloat(total_opt_rev),
            'revenue_delta': pyfloat(total_opt_rev - total_cur_rev),
            'revenue_delta_pct': pyfloat1(
                (total_opt_rev - total_cur_rev) / max(total_cur_rev, 0.01) * 100
            ),
            'current_blended_roas': pyfloat(
                total_cur_rev / max(total_cur_spend, 0.01)
            ),
            'optimal_blended_roas': pyfloat(
                total_opt_rev / max(total_opt_spend, 0.01)
            ),
            'marginal_roas_converged': bool(spread < tolerance),
            'marginal_roas_spread': float(round(spread, 4)),
            'convergence_iterations': int(len(channels) - len(active)) if active else int(len(channels)),
        },
    }


def load_channel_data(data_dir: str, avg_revenue: Optional[str] = None,
                      horizon_days: int = 30):
    """Load current spend and revenue per channel from raw CSVs."""
    from src.ingest import load_all
    df = load_all(data_dir)
    daily = df.groupby('ds').agg(
        spend=('spend', 'sum'),
        revenue=('revenue', 'sum'),
    ).reset_index()
    daily = daily.sort_values('ds')
    last_daily = daily.tail(30)

    if avg_revenue is None:
        avg_rev = last_daily['revenue'].mean()
    else:
        avg_rev = float(avg_revenue)

    spends = {}
    revenues = {}
    for ch in df['channel'].unique():
        ch_data = df[df['channel'] == ch]
        ch_daily = ch_data.groupby('ds').agg(
            spend=('spend', 'sum'),
            revenue=('revenue', 'sum'),
        ).reset_index()
        ch_daily = ch_daily.sort_values('ds')
        ch_last = ch_daily.tail(30)
        spends[ch] = ch_last['spend'].mean() * horizon_days / 30
        revenues[ch] = ch_last['revenue'].mean() * horizon_days / 30

    return spends, revenues


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--total-budget', type=float, required=True)
    parser.add_argument('--out', default='./output/optimized.json')
    args = parser.parse_args()

    spends, revenues = load_channel_data(args.data_dir)
    result = optimize(spends, revenues, args.total_budget)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Optimization saved to {args.out}")
    s = result['summary']
    print(f"Revenue: ${s['total_current_revenue']:,.0f} → ${s['total_optimal_revenue']:,.0f} ({s['revenue_delta_pct']:+.1f}%)")
    print(f"ROAS:    {s['current_blended_roas']}x → {s['optimal_blended_roas']}x")
    print(f"Converged: {s['marginal_roas_converged']} (spread: {s['marginal_roas_spread']})")
