import pandas as pd
import numpy as np
from pathlib import Path

REVENUE_ZERO_THRESHOLD = 0.80

def load_google(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={
        'segments_date': 'ds',
        'metrics_cost_micros': 'spend',
        'metrics_conversions_value': 'revenue',
        'metrics_clicks': 'clicks',
        'metrics_impressions': 'impressions',
        'metrics_conversions': 'conversions',
        'campaign_advertising_channel_type': 'campaign_type',
        'campaign_name': 'campaign_name',
        'campaign_id': 'campaign_id',
    })
    df['spend'] = df['spend'] / 1_000_000
    df['channel'] = 'google'
    df['ds'] = pd.to_datetime(df['ds'])
    df['revenue_flagged'] = False
    df['revenue_source'] = 'tracked'
    return df[['ds','channel','campaign_id','campaign_name','campaign_type',
               'spend','revenue','clicks','impressions','conversions',
               'revenue_flagged','revenue_source']]

def load_bing(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={
        'TimePeriod': 'ds',
        'Revenue': 'revenue',
        'Spend': 'spend',
        'Clicks': 'clicks',
        'Impressions': 'impressions',
        'Conversions': 'conversions',
        'CampaignType': 'campaign_type',
        'CampaignName': 'campaign_name',
        'CampaignId': 'campaign_id',
    })
    df['channel'] = 'bing'
    df['ds'] = pd.to_datetime(df['ds'])

    zero_ratio = (df['revenue'] == 0).mean()
    if zero_ratio > REVENUE_ZERO_THRESHOLD:
        nonzero = df[df['revenue'] > 0]
        if len(nonzero) > 10:
            avg_rev_per_click = (nonzero['revenue'] / nonzero['clicks'].replace(0, np.nan)).median()
        else:
            avg_rev_per_click = None

        if avg_rev_per_click and not np.isnan(avg_rev_per_click):
            df['revenue'] = df['clicks'] * avg_rev_per_click
            df['revenue_source'] = 'click_proxy'
        else:
            df['revenue'] = df['spend'] * 1.5
            df['revenue_source'] = 'spend_proxy'

        df['revenue_flagged'] = True
        print(f"[WARN] Bing Revenue={zero_ratio:.0%} zeros. Using proxy. Flag raised for LLM summary.")
    else:
        df['revenue_source'] = 'tracked'
        df['revenue_flagged'] = False

    return df[['ds','channel','campaign_id','campaign_name','campaign_type',
               'spend','revenue','clicks','impressions','conversions',
               'revenue_flagged','revenue_source']]

def load_meta(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={
        'date_start': 'ds',
        'conversion': 'conversions',
        'campaign_name': 'campaign_name',
        'campaign_id': 'campaign_id',
    })
    df['channel'] = 'meta'
    df['ds'] = pd.to_datetime(df['ds'])
    zero_conv = (df['conversions'] == 0).mean()
    df['revenue_flagged'] = zero_conv > 0.9
    df['revenue_source'] = 'spend_proxy' if zero_conv > 0.9 else 'conversion_based'
    df['revenue'] = df.apply(
        lambda r: r['spend'] * 1.8 if r['conversions'] == 0 else r['conversions'],
        axis=1
    )
    df['campaign_type'] = 'SOCIAL'
    return df[['ds','channel','campaign_id','campaign_name','campaign_type',
               'spend','revenue','clicks','impressions','conversions',
               'revenue_flagged','revenue_source']]

def load_all(data_dir: str) -> pd.DataFrame:
    p = Path(data_dir)
    frames = []
    for f in p.glob('*.csv'):
        name = f.name.lower()
        if 'google' in name:
            frames.append(load_google(str(f)))
        elif 'bing' in name or 'microsoft' in name or 'ms_ads' in name:
            frames.append(load_bing(str(f)))
        elif 'meta' in name or 'facebook' in name:
            frames.append(load_meta(str(f)))
    if not frames:
        raise ValueError(f"No recognized CSVs found in {data_dir}")
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values('ds').reset_index(drop=True)
    return df
