import argparse
import pandas as pd
import numpy as np
from src.ingest import load_all

def build_features(data_dir: str):
    df = load_all(data_dir)

    daily = df.groupby(['ds', 'channel']).agg(
        revenue=('revenue', 'sum'),
        spend=('spend', 'sum'),
        clicks=('clicks', 'sum'),
        impressions=('impressions', 'sum'),
        conversions=('conversions', 'sum'),
        revenue_flagged=('revenue_flagged', 'max'),
    ).reset_index()

    daily['roas'] = daily.apply(
        lambda r: r['revenue'] / r['spend'] if r['spend'] > 0 else 0, axis=1
    )
    daily['ctr'] = daily.apply(
        lambda r: r['clicks'] / r['impressions'] if r['impressions'] > 0 else 0, axis=1
    )

    daily['day_of_week'] = daily['ds'].dt.dayofweek
    daily['month'] = daily['ds'].dt.month
    daily['is_weekend'] = daily['day_of_week'].isin([5, 6]).astype(int)
    daily['is_month_end'] = daily['ds'].dt.is_month_end.astype(int)

    daily = daily.sort_values(['channel', 'ds'])
    daily['spend_lag_7d'] = daily.groupby('channel')['spend'].shift(7)
    daily['roas_rolling_14d'] = daily.groupby('channel')['roas'].transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )
    daily['revenue_rolling_7d'] = daily.groupby('channel')['revenue'].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )

    blended = daily.groupby('ds').agg(
        revenue=('revenue', 'sum'),
        spend=('spend', 'sum'),
        clicks=('clicks', 'sum'),
        impressions=('impressions', 'sum'),
        conversions=('conversions', 'sum'),
    ).reset_index()
    blended['roas'] = blended['revenue'] / blended['spend'].replace(0, np.nan)
    blended['ctr'] = blended['clicks'] / blended['impressions'].replace(0, np.nan)
    blended['channel'] = 'blended'
    blended['revenue_flagged'] = False
    blended['day_of_week'] = blended['ds'].dt.dayofweek
    blended['month'] = blended['ds'].dt.month
    blended['is_weekend'] = blended['day_of_week'].isin([5, 6]).astype(int)
    blended['is_month_end'] = blended['ds'].dt.is_month_end.astype(int)
    blended = blended.sort_values('ds')
    blended['spend_lag_7d'] = blended['spend'].shift(7)
    blended['roas_rolling_14d'] = blended['roas'].rolling(14, min_periods=3).mean()
    blended['revenue_rolling_7d'] = blended['revenue'].rolling(7, min_periods=1).mean()

    combined = pd.concat([daily, blended], ignore_index=True)

    return combined

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='./data')
    parser.add_argument('--out', default='features.parquet')
    args = parser.parse_args()

    combined = build_features(args.data_dir)
    combined.to_parquet(args.out)
    print(f"Features saved to {args.out}")
