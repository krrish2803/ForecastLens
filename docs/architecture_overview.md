# Architecture Overview

## System Diagram

```mermaid
flowchart TD
    subgraph INPUT["Input Layer"]
        G[google_ads_campaign_stats.csv]
        B[bing_campaign_stats.csv]
        M[meta_ads_campaign_stats.csv]
    end

    subgraph PIPELINE["run.sh Pipeline"]
        IN[ingest.py\nNormalize + clean]
        FE[generate_features.py\nFeature engineering]
        FC[forecast.py\nProphet P10/P50/P90]
        PR[predict.py\nWrite predictions.csv]
    end

    subgraph MODELS["pickle/"]
        MP[model.pkl\nTrained Prophet models]
        SC[channel_scalers.pkl\nNorm params]
    end

    subgraph AI["AI Layer"]
        LS[llm_summary.py\nClaude API]
        BS[budget_sim.py\nDiminishing returns]
    end

    subgraph FRONTEND["Frontend"]
        FE2[index.html\nDashboard]
        CH[charts.js\nChart.js bands]
        API[FastAPI\nmain.py]
    end

    subgraph OUTPUT["Output"]
        OUT[predictions.csv\nP10/P50/P90 per channel]
    end

    G --> IN
    B --> IN
    M --> IN
    IN --> FE
    FE --> FC
    FC --> PR
    MP --> PR
    SC --> IN
    PR --> OUT
    FC --> LS
    FC --> BS
    LS --> API
    BS --> API
    API --> FE2
    FE2 --> CH
```

## Stack

| Layer | Technology |
|-------|-----------|
| Forecasting | Facebook Prophet 1.1.5 |
| Backend | FastAPI + Python 3.11 |
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Charts | Chart.js 4.x |
| LLM | Anthropic Claude API |
| Data | Pandas + PyArrow |
| Model storage | joblib pickle |
| Submission | run.sh -> CSV |

## Data Flow

1. `run.sh ./data ./pickle/model.pkl ./output/predictions.csv`
2. `generate_features.py` reads all CSVs dynamically from `data/`
3. Normalizes: Google cost micros / 1M, Bing revenue proxy, Meta attribution flags
4. Saves `features.parquet`
5. `predict.py` loads `model.pkl`, runs Prophet forecast per channel
6. Writes `predictions.csv` with P10/P50/P90 per channel per horizon
