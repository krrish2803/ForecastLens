"""Risk and anomaly alerting — detect patterns that could invalidate the forecast."""

import argparse
import json
import numpy as np
import pandas as pd
from src.ingest import load_all


def detect(data_dir: str) -> dict:
    """Scan raw data and return a list of risk/anomaly alerts."""
    df = load_all(data_dir)

    daily = df.groupby(['ds', 'channel']).agg(
        revenue=('revenue', 'sum'),
        spend=('spend', 'sum'),
        clicks=('clicks', 'sum'),
        conversions=('conversions', 'sum'),
    ).reset_index().sort_values(['channel', 'ds'])

    daily['roas'] = np.where(daily['spend'] > 0,
                             daily['revenue'] / daily['spend'], np.nan)

    alerts = []

    for ch in sorted(daily['channel'].unique()):
        ch_d = daily[daily['channel'] == ch].copy()
        ch_r = df[df['channel'] == ch].sort_values('ds')
        if ch_d.empty:
            continue

        # 1. Spend-efficiency divergence
        if len(ch_d) >= 14:
            last14 = ch_d.tail(14)
            sp_trend = last14['spend'].pct_change().mean()
            roas_trend = last14['roas'].pct_change().mean()
            if sp_trend > 0.03 and roas_trend is not None and roas_trend < -0.03:
                alerts.append({
                    'channel': ch, 'type': 'spend_efficiency_divergence',
                    'severity': 'warning',
                    'title': 'Spend rising while ROAS declining',
                    'message': f'Spend trending +{sp_trend * 100:.0f}% but ROAS trending {roas_trend * 100:.0f}% over last 14 days',
                    'recommendation': 'Audit campaign performance before committing more budget',
                    'metric': 'roas', 'direction': 'negative',
                })

        # 2. Concentration risk
        if not ch_r.empty and 'campaign_name' in ch_r.columns:
            camp_rev = ch_r.groupby('campaign_name')['revenue'].sum()
            if len(camp_rev) > 1:
                top_share = camp_rev.max() / camp_rev.sum()
                if top_share > 0.50:
                    top_camp = camp_rev.idxmax()
                    alerts.append({
                        'channel': ch, 'type': 'concentration_risk',
                        'severity': 'warning',
                        'title': 'High campaign concentration',
                        'message': f'Top campaign "{top_camp}" drives {top_share:.0%} of {ch} revenue (${camp_rev.max():,.0f} of ${camp_rev.sum():,.0f})',
                        'recommendation': 'Diversify spend to reduce single-campaign dependency',
                        'metric': 'revenue', 'direction': 'neutral',
                    })

        # 3. ROAS drift (performance instability)
        if len(ch_d) >= 14:
            w1 = ch_d.tail(7)['roas'].dropna()
            w2 = ch_d.iloc[-14:-7]['roas'].dropna()
            if len(w1) >= 3 and len(w2) >= 3:
                drift = (w1.mean() - w2.mean()) / max(abs(w2.mean()), 0.01)
                if abs(drift) > 0.25:
                    direction = 'positive' if drift > 0 else 'negative'
                    alerts.append({
                        'channel': ch, 'type': 'roas_drift',
                        'severity': 'info',
                        'title': f'ROAS drift: {drift * 100:+.0f}%',
                        'message': f'ROAS shifted {drift * 100:+.0f}% last 7d vs prior week ({w2.mean():.2f}x → {w1.mean():.2f}x)',
                        'recommendation': 'Check for campaign changes, creative rotations, or audience shifts',
                        'metric': 'roas', 'direction': direction,
                    })

        # 4. Spend spike
        if len(ch_d) >= 14:
            mu = ch_d['spend'].mean()
            sd = ch_d['spend'].std()
            last_sp = ch_d['spend'].iloc[-1]
            if sd > 0 and last_sp > mu + 3 * sd:
                alerts.append({
                    'channel': ch, 'type': 'spend_spike',
                    'severity': 'info',
                    'title': 'Spend spike detected',
                    'message': f'Latest day spend (${last_sp:,.0f}) is >3σ above mean (${mu:,.0f})',
                    'recommendation': 'Verify no data ingestion error or one-time campaign launch',
                    'metric': 'spend', 'direction': 'positive',
                })

        # 5. Tracking coverage decline
        if 'revenue_source' in ch_r.columns:
            srcs = ch_r['revenue_source'].value_counts()
            proxy_pct = sum(srcs.get(s, 0) for s in ['click_proxy', 'spend_proxy']) / len(ch_r)
            if proxy_pct > 0.5:
                alerts.append({
                    'channel': ch, 'type': 'tracking_coverage',
                    'severity': 'warning',
                    'title': 'Attribution gap: proxy revenue',
                    'message': f'{proxy_pct:.0%} of rows use proxy revenue (not directly attributed)',
                    'recommendation': 'Fix conversion tracking pipeline for reliable ROAS measurement',
                    'metric': 'revenue', 'direction': 'negative',
                })

        # 6. Zero-return spend (spend > 0, revenue = 0)
        zero_ret = ch_d[(ch_d['spend'] > 0) & (ch_d['revenue'] == 0)]
        if len(zero_ret) > len(ch_d) * 0.1:
            alerts.append({
                'channel': ch, 'type': 'zero_return_spend',
                'severity': 'warning',
                'title': 'Significant zero-return spend',
                'message': f'{len(zero_ret)} of {len(ch_d)} days ({len(zero_ret) / len(ch_d):.0%}) have spend > $0 with $0 attributed revenue',
                'recommendation': 'Review attribution pipeline — spend may be going to untracked placements',
                'metric': 'revenue', 'direction': 'negative',
            })

        # 7. Naming instability
        if 'campaign_name' in ch_r.columns:
            camps = ch_r['campaign_name'].dropna().unique()
            if len(camps) > 15:
                alerts.append({
                    'channel': ch, 'type': 'naming_instability',
                    'severity': 'info',
                    'title': 'High campaign count',
                    'message': f'{len(camps)} unique campaign names — may indicate dynamic naming or tagging instability',
                    'recommendation': 'Standardize campaign naming conventions and limit auto-generated campaigns',
                    'metric': 'campaigns', 'direction': 'neutral',
                })

    # Sort: errors first, then warnings, then info
    severity_order = {'error': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda a: (severity_order.get(a['severity'], 3), a['channel']))

    counts = {'error': 0, 'warning': 0, 'info': 0}
    for a in alerts:
        sev = a['severity']
        if sev in counts:
            counts[sev] += 1

    return {
        'alerts': alerts,
        'alert_count': len(alerts),
        'critical_count': counts['error'],
        'warning_count': counts['warning'],
        'info_count': counts['info'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--out', default='./output/risks.json')
    args = parser.parse_args()
    result = detect(args.data_dir)
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Risks saved to {args.out}")
    print(f"{result['alert_count']} alerts ({result['warning_count']} warnings, {result['info_count']} info)")
    for a in result['alerts']:
        print(f"  [{a['severity']}] {a['channel']}: {a['title']}")
