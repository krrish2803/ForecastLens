import argparse
import json
import pandas as pd
import numpy as np
from src.ingest import load_all
from src.forecast import fit_prophet, forecast_channel, HORIZONS


def build_ct_daily(data_dir: str) -> pd.DataFrame:
    """Aggregate raw CSVs to daily campaign_type level."""
    df = load_all(data_dir)

    ct = df.groupby(['ds', 'channel', 'campaign_type']).agg(
        revenue=('revenue', 'sum'),
        spend=('spend', 'sum'),
        clicks=('clicks', 'sum'),
        impressions=('impressions', 'sum'),
        conversions=('conversions', 'sum'),
    ).reset_index()

    ct = ct.sort_values(['channel', 'campaign_type', 'ds'])
    ct['roas'] = np.where(ct['spend'] > 0, ct['revenue'] / ct['spend'], 0.0)

    return ct


def reconcile(data_dir: str) -> dict:
    """Bottom-up reconciled forecast: campaign_type -> channel -> blended."""
    ct_daily = build_ct_daily(data_dir)

    result = {
        'campaign_types': {},
        'channels': {},
        'blended': {},
        'verification': {},
    }

    # 1. Forecast each campaign_type individually
    groups = ct_daily.groupby(['channel', 'campaign_type'])

    for (channel, campaign_type), group in groups:
        if len(group) < 14:
            continue
        group = group.copy()

        try:
            rev_model, use_log = fit_prophet(group, 'revenue')
            spend_model, _ = fit_prophet(group, 'spend')
        except Exception:
            continue

        key = f"{channel}_{campaign_type}"
        result['campaign_types'][key] = {
            'channel': channel,
            'campaign_type': campaign_type,
        }

        for horizon in HORIZONS:
            try:
                rev_fc = forecast_channel(rev_model, horizon, use_log)
                spend_fc = forecast_channel(spend_model, horizon, False)
            except Exception:
                continue

            rp10 = max(0.0, rev_fc['p10'])
            rp50 = max(0.0, rev_fc['p50'])
            rp90 = max(0.0, rev_fc['p90'])
            sp = max(0.0, spend_fc['p50'])

            result['campaign_types'][key][horizon] = {
                'revenue_p10': round(rp10, 2),
                'revenue_p50': round(rp50, 2),
                'revenue_p90': round(rp90, 2),
                'spend': round(sp, 2),
                'roas_p50': round(rp50 / sp if sp > 0 else 0.0, 2),
            }

    # 2. Sum campaign_type -> channel
    by_ch = {}
    for key, info in result['campaign_types'].items():
        ch = info['channel']
        by_ch.setdefault(ch, []).append(key)

    for channel, ct_keys in by_ch.items():
        result['channels'][channel] = {}
        for horizon in HORIZONS:
            rp10 = sum(result['campaign_types'][k].get(horizon, {}).get('revenue_p10', 0.0) for k in ct_keys)
            rp50 = sum(result['campaign_types'][k].get(horizon, {}).get('revenue_p50', 0.0) for k in ct_keys)
            rp90 = sum(result['campaign_types'][k].get(horizon, {}).get('revenue_p90', 0.0) for k in ct_keys)
            sp = sum(result['campaign_types'][k].get(horizon, {}).get('spend', 0.0) for k in ct_keys)

            result['channels'][channel][horizon] = {
                'revenue_p10': round(rp10, 2),
                'revenue_p50': round(rp50, 2),
                'revenue_p90': round(rp90, 2),
                'spend': round(sp, 2),
                'roas_p50': round(rp50 / sp if sp > 0 else 0.0, 2),
            }

    # 3. Sum channel -> blended
    for horizon in HORIZONS:
        rp10 = sum(result['channels'][ch].get(horizon, {}).get('revenue_p10', 0.0) for ch in by_ch)
        rp50 = sum(result['channels'][ch].get(horizon, {}).get('revenue_p50', 0.0) for ch in by_ch)
        rp90 = sum(result['channels'][ch].get(horizon, {}).get('revenue_p90', 0.0) for ch in by_ch)
        sp = sum(result['channels'][ch].get(horizon, {}).get('spend', 0.0) for ch in by_ch)

        result['blended'][horizon] = {
            'revenue_p10': round(rp10, 2),
            'revenue_p50': round(rp50, 2),
            'revenue_p90': round(rp90, 2),
            'spend': round(sp, 2),
            'roas_p50': round(rp50 / sp if sp > 0 else 0.0, 2),
        }

    # 4. Verify consistency
    max_disc = 0.0
    all_ok = True
    for channel, ct_keys in by_ch.items():
        for horizon in HORIZONS:
            ct_sum = sum(result['campaign_types'][k].get(horizon, {}).get('revenue_p50', 0.0) for k in ct_keys)
            ch_val = result['channels'][channel].get(horizon, {}).get('revenue_p50', 0.0)
            disc = abs(ct_sum - ch_val)
            if disc > max_disc:
                max_disc = disc
            if disc > 0.01:
                all_ok = False

    for horizon in HORIZONS:
        ch_sum = sum(result['channels'][ch].get(horizon, {}).get('revenue_p50', 0.0) for ch in by_ch)
        bl_val = result['blended'].get(horizon, {}).get('revenue_p50', 0.0)
        disc = abs(ch_sum - bl_val)
        if disc > max_disc:
            max_disc = disc
        if disc > 0.01:
            all_ok = False

    result['verification'] = {
        'all_levels_consistent': all_ok,
        'max_discrepancy_p50': round(max_disc, 4),
        'levels': ['campaign_type', 'channel', 'blended'],
        'method': 'bottom-up_sum',
    }

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--out', default='./output/reconciled.json')
    args = parser.parse_args()

    r = reconcile(args.data_dir)
    with open(args.out, 'w') as f:
        json.dump(r, f, indent=2)
    print(f"Reconciled forecast saved to {args.out}")
    print(f"Consistent: {r['verification']['all_levels_consistent']}")
