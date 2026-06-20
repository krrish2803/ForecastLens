# Architecture

## System Overview

```mermaid
graph TB
    subgraph Input["Input Layer"]
        CSV[CSV Files<br/>google_ads.csv<br/>bing.csv<br/>meta.csv]
        UPLOAD[Upload API<br/>POST /api/upload]
    end

    subgraph Processing["Processing Layer"]
        INGEST[Ingest<br/>src/ingest.py]
        FEATURES[Feature Generation<br/>src/generate_features.py]
        FORECAST[Prophet Forecast<br/>src/forecast.py]
        RECONCILE[Reconciliation<br/>src/reconciliation.py]
        QUALITY[Quality Scorecard<br/>src/quality.py]
        OPTIMIZE[Budget Optimizer<br/>src/optimizer.py]
        SCENARIOS[Scenario Planner<br/>src/scenarios.py]
        DRIVERS[Driver Decomposition<br/>src/drivers.py]
        FC_CHANGE[Forecast Change<br/>src/forecast_change.py]
        RISKS[Risk Detection<br/>src/risks.py]
        GATING[Quality Gating<br/>src/gating.py]
        LLM[AI Summary<br/>src/llm_summary.py]
    end

    subgraph Output["Output Layer"]
        PRED[predictions.csv]
        RECON[reconciled.json]
        SCEN[scenarios.json]
        FC[forecast_change.json]
        GATED[gated_forecast.json]
    end

    subgraph API["API Layer — FastAPI"]
        EP_FORECAST[POST /api/forecast]
        EP_RECONCILE[POST /api/reconcile]
        EP_OPTIMIZE[POST /api/optimize]
        EP_QUALITY[POST /api/quality]
        EP_SCENARIOS[POST /api/scenarios]
        EP_DRIVERS[POST /api/drivers]
        EP_FC[POST /api/forecast-change]
        EP_RISKS[POST /api/risks]
        EP_GATING[POST /api/gating]
        EP_SUMMARY[GET /api/summary]
    end

    subgraph Frontend["Frontend — Dashboard"]
        HTML[index.html]
        CSS[style.css]
        JS[app.js + charts.js]
    end

    CSV --> INGEST
    UPLOAD --> CSV
    INGEST --> FEATURES
    FEATURES --> FORECAST
    FEATURES --> QUALITY
    FORECAST --> PRED
    FORECAST --> RECONCILE
    RECONCILE --> RECON
    FORECAST --> SCENARIOS
    SCENARIOS --> SCEN
    FORECAST --> FC_CHANGE
    PRED --> FC_CHANGE
    FC_CHANGE --> FC
    QUALITY --> GATING
    FORECAST --> GATING
    GATING --> GATED

    FORECAST -.-> EP_FORECAST
    RECONCILE -.-> EP_RECONCILE
    OPTIMIZE -.-> EP_OPTIMIZE
    QUALITY -.-> EP_QUALITY
    SCENARIOS -.-> EP_SCENARIOS
    DRIVERS -.-> EP_DRIVERS
    FC_CHANGE -.-> EP_FC
    RISKS -.-> EP_RISKS
    GATING -.-> EP_GATING
    LLM -.-> EP_SUMMARY

    EP_FORECAST --> JS
    EP_RECONCILE --> JS
    EP_OPTIMIZE --> JS
    EP_QUALITY --> JS
    EP_SCENARIOS --> JS
    EP_DRIVERS --> JS
    EP_FC --> JS
    EP_RISKS --> JS
    EP_GATING --> JS
    EP_SUMMARY --> JS

    JS --> HTML
    HTML --> CSS
```

---

## Pipeline Data Flow

```mermaid
flowchart LR
    CSV[Raw CSVs] --> INGEST(ingest.py)
    INGEST --> FEAT(generate_features.py)
    FEAT --> FORECAST(forecast.py)
    FORECAST --> PRED[predictions.csv]
    FORECAST --> RECON(reconciliation.py)
    RECON --> RJ[reconciled.json]
    FORECAST --> SCEN(scenarios.py)
    SCEN --> SJ[scenarios.json]
    FEAT --> FC(forecast_change.py)
    PRED --> FC
    FC --> FCJ[forecast_change.json]
    FEAT --> QUAL(quality.py)
    QUAL --> GATE(gating.py)
    FORECAST --> GATE
    GATE --> GJ[gated_forecast.json]
```

---

## Reconciliation Architecture

```mermaid
graph TB
    subgraph CampaignTypes["Campaign-Type Level"]
        CT1[google_SEARCH<br/>P10/P50/P90]
        CT2[google_DISPLAY<br/>P10/P50/P90]
        CT3[google_SHOPPING<br/>P10/P50/P90]
        CT4[bing_SEARCH<br/>P10/P50/P90]
        CT5[bing_DISPLAY<br/>P10/P50/P90]
        CT6[meta_SOCIAL<br/>P10/P50/P90]
    end

    subgraph Channels["Channel Level"]
        G[Google<br/>sum of campaign types]
        B[Bing<br/>sum of campaign types]
        M[Meta<br/>sum of campaign types]
    end

    subgraph Blended["Blended Level"]
        BLENDED[Total<br/>sum of channels]
    end

    CT1 --> G
    CT2 --> G
    CT3 --> G
    CT4 --> B
    CT5 --> B
    CT6 --> M
    G --> BLENDED
    B --> BLENDED
    M --> BLENDED

    VERIFY[Verification<br/>all_levels_consistent<br/>max_discrepancy_p50 = $0.0] -.-> BLENDED
```

---

## Budget Optimizer Flow

```mermaid
flowchart TD
    INPUT[Total Budget + Min/Max Constraints] --> K[Compute k per channel<br/>revenue = k × ln(spend + 1)]
    K --> WF[Water-Filling Loop]
    WF --> LAMBDA[Binary search λ<br/>marginal ROAS = k / (spend + 1)]
    LAMBDA --> ALLOC[Allocate budget<br/>spend = k/λ - 1]
    ALLOC --> CHECK{Constrained?<br/>spend < min or > max}
    CHECK -->|Yes| FIX[Fix constrained channel<br/>redistribute remainder]
    CHECK -->|No| DONE{All channels<br/>processed?}
    FIX --> WF
    DONE -->|No| WF
    DONE -->|Yes| RESULT[Optimal allocations<br/>marginal ROAS equalized]
```

---

## Fisher Decomposition

```mermaid
flowchart LR
    subgraph Inputs["Input Periods"]
        P1[Period 1<br/>spend₁, revenue₁, ROAS₁]
        P2[Period 2<br/>spend₂, revenue₂, ROAS₂]
    end

    subgraph Effects["Fisher Ideal Effects"]
        SE[Spend Effect<br/>Δspend × avg(ROAS)]
        EE[Efficiency Effect<br/>ΔROAS × avg(spend)]
    end

    subgraph Result["Result"]
        TOTAL[ΔRevenue<br/>= spend_effect + efficiency_effect<br/>✓ zero residual]
    end

    P1 --> SE
    P2 --> SE
    P1 --> EE
    P2 --> EE
    SE --> TOTAL
    EE --> TOTAL
```

---

## Frontend Architecture

```mermaid
graph TB
    subgraph Pages["Pages"]
        LANDING[landing.html<br/>SaaS marketing page]
        DASHBOARD[index.html<br/>Analytics dashboard]
    end

    subgraph DashboardSections["Dashboard Sections"]
        HERO[Upload Zone<br/>Drag-drop CSV upload]
        QUALITY[Data Quality<br/>Scorecard + A-F grade]
        METRICS[Forecast Metrics<br/>Revenue, ROAS, Confidence]
        CHARTS[Probabilistic Charts<br/>Chart.js with P10/P50/P90]
        RECON[Reconciled Table<br/>Campaign → Channel → Blended]
        SIM[Budget Simulator<br/>What-if slider]
        OPT[Budget Optimizer<br/>Allocation bars]
        SCEN[Scenario Compare<br/>Base/Cons/Aggr table]
        DRIVERS[Driver Decomposition<br/>Spend vs Efficiency bars]
        FC[Forecast Change<br/>Actual vs Forecast]
        RISKS[Risk Alerts<br/>Severity-colored cards]
        SUMMARY[AI Causal Summary<br/>Claude bullet points]
    end

    DASHBOARD --> HERO
    DASHBOARD --> QUALITY
    DASHBOARD --> METRICS
    DASHBOARD --> CHARTS
    DASHBOARD --> RECON
    DASHBOARD --> SIM
    DASHBOARD --> OPT
    DASHBOARD --> SCEN
    DASHBOARD --> DRIVERS
    DASHBOARD --> FC
    DASHBOARD --> RISKS
    DASHBOARD --> SUMMARY
```

---

## Technology Stack

```mermaid
graph LR
    subgraph Backend["Backend"]
        PY[Python 3.9]
        FAST[FastAPI]
        PROPHET[Prophet]
        PD[Pandas / NumPy]
        UVICORN[Uvicorn]
    end

    subgraph Frontend["Frontend"]
        HTML[HTML5]
        CSS3[CSS3<br/>Glassmorphism]
        JS[JavaScript<br/>Chart.js]
    end

    subgraph Infra["Infrastructure"]
        DOCKER[Docker]
        ENV[.env config]
    end

    PY --> FAST
    PY --> PROPHET
    PY --> PD
    FAST --> UVICORN
    FAST --> JS
    JS --> HTML
    HTML --> CSS3
    DOCKER --> FAST
    ENV --> FAST
```
