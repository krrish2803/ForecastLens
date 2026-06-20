import anthropic
import json
import pandas as pd
import os

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            _client = anthropic.Anthropic(api_key=api_key)
    return _client

SYSTEM_PROMPT = """You are a senior digital marketing analyst at a top e-commerce agency.
You are given historical ad channel performance data and a revenue forecast.
Your job: write exactly 3 bullet points explaining WHY revenue is expected to change.

Rules:
- Be specific with numbers and percentages from the data
- Mention seasonality signals if visible
- Flag data quality issues (like Bing revenue attribution gap)
- Mention channel-specific risks (Meta CPM spikes, Google ROAS trends)
- Write for a marketing manager, not a data scientist
- Each bullet max 2 sentences
- Do NOT use jargon like "heteroscedasticity" or "MAPE"
- Output format: exactly 3 bullet points starting with "•"
"""

def generate_summary(
    channel_stats: dict,
    forecast_results: dict,
    flags: dict,
) -> str:
    context = f"""
HISTORICAL PERFORMANCE SUMMARY:
{json.dumps(channel_stats, indent=2)}

FORECAST RESULTS (30/60/90 days):
{json.dumps({
    ch: {
        str(h) + '_days': {
            'revenue_range': f"${v['revenue_p10']:,.0f} — ${v['revenue_p90']:,.0f}",
            'roas_range': f"{v['roas_p10']:.1f}x — {v['roas_p90']:.1f}x"
        }
        for h, v in horizons.items()
    }
    for ch, horizons in forecast_results.items()
}, indent=2)}

DATA QUALITY FLAGS:
{json.dumps(flags, indent=2)}

Write your 3-bullet causal summary now:
"""

    c = get_client()
    if c is None:
        return "• AI summary unavailable — set ANTHROPIC_API_KEY to enable.\n• Revenue trend: see forecast table above for P10/P50/P90 values.\n• Data quality: check flags section for attribution gaps."
    message = c.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": context}],
        system=SYSTEM_PROMPT,
    )
    return message.content[0].text

def build_channel_stats(daily_df) -> dict:
    stats = {}
    for ch in daily_df['channel'].unique():
        ch_data = daily_df[daily_df['channel'] == ch]
        last_30 = ch_data.tail(30)
        prev_30 = ch_data.iloc[-60:-30] if len(ch_data) >= 60 else ch_data.head(30)

        stats[ch] = {
            'avg_daily_spend_last30': round(last_30['spend'].mean(), 2),
            'avg_daily_revenue_last30': round(last_30['revenue'].mean(), 2),
            'avg_roas_last30': round(last_30['roas'].mean(), 2) if 'roas' in last_30 else None,
            'revenue_trend_pct': round(
                (last_30['revenue'].mean() - prev_30['revenue'].mean()) /
                (prev_30['revenue'].mean() + 0.01) * 100, 1
            ),
            'spend_trend_pct': round(
                (last_30['spend'].mean() - prev_30['spend'].mean()) /
                (prev_30['spend'].mean() + 0.01) * 100, 1
            ),
            'revenue_flagged': bool(ch_data.get('revenue_flagged', pd.Series([False])).any()),
        }
    return stats
