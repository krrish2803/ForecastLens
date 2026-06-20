"""Forecast change decomposition — compare forecast vs recent actuals."""

import argparse
import json
import pandas as pd
import numpy as np


def decompose(features_path: str, predictions_path: str,
              horizon: int = 30) -> dict:
    """Compare recent actuals vs forecast, with Fisher-style decomposition.

    Returns per-channel + blended:
      - recent actuals (revenue, spend, ROAS)
      - forecast (revenue, spend, ROAS)
      - delta (abs + %)
      - spend_effect / efficiency_effect
    """
    daily = pd.read_parquet(features_path)
    pred = pd.read_csv(predictions_path)

    channels = [ch for ch in daily['channel'].unique() if ch != 'blended']
    if not channels:
        return {'error': 'No channels in features'}

    result = {'horizon': horizon, 'channels': {}}
    blended_actual = {'revenue': 0.0, 'spend': 0.0}
    blended_forecast = {'revenue': 0.0, 'spend': 0.0}

    for ch in channels:
        ch_data = daily[daily['channel'] == ch].sort_values('ds')
        if len(ch_data) < horizon:
            continue

        recent = ch_data.tail(horizon)
        actual_rev = recent['revenue'].sum()
        actual_spend = recent['spend'].sum()
        actual_roas = actual_rev / max(actual_spend, 0.01)

        fc_row = pred[(pred['channel'] == ch) & (pred['horizon_days'] == horizon)]
        if fc_row.empty:
            continue
        fc = fc_row.iloc[0]
        fc_rev = float(fc['revenue_p50'])
        fc_spend = float(fc['spend_p50'])
        fc_roas = fc_rev / max(fc_spend, 0.01)

        delta_rev = fc_rev - actual_rev
        delta_spend = fc_spend - actual_spend
        delta_roas = fc_roas - actual_roas
        change_pct = ((delta_rev / max(abs(actual_rev), 0.01)) * 100)

        avg_spend = (actual_spend + fc_spend) / 2.0
        avg_roas = (actual_roas + fc_roas) / 2.0
        spend_effect = delta_spend * avg_roas
        efficiency_effect = delta_roas * avg_spend

        result['channels'][ch] = {
            'actual': {
                'revenue': round(actual_rev, 2),
                'spend': round(actual_spend, 2),
                'roas': round(actual_roas, 2),
            },
            'forecast': {
                'revenue': round(fc_rev, 2),
                'spend': round(fc_spend, 2),
                'roas': round(fc_roas, 2),
            },
            'delta': {
                'revenue': round(delta_rev, 2),
                'spend': round(delta_spend, 2),
                'roas': round(delta_roas, 4),
                'change_pct': round(change_pct, 2),
            },
            'drivers': {
                'spend_effect': round(spend_effect, 2),
                'efficiency_effect': round(efficiency_effect, 2),
                'spend_pct_of_change': round((spend_effect / max(abs(spend_effect + efficiency_effect), 0.01)) * 100, 2),
                'efficiency_pct_of_change': round((efficiency_effect / max(abs(spend_effect + efficiency_effect), 0.01)) * 100, 2),
            },
        }

        blended_actual['revenue'] += actual_rev
        blended_actual['spend'] += actual_spend
        blended_forecast['revenue'] += fc_rev
        blended_forecast['spend'] += fc_spend

    # Blended
    ba_rev = blended_actual['revenue']
    ba_spend = blended_actual['spend']
    ba_roas = ba_rev / max(ba_spend, 0.01)
    bf_rev = blended_forecast['revenue']
    bf_spend = blended_forecast['spend']
    bf_roas = bf_rev / max(bf_spend, 0.01)
    bd_rev = bf_rev - ba_rev
    bd_spend = bf_spend - ba_spend
    bd_roas = bf_roas - ba_roas
    bavg_s = (ba_spend + bf_spend) / 2.0
    bavg_r = (ba_roas + bf_roas) / 2.0
    bse = bd_spend * bavg_r
    bee = bd_roas * bavg_s

    result['blended'] = {
        'actual': {
            'revenue': round(ba_rev, 2),
            'spend': round(ba_spend, 2),
            'roas': round(ba_roas, 2),
        },
        'forecast': {
            'revenue': round(bf_rev, 2),
            'spend': round(bf_spend, 2),
            'roas': round(bf_roas, 2),
        },
        'delta': {
            'revenue': round(bd_rev, 2),
            'spend': round(bd_spend, 2),
            'roas': round(bd_roas, 4),
            'change_pct': round((bd_rev / max(abs(ba_rev), 0.01)) * 100, 2),
        },
        'drivers': {
            'spend_effect': round(bse, 2),
            'efficiency_effect': round(bee, 2),
            'spend_pct_of_change': round((bse / max(abs(bse + bee), 0.01)) * 100, 2),
            'efficiency_pct_of_change': round((bee / max(abs(bse + bee), 0.01)) * 100, 2),
        },
    }

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--features', default='features.parquet')
    parser.add_argument('--predictions', default='./output/predictions.csv')
    parser.add_argument('--horizon', type=int, default=30, choices=[30, 60, 90])
    parser.add_argument('--out', default='./output/forecast_change.json')
    args = parser.parse_args()

    result = decompose(args.features, args.predictions, args.horizon)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Forecast change saved to {args.out}")
    for ch, cd in result.get('channels', {}).items():
        d = cd['delta']
        dr = cd['drivers']
        print(f"  {ch}: \${d['revenue']:+,.0f} ({d['change_pct']:+.1f}%) — spend {dr['spend_pct_of_change']:+.0f}% / eff {dr['efficiency_pct_of_change']:+.0f}%")
    b = result.get('blended', {})
    if b:
        d = b['delta']
        dr = b['drivers']
        print(f"  blended: \${d['revenue']:+,.0f} ({d['change_pct']:+.1f}%) — spend {dr['spend_pct_of_change']:+.0f}% / eff {dr['efficiency_pct_of_change']:+.0f}%")
