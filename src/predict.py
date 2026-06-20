import argparse
import pandas as pd
import joblib
import csv
import os
from src.forecast import forecast_all_channels

def write_predictions(forecast_results: dict, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    rows = []
    for channel, horizons in forecast_results.items():
        for horizon_days, values in horizons.items():
            rows.append({
                'channel': channel,
                'horizon_days': horizon_days,
                'revenue_p10': values['revenue_p10'],
                'revenue_p50': values['revenue_p50'],
                'revenue_p90': values['revenue_p90'],
                'spend_p10': values['spend_p10'],
                'spend_p50': values['spend_p50'],
                'spend_p90': values['spend_p90'],
                'roas_p10': values['roas_p10'],
                'roas_p50': values['roas_p50'],
                'roas_p90': values['roas_p90'],
            })
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Predictions written: {len(df)} rows -> {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--features', default='features.parquet')
    parser.add_argument('--model', default='./pickle/model.pkl')
    parser.add_argument('--output', default='./output/predictions.csv')
    args = parser.parse_args()

    forecast_results = forecast_all_channels(args.features)
    write_predictions(forecast_results, args.output)
