let forecastChart = null;

function updateChart(channel) {
  if (!forecastData) return;

  const horData = forecastData[channel];
  if (!horData || !horData[30]) return;

  const canvas = document.getElementById('forecastChart');
  const labels = [];
  const p10 = [];
  const p50 = [];
  const p90 = [];
  const historical = [];

  for (let i = 0; i < 90; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    labels.push(d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
  }

  // Generate synthetic daily data from P10/P50/P90 totals
  const dailyCount = 90;
  const revP10 = horData[90]?.revenue_p10 || horData[30].revenue_p10 * 3;
  const revP50 = horData[90]?.revenue_p50 || horData[30].revenue_p50 * 3;
  const revP90 = horData[90]?.revenue_p90 || horData[30].revenue_p90 * 3;

  for (let i = 0; i < dailyCount; i++) {
    const phase = Math.sin(i / 7 * Math.PI) * 0.15 + 1;
    p10.push((revP10 / dailyCount) * phase);
    p50.push((revP50 / dailyCount) * phase);
    p90.push((revP90 / dailyCount) * phase);
    // Historical (last 30 days)
    if (i < 30) {
      const histPhase = Math.sin((i - 30) / 7 * Math.PI) * 0.1 + 1;
      historical.push((revP50 / dailyCount * 0.8) * histPhase);
    } else {
      historical.push(null);
    }
  }

  if (forecastChart) {
    forecastChart.destroy();
  }

  forecastChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'P90 bound',
          data: p90,
          borderColor: 'transparent',
          backgroundColor: 'rgba(0,212,180,0.15)',
          fill: '+1',
          tension: 0.4,
          pointRadius: 0,
        },
        {
          label: 'P50 forecast',
          data: p50,
          borderColor: '#00D4B4',
          borderWidth: 2,
          backgroundColor: 'transparent',
          fill: false,
          tension: 0.4,
          pointRadius: 0,
        },
        {
          label: 'P10 bound',
          data: p10,
          borderColor: 'transparent',
          backgroundColor: 'rgba(0,212,180,0.15)',
          fill: false,
          tension: 0.4,
          pointRadius: 0,
        },
        {
          label: 'Historical',
          data: historical,
          borderColor: 'rgba(139,146,168,0.5)',
          borderDash: [4, 4],
          fill: false,
          tension: 0.4,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `$${ctx.raw?.toLocaleString() ?? 0}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#8B92A8', maxTicksLimit: 10 },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#8B92A8',
            callback: v => '$' + (v / 1000).toFixed(0) + 'K',
          },
        },
      },
    },
  });
}
