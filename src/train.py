import joblib
import pandas as pd
from pathlib import Path
from src.forecast import fit_prophet
from src.generate_features import build_features

def train_and_save(data_dir: str = './data', out_dir: str = './pickle'):
    Path(out_dir).mkdir(exist_ok=True)
    combined = build_features(data_dir)

    models = {}
    for channel in combined['channel'].unique():
        ch_data = combined[combined['channel'] == channel]
        rev_model, use_log = fit_prophet(ch_data, 'revenue')
        spend_model, _ = fit_prophet(ch_data, 'spend')
        models[channel] = {
            'revenue': rev_model,
            'spend': spend_model,
            'use_log': use_log,
        }

    joblib.dump(models, f'{out_dir}/model.pkl')
    print(f"Model saved to {out_dir}/model.pkl")

if __name__ == '__main__':
    train_and_save()
