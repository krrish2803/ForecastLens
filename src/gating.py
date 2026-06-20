"""Data-quality gating — adjust forecast confidence bands from quality scorecard."""

import argparse
import json
import numpy as np
from src.quality import scorecard
from src.forecast import forecast_all_channels


def apply_gating(features_path: str, predictions_path: str = None,
                 alpha: float = 1.5) -> dict:
    """Adjust forecast P10/P90 bands using quality confidence penalty.

    Parameters
    ----------
    features_path : str
        Path to features.parquet (used for quality + forecast).
    predictions_path : str or None
        Path to predictions.csv (if None, re-run forecast).
    alpha : float
        Sensitivity multiplier (1.5 = widen bands 50% more than penalty suggests).

    Returns
    -------
    dict with 'raw' and 'gated' forecasts, 'quality' summary, and penalty.
    """
    quality = scorecard('./data')
    penalty = quality.get('confidence_penalty', 0.0)

    forecast = forecast_all_channels(features_path)

    adjust_factor = 1.0 + penalty * alpha

    gated = {}
    for ch, horizons in forecast.items():
        gated[ch] = {}
        for h, v in horizons.items():
            p10 = v['revenue_p10']
            p50 = v['revenue_p50']
            p90 = v['revenue_p90']

            spread_lower = p50 - p10
            spread_upper = p90 - p50

            adj_p10 = max(0, p50 - spread_lower * adjust_factor)
            adj_p90 = p50 + spread_upper * adjust_factor

            gated[ch][h] = {
                'revenue_p10': round(adj_p10, 2),
                'revenue_p50': round(p50, 2),
                'revenue_p90': round(adj_p90, 2),
            }

    raw_summary = {}
    for ch, horizons in forecast.items():
        raw_summary[ch] = {}
        for h, v in horizons.items():
            raw_summary[ch][h] = {
                'revenue_p10': v['revenue_p10'],
                'revenue_p50': v['revenue_p50'],
                'revenue_p90': v['revenue_p90'],
            }

    return {
        'quality': {
            'overall_grade': quality['overall_grade'],
            'overall_score': quality['overall_score'],
            'confidence_penalty': penalty,
        },
        'raw': raw_summary,
        'gated': gated,
        'adjust_factor': round(adjust_factor, 2),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--features', default='features.parquet')
    parser.add_argument('--out', default='./output/gated_forecast.json')
    parser.add_argument('--alpha', type=float, default=1.5)
    args = parser.parse_args()

    result = apply_gating(args.features, alpha=args.alpha)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Gated forecast saved to {args.out}")
    print(f"Quality: {result['quality']['overall_grade']} ({result['quality']['overall_score']}) penalty={result['quality']['confidence_penalty']}")
    print(f"Adjust factor: {result['adjust_factor']}x")
    for ch in result['gated']:
        for h, v in result['gated'][ch].items():
            r = result['raw'][ch][h]
            print(f"  {ch} {h}d: raw P10=${r['revenue_p10']:,.0f}→gated P10=${v['revenue_p10']:,.0f}, raw P90=${r['revenue_p90']:,.0f}→gated P90=${v['revenue_p90']:,.0f}")
