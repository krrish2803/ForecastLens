"""Driver decomposition — decompose revenue changes into spend + efficiency components."""

import argparse
import json
import numpy as np
import pandas as pd
from src.ingest import load_all


def decompose(data_dir: str) -> dict:
    """Decompose revenue change (recent 30d vs prior 30d) into spend and efficiency drivers.

    Uses the Fisher ideal decomposition (symmetric):
        Δrevenue = Δspend × avg(ROAS) + ΔROAS × avg(spend)
    which is exact (no residual term).
    """
    df = load_all(data_dir)

    daily = df.groupby(['ds', 'channel']).agg(
        revenue=('revenue', 'sum'),
        spend=('spend', 'sum'),
    ).reset_index().sort_values(['channel', 'ds'])

    dates = sorted(daily['ds'].unique())
    if len(dates) < 14:
        return {'error': 'Insufficient data — need at least 14 days'}

    # Recent 30d vs prior 30d (or as much as available)
    n = min(30, len(dates) // 2)
    recent_dates = dates[-n:]
    prior_dates = dates[-2 * n:-n] if len(dates) >= 2 * n else dates[:n]

    recent = daily[daily['ds'].isin(recent_dates)]
    prior = daily[daily['ds'].isin(prior_dates)]

    channels = sorted(daily['channel'].unique())
    channel_data = {}
    blended = {'revenue_before': 0.0, 'revenue_after': 0.0,
               'spend_before': 0.0, 'spend_after': 0.0}

    for ch in channels:
        cr = recent[recent['channel'] == ch]
        cp = prior[prior['channel'] == ch]
        if cr.empty or cp.empty:
            continue

        rev_1 = cp['revenue'].mean() * n
        sp_1 = cp['spend'].mean() * n
        roas_1 = rev_1 / sp_1 if sp_1 > 0 else 0.0

        rev_2 = cr['revenue'].mean() * n
        sp_2 = cr['spend'].mean() * n
        roas_2 = rev_2 / sp_2 if sp_2 > 0 else 0.0

        drev = rev_2 - rev_1
        drev_pct = drev / rev_1 * 100 if rev_1 > 0 else 0.0

        dspend = sp_2 - sp_1
        droas = roas_2 - roas_1

        avg_roas = (roas_1 + roas_2) / 2.0
        avg_spend = (sp_1 + sp_2) / 2.0

        spend_eff = dspend * avg_roas
        eff_eff = droas * avg_spend

        # Dominant driver label
        drivers = []
        if abs(spend_eff) > abs(eff_eff) and abs(spend_eff) > 0.01:
            drivers.append('spend')
        if abs(eff_eff) >= abs(spend_eff) and abs(eff_eff) > 0.01:
            drivers.append('efficiency')
        if not drivers:
            drivers.append('stable')

        channel_data[ch] = {
            'revenue_before': round(rev_1, 2),
            'revenue_after': round(rev_2, 2),
            'change_abs': round(drev, 2),
            'change_pct': round(drev_pct, 2),
            'spend_before': round(sp_1, 2),
            'spend_after': round(sp_2, 2),
            'roas_before': round(roas_1, 2),
            'roas_after': round(roas_2, 2),
            'drivers': {
                'spend_effect': round(spend_eff, 2),
                'efficiency_effect': round(eff_eff, 2),
                'spend_pct_of_change': round(spend_eff / drev * 100 if abs(drev) > 0.01 else 0, 1),
                'efficiency_pct_of_change': round(eff_eff / drev * 100 if abs(drev) > 0.01 else 0, 1),
            },
            'dominant_drivers': drivers,
        }

        blended['revenue_before'] += rev_1
        blended['revenue_after'] += rev_2
        blended['spend_before'] += sp_1
        blended['spend_after'] += sp_2

    bl_rev_before = blended['revenue_before']
    bl_rev_after = blended['revenue_after']
    bl_change = bl_rev_after - bl_rev_before
    bl_change_pct = bl_change / bl_rev_before * 100 if bl_rev_before > 0 else 0.0

    bl_spend_eff = sum(cd['drivers']['spend_effect'] for cd in channel_data.values())
    bl_eff_eff = sum(cd['drivers']['efficiency_effect'] for cd in channel_data.values())

    # Per-channel contribution to blended change
    contributions = {}
    for ch, cd in channel_data.items():
        contributions[ch] = {
            'pct_of_blended': round(cd['change_abs'] / bl_change * 100 if abs(bl_change) > 0.01 else 0, 1),
            'spend_pct_of_blended': round(cd['drivers']['spend_effect'] / bl_change * 100 if abs(bl_change) > 0.01 else 0, 1),
            'efficiency_pct_of_blended': round(cd['drivers']['efficiency_effect'] / bl_change * 100 if abs(bl_change) > 0.01 else 0, 1),
        }

    return {
        'periods': {
            'recent': {'days': n, 'start': str(recent_dates[0]), 'end': str(recent_dates[-1])},
            'prior': {'days': n, 'start': str(prior_dates[0]), 'end': str(prior_dates[-1])},
        },
        'channels': channel_data,
        'contributions': contributions,
        'blended': {
            'revenue_before': round(bl_rev_before, 2),
            'revenue_after': round(bl_rev_after, 2),
            'change_abs': round(bl_change, 2),
            'change_pct': round(bl_change_pct, 2),
            'spend_effect': round(bl_spend_eff, 2),
            'efficiency_effect': round(bl_eff_eff, 2),
            'spend_pct_of_change': round(bl_spend_eff / bl_change * 100 if abs(bl_change) > 0.01 else 0, 1),
            'efficiency_pct_of_change': round(bl_eff_eff / bl_change * 100 if abs(bl_change) > 0.01 else 0, 1),
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--out', default='./output/drivers.json')
    args = parser.parse_args()
    result = decompose(args.data_dir)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    bl = result.get('blended', {})
    print(f"Drivers saved to {args.out}")
    print(f"Revenue: ${bl.get('revenue_before', 0):,.0f} → ${bl.get('revenue_after', 0):,.0f} ({bl.get('change_pct', 0):+.1f}%)")
    print(f"  Spend effect:      ${bl.get('spend_effect', 0):,.0f} ({bl.get('spend_pct_of_change', 0):+.1f}% of change)")
    print(f"  Efficiency effect: ${bl.get('efficiency_effect', 0):,.0f} ({bl.get('efficiency_pct_of_change', 0):+.1f}% of change)")
