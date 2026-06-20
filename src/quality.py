import pandas as pd
import numpy as np
from pathlib import Path
from src.ingest import load_all


_GRADES = [
    (90, 'A', 'Excellent'),
    (75, 'B', 'Good'),
    (60, 'C', 'Fair'),
    (40, 'D', 'Poor'),
    (0, 'F', 'Critical'),
]


def _grade(score: float) -> str:
    for threshold, letter, _ in _GRADES:
        if score >= threshold:
            return letter
    return 'F'


def _grade_label(score: float) -> str:
    for threshold, _, label in _GRADES:
        if score >= threshold:
            return label
    return 'Critical'


def scorecard(data_dir: str) -> dict:
    """Analyze raw CSVs and return a quality scorecard with per-channel scores and issues."""
    try:
        df = load_all(data_dir)
    except ValueError as e:
        return {
            'overall_score': 0.0,
            'overall_grade': 'F',
            'overall_label': 'Critical',
            'channels': {},
            'confidence_penalty': 1.0,
            'fatal_error': str(e),
        }

    channels = sorted(df['channel'].unique())
    channel_data = {}

    for ch in channels:
        ch_df = df[df['channel'] == ch].sort_values('ds').copy()
        issues = []

        # 1. Data volume
        n_days = ch_df['ds'].nunique()
        if n_days < 14:
            issues.append({'check': 'data_volume', 'severity': 'error',
                           'message': f'Only {n_days} days — minimum 30 required for reliable forecasting'})
        elif n_days < 30:
            issues.append({'check': 'data_volume', 'severity': 'warning',
                           'message': f'Only {n_days} days — 60+ recommended for seasonality detection'})
        elif n_days < 60:
            issues.append({'check': 'data_volume', 'severity': 'info',
                           'message': f'{n_days} days — adequate but more history improves accuracy'})

        # 2. Revenue completeness
        zero_rev = (ch_df['revenue'] == 0).mean()
        if zero_rev > 0.80:
            issues.append({'check': 'revenue_attribution', 'severity': 'error',
                           'message': f'{zero_rev:.0%} of rows have $0 revenue — revenue model will be unreliable'})
        elif zero_rev > 0.30:
            issues.append({'check': 'revenue_attribution', 'severity': 'warning',
                           'message': f'{zero_rev:.0%} of rows have $0 revenue — gap may bias forecasts low'})

        revenue_source = ch_df['revenue_source'].iloc[0] if 'revenue_source' in ch_df.columns else 'tracked'
        if 'proxy' in str(revenue_source):
            issues.append({'check': 'revenue_proxy', 'severity': 'warning',
                           'message': f'Revenue is {revenue_source} — accuracy depends on proxy quality'})

        # 3. Date coverage continuity
        dr = pd.date_range(ch_df['ds'].min(), ch_df['ds'].max(), freq='D')
        missing = len(dr) - ch_df['ds'].nunique()
        cov = ch_df['ds'].nunique() / len(dr) if len(dr) > 0 else 1.0
        if cov < 0.70:
            issues.append({'check': 'date_gaps', 'severity': 'error',
                           'message': f'Date coverage: {cov:.0%} — {missing} missing days create gaps in the time series'})
        elif cov < 0.90:
            issues.append({'check': 'date_gaps', 'severity': 'warning',
                           'message': f'Date coverage: {cov:.0%} — {missing} days missing'})

        # 4. Spend = 0 with revenue > 0 anomalies
        anomalies = ch_df[(ch_df['spend'] == 0) & (ch_df['revenue'] > 0)]
        if len(anomalies) > 5:
            issues.append({'check': 'spend_anomaly', 'severity': 'warning',
                           'message': f'{len(anomalies)} rows with revenue>0 but $0 spend — possible data pipeline issue'})

        # 5. Campaign naming consistency
        camps = ch_df['campaign_name'].dropna().unique()
        if len(camps) > 1:
            prefixes = set()
            for c in camps:
                c = str(c).strip()
                if '_' in c:
                    prefixes.add(c.split('_')[0])
                elif '-' in c:
                    prefixes.add(c.split('-')[0])
                else:
                    prefixes.add(c[:8])
            if len(prefixes) > max(3, len(camps) * 0.5):
                issues.append({'check': 'naming_inconsistency', 'severity': 'info',
                               'message': f'{len(prefixes)} naming prefixes across {len(camps)} campaigns — consider standardizing'})

        # 6. Data freshness
        last = ch_df['ds'].max()
        now = pd.Timestamp.now()
        stale_days = (now - last).days
        if stale_days > 60:
            issues.append({'check': 'stale_data', 'severity': 'warning',
                           'message': f'Data ends {stale_days} days ago — forecast may not reflect recent trends'})
        elif stale_days > 30:
            issues.append({'check': 'stale_data', 'severity': 'info',
                           'message': f'Data ends {stale_days} days ago'})

        # 7. ROAS outlier detection
        roas = ch_df['revenue'] / ch_df['spend'].replace(0, np.nan)
        extreme = roas.dropna()
        if len(extreme) > 0:
            p99 = extreme.quantile(0.99)
            outlier_count = (extreme > p99 * 3).sum() if p99 > 0 else 0
            if outlier_count > 3:
                issues.append({'check': 'roas_outliers', 'severity': 'info',
                               'message': f'{outlier_count} extreme ROAS values detected (>3x 99th percentile)'})

        # Compute score
        deductions = {'error': 25, 'warning': 10, 'info': 3}
        score = 100.0
        for iss in issues:
            score -= deductions.get(iss['severity'], 0)
        score = max(0.0, min(100.0, score))

        channel_data[ch] = {
            'score': round(score, 1),
            'grade': _grade(score),
            'label': _grade_label(score),
            'issues': issues,
            'n_days': n_days,
            'zero_revenue_pct': round(zero_rev * 100, 1),
            'revenue_source': revenue_source,
        }

    # Overall score (volume-weighted)
    total_days = sum(cd['n_days'] for cd in channel_data.values()) or 1
    overall = sum(cd['score'] * cd['n_days'] / total_days for cd in channel_data.values())

    # Channel diversity bonus/penalty
    if len(channels) < 3:
        overall -= 10 * (3 - len(channels))

    overall = max(0.0, min(100.0, overall))

    penalty = round((100.0 - overall) / 100.0, 2)

    return {
        'overall_score': round(overall, 1),
        'overall_grade': _grade(overall),
        'overall_label': _grade_label(overall),
        'channels': channel_data,
        'confidence_penalty': penalty,
        'channels_found': channels,
        'channels_expected': 3,
        'fatal_error': None,
    }


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--out', default='./output/quality.json')
    args = parser.parse_args()

    result = scorecard(args.data_dir)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Quality scorecard saved to {args.out}")
    print(f"Overall: {result['overall_grade']} ({result['overall_score']})")
    for ch, cd in result.get('channels', {}).items():
        print(f"  {ch}: {cd['grade']} ({cd['score']}) — {len(cd['issues'])} issues")
