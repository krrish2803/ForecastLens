import numpy as np
from typing import Literal

Channel = Literal['google', 'bing', 'meta']

BASELINE_ROAS = {'google': 3.2, 'bing': 1.8, 'meta': 2.1}

def diminishing_returns_revenue(base_spend: float, new_spend: float,
                                 base_revenue: float) -> float:
    if base_spend <= 0 or base_revenue <= 0:
        return 0
    k = base_revenue / np.log(base_spend + 1)
    return k * np.log(new_spend + 1)

def simulate(
    channel: Channel,
    current_spend: float,
    new_spend: float,
    current_revenue_p50: float,
) -> dict:
    projected_p50 = diminishing_returns_revenue(current_spend, new_spend, current_revenue_p50)

    delta_ratio = abs(new_spend - current_spend) / (current_spend + 1)
    uncertainty = 0.15 + (delta_ratio * 0.10)

    projected_p10 = projected_p50 * (1 - uncertainty)
    projected_p90 = projected_p50 * (1 + uncertainty)

    return {
        'channel': channel,
        'current_spend': round(current_spend, 2),
        'new_spend': round(new_spend, 2),
        'spend_delta': round(new_spend - current_spend, 2),
        'spend_delta_pct': round((new_spend - current_spend) / (current_spend + 1) * 100, 1),
        'revenue_p10': round(max(0, projected_p10), 2),
        'revenue_p50': round(max(0, projected_p50), 2),
        'revenue_p90': round(max(0, projected_p90), 2),
        'roas_p50': round(projected_p50 / new_spend if new_spend > 0 else 0, 2),
        'marginal_roas': round(
            (projected_p50 - current_revenue_p50) / (new_spend - current_spend)
            if new_spend != current_spend else 0, 2
        ),
        'recommendation': _recommendation(
            projected_p50 - current_revenue_p50,
            new_spend - current_spend
        )
    }

def _recommendation(revenue_delta: float, spend_delta: float) -> str:
    if spend_delta == 0:
        return "No change in spend"
    marginal_roas = revenue_delta / spend_delta if spend_delta != 0 else 0
    if marginal_roas > 3:
        return "Strong — marginal ROAS >3x, increase budget"
    elif marginal_roas > 1.5:
        return "Moderate — profitable but diminishing returns visible"
    elif marginal_roas > 1:
        return "Borderline — barely profitable at margin"
    else:
        return "Not recommended — marginal ROAS <1x"
