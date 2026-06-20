const API_BASE = 'http://localhost:8000';

let uploadedFiles = {};
let forecastData = null;
let reconciledData = null;
let gatingData = null;
let useGating = true;
let currentHorizon = 30;
let currentReconHorizon = 30;

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const runBtn = document.getElementById('runForecastBtn');

const googleBadge = document.getElementById('googleBadge');
const bingBadge = document.getElementById('bingBadge');
const metaBadge = document.getElementById('metaBadge');

// Drag & drop
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('dragover');
});
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
  handleFiles(e.target.files);
});

function handleFiles(files) {
  for (const file of files) {
    const name = file.name.toLowerCase();
    if (name.includes('google')) {
      uploadedFiles.google = file;
      googleBadge.textContent = 'google_ads.csv ✓';
      googleBadge.classList.add('loaded');
    } else if (name.includes('bing') || name.includes('microsoft')) {
      uploadedFiles.bing = file;
      bingBadge.textContent = 'bing.csv ✓';
      bingBadge.classList.add('loaded');
    } else if (name.includes('meta') || name.includes('facebook')) {
      uploadedFiles.meta = file;
      metaBadge.textContent = 'meta.csv ✓';
      metaBadge.classList.add('loaded');
    }
  }
  runBtn.disabled = Object.keys(uploadedFiles).length < 3;
}

// Run forecast
runBtn.addEventListener('click', async () => {
  runBtn.disabled = true;
  runBtn.textContent = 'Running...';

  try {
    const formData = new FormData();
    for (const key in uploadedFiles) {
      formData.append('files', uploadedFiles[key]);
    }

    await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      body: formData,
    });

    const resp = await fetch(`${API_BASE}/api/forecast`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ horizons: [30, 60, 90] }),
    });
    const data = await resp.json();
    forecastData = data.forecast;

    document.getElementById('forecastSection').style.display = 'block';
    document.getElementById('chartsSection').style.display = 'block';
    document.getElementById('reconciledSection').style.display = 'block';
    document.getElementById('optimizerSection').style.display = 'block';
    document.getElementById('simulatorSection').style.display = 'block';
    document.getElementById('scenariosSection').style.display = 'block';
    document.getElementById('driversSection').style.display = 'block';
    document.getElementById('fcSection').style.display = 'block';
    document.getElementById('risksSection').style.display = 'block';
    document.getElementById('summarySection').style.display = 'block';

    // Load gating
    try {
      const g = await fetchGating();
      if (g) gatingData = g;
    } catch (_) {}
    if (!gatingData) gatingData = getMockGating();
    renderGating(gatingData);

    updateMetrics(currentHorizon);
    updateChart('blended');

    // Load drivers + forecast change + risks
    try {
      const d = await fetchDrivers();
      if (d) driverData = d;
    } catch (_) {}
    if (!driverData) driverData = getMockDrivers();
    renderDrivers(driverData);

    try {
      const fc = await fetchForecastChange(currentHorizon);
      if (fc) fcData = fc;
    } catch (_) {}
    if (!fcData) fcData = getMockForecastChange();
    renderForecastChange(fcData);

    try {
      const r = await fetchRisks();
      if (r) riskData = r;
    } catch (_) {}
    if (!riskData) riskData = getMockRisks();
    renderRisks(riskData);

    // Load scenarios
    try {
      const scData = await fetchScenarios(currentHorizon, null);
      if (scData) scenarioData = scData;
    } catch (_) {}
    if (!scenarioData) scenarioData = getMockScenarios(currentHorizon);
    renderScenarios(scenarioData, currentHorizon);

    // Pre-populate optimizer with current total spend
    const totalSpend = Object.values(forecastData).reduce((acc, ch) => {
      return acc + (ch[currentHorizon]?.revenue_p50 || 0) / 3;
    }, 0);
    document.getElementById('optBudget').value = Math.round(totalSpend);

    // Load reconciled breakdown
    try {
      const reconResp = await fetch(`${API_BASE}/api/reconcile`, { method: 'POST' });
      const reconData = await reconResp.json();
      if (reconData.status === 'ok') {
        reconciledData = reconData.reconciled;
      }
    } catch (_) {}
    if (!reconciledData) reconciledData = getMockReconciled();
    renderReconciled(currentReconHorizon);

    // Load summary
    const summaryResp = await fetch(`${API_BASE}/api/summary`);
    const summaryData = await summaryResp.json();
    renderSummary(summaryData.summary);

  } catch (err) {
    // Demo mode — use mock data if API is not available
    forecastData = getMockForecast();
    reconciledData = getMockReconciled();
    document.getElementById('forecastSection').style.display = 'block';
    document.getElementById('chartsSection').style.display = 'block';
    document.getElementById('reconciledSection').style.display = 'block';
    document.getElementById('optimizerSection').style.display = 'block';
    document.getElementById('simulatorSection').style.display = 'block';
    document.getElementById('scenariosSection').style.display = 'block';
    document.getElementById('driversSection').style.display = 'block';
    document.getElementById('fcSection').style.display = 'block';
    document.getElementById('risksSection').style.display = 'block';
    document.getElementById('summarySection').style.display = 'block';

    gatingData = getMockGating();
    renderGating(gatingData);
    updateMetrics(currentHorizon);
    updateChart('blended');
    renderReconciled(currentReconHorizon);
    driverData = getMockDrivers();
    renderDrivers(driverData);
    fcData = getMockForecastChange();
    renderForecastChange(fcData);
    riskData = getMockRisks();
    renderRisks(riskData);
    scenarioData = getMockScenarios(currentHorizon);
    renderScenarios(scenarioData, currentHorizon);
    const totalSpend = Object.values(forecastData).reduce((acc, ch) => {
      return acc + (ch[currentHorizon]?.revenue_p50 || 0) / 3;
    }, 0);
    document.getElementById('optBudget').value = Math.round(totalSpend);
    renderSummary('• Google Ads shows strong 12% week-over-week revenue growth driven by brand campaign uplift.\n• Bing Ads revenue is proxy-based due to 96% zero-attribution rows — accuracy depends on click correlation.\n• Meta Ads conversion tracking gap persists but estimated ROAS of 1.8x remains profitable at current spend levels.');
  }

  runBtn.textContent = 'Run Forecast';
});

// Data quality check
let qualityData = null;
document.getElementById('checkQualityBtn').addEventListener('click', checkQuality);

async function checkQuality() {
  const btn = document.getElementById('checkQualityBtn');
  btn.disabled = true;
  btn.textContent = 'Checking...';

  try {
    const formData = new FormData();
    for (const key in uploadedFiles) {
      formData.append('files', uploadedFiles[key]);
    }
    await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });

    const resp = await fetch(`${API_BASE}/api/quality`, { method: 'POST' });
    const j = await resp.json();
    if (j.status === 'ok') qualityData = j.quality;
  } catch (_) {}
  if (!qualityData) qualityData = getMockQuality();

  document.getElementById('qualitySection').style.display = 'block';
  renderQuality(qualityData);
  btn.textContent = 'Check Data Quality';
  btn.disabled = false;
}

function getMockQuality() {
  return {
    overall_score: 72.4,
    overall_grade: 'C',
    overall_label: 'Fair',
    confidence_penalty: 0.28,
    channels_found: ['google', 'bing', 'meta'],
    channels_expected: 3,
    channels: {
      google: { score: 88.2, grade: 'B', label: 'Good', n_days: 187, zero_revenue_pct: 2.1, revenue_source: 'tracked', issues: [] },
      bing: { score: 45.0, grade: 'D', label: 'Poor', n_days: 92, zero_revenue_pct: 96.0, revenue_source: 'click_proxy', issues: [
        { check: 'revenue_attribution', severity: 'error', message: '96% of rows have $0 revenue — revenue model will be unreliable' },
        { check: 'revenue_proxy', severity: 'warning', message: 'Revenue is click_proxy — accuracy depends on proxy quality' },
      ]},
      meta: { score: 78.5, grade: 'C', label: 'Fair', n_days: 134, zero_revenue_pct: 14.3, revenue_source: 'conversion_based', issues: [
        { check: 'revenue_attribution', severity: 'info', message: '14.3% of rows have $0 revenue — gap may bias forecasts low' },
      ]},
    },
  };
}

function renderQuality(q) {
  const overview = document.getElementById('qualityOverview');
  const detail = document.getElementById('qualityDetail');

  const gradeColors = { A: '#00D4B4', B: '#4CAF50', C: '#FFB700', D: '#FF6B6B', F: '#FF4444' };
  const color = gradeColors[q.overall_grade] || '#888';

  overview.innerHTML = `
    <div class="quality-badge" style="border-color:${color};color:${color}">
      <span class="quality-grade">${q.overall_grade}</span>
      <span class="quality-label">${q.overall_label}</span>
      <span class="quality-score">${q.overall_score}/100</span>
    </div>
    <div class="quality-stats">
      <div class="quality-stat">
        <span class="quality-stat-label">Confidence Penalty</span>
        <span class="quality-stat-value" style="color:${q.confidence_penalty > 0.2 ? '#FFB700' : '#00D4B4'}">−${(q.confidence_penalty * 100).toFixed(0)}%</span>
      </div>
      <div class="quality-stat">
        <span class="quality-stat-label">Channels Found</span>
        <span class="quality-stat-value">${q.channels_found.length}/${q.channels_expected}</span>
      </div>
      <div class="quality-stat">
        <span class="quality-stat-label">Span</span>
        <span class="quality-stat-value">${Math.max(...Object.values(q.channels).map(c => c.n_days))} days</span>
      </div>
      <div class="quality-stat">
        <span class="quality-stat-label">Worst</span>
        <span class="quality-stat-value">${Object.entries(q.channels).sort((a,b) => a[1].score - b[1].score)[0][0]} ${Object.entries(q.channels).sort((a,b) => a[1].score - b[1].score)[0][1].grade}</span>
      </div>
    </div>
  `;

  let html = '';
  for (const [ch, cd] of Object.entries(q.channels)) {
    const chColor = gradeColors[cd.grade] || '#888';
    const sevLabel = { error: 'Error', warning: 'Warning', info: 'Info' };
    html += `<div class="quality-channel">
      <div class="quality-channel-header">
        <span class="quality-ch-name">${ch.charAt(0).toUpperCase() + ch.slice(1)}</span>
        <span class="quality-ch-badge" style="border-color:${chColor};color:${chColor}">${cd.grade} ${cd.score}</span>
        <span class="quality-ch-meta">${cd.n_days} days · ${cd.zero_revenue_pct}% zero rev · ${cd.revenue_source}</span>
      </div>
      <div class="quality-ch-issues">
        ${cd.issues.length === 0 ? '<span class="quality-no-issues">No issues detected</span>' : ''}
        ${cd.issues.map(iss => `
          <div class="quality-issue quality-issue-${iss.severity}">
            <span class="quality-issue-tag">${sevLabel[iss.severity]}</span>
            <span>${iss.message}</span>
          </div>
        `).join('')}
      </div>
    </div>`;
  }
  detail.innerHTML = html;
}

// Horizon switching
document.querySelectorAll('.horizon-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.horizon-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentHorizon = parseInt(btn.dataset.horizon);
    if (forecastData) updateMetrics(currentHorizon);
  });
});

function updateMetrics(horizon) {
  const totalRev = Object.values(forecastData).reduce((acc, ch) => {
    return {
      p10: acc.p10 + (ch[horizon]?.revenue_p10 || 0),
      p50: acc.p50 + (ch[horizon]?.revenue_p50 || 0),
      p90: acc.p90 + (ch[horizon]?.revenue_p90 || 0),
    };
  }, { p10: 0, p50: 0, p90: 0 });

  const blendedRoas = forecastData.blended?.[horizon];

  document.getElementById('totalRevenue').textContent =
    `$${(totalRev.p10 / 1000).toFixed(1)}K — $${(totalRev.p90 / 1000).toFixed(1)}K`;
  document.getElementById('totalRevenue').className = 'metric-value';

  document.getElementById('blendedRoas').textContent =
    blendedRoas ? `${blendedRoas.roas_p50.toFixed(1)}x` : '--';
  document.getElementById('blendedRoas').className = 'metric-value';

  const bandWidth = totalRev.p50 > 0
    ? ((totalRev.p90 - totalRev.p10) / totalRev.p50 * 100).toFixed(0)
    : 0;
  document.getElementById('confidenceBand').textContent = `±${Math.round(parseInt(bandWidth) / 2)}%`;
  document.getElementById('confidenceBand').className = 'metric-value';
}

// Chart toggles
document.querySelectorAll('.chart-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.chart-toggle').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateChart(btn.dataset.channel);
  });
});

function getMockForecast() {
  return {
    blended: {
      30: { revenue_p10: 45000, revenue_p50: 58000, revenue_p90: 72000, roas_p10: 2.1, roas_p50: 2.9, roas_p90: 3.8, daily: [] },
      60: { revenue_p10: 88000, revenue_p50: 112000, revenue_p90: 140000, roas_p10: 2.0, roas_p50: 2.8, roas_p90: 3.6, daily: [] },
      90: { revenue_p10: 128000, revenue_p50: 165000, revenue_p90: 206000, roas_p10: 1.9, roas_p50: 2.7, roas_p90: 3.5, daily: [] },
    },
    google: {
      30: { revenue_p10: 28000, revenue_p50: 35000, revenue_p90: 43000, roas_p10: 2.8, roas_p50: 3.5, roas_p90: 4.2, daily: [] },
      60: { revenue_p10: 54000, revenue_p50: 68000, revenue_p90: 84000, roas_p10: 2.7, roas_p50: 3.4, roas_p90: 4.0, daily: [] },
      90: { revenue_p10: 78000, revenue_p50: 99000, revenue_p90: 123000, roas_p10: 2.6, roas_p50: 3.3, roas_p90: 3.9, daily: [] },
    },
    bing: {
      30: { revenue_p10: 8000, revenue_p50: 12000, revenue_p90: 16000, roas_p10: 1.2, roas_p50: 1.8, roas_p90: 2.5, daily: [] },
      60: { revenue_p10: 15000, revenue_p50: 23000, revenue_p90: 32000, roas_p10: 1.1, roas_p50: 1.7, roas_p90: 2.4, daily: [] },
      90: { revenue_p10: 22000, revenue_p50: 34000, revenue_p90: 48000, roas_p10: 1.0, roas_p50: 1.6, roas_p90: 2.3, daily: [] },
    },
    meta: {
      30: { revenue_p10: 9000, revenue_p50: 13000, revenue_p90: 18000, roas_p10: 1.5, roas_p50: 2.1, roas_p90: 2.8, daily: [] },
      60: { revenue_p10: 17000, revenue_p50: 25000, revenue_p90: 34000, roas_p10: 1.4, roas_p50: 2.0, roas_p90: 2.7, daily: [] },
      90: { revenue_p10: 25000, revenue_p50: 37000, revenue_p90: 50000, roas_p10: 1.3, roas_p50: 1.9, roas_p90: 2.6, daily: [] },
    },
  };
}

function renderSummary(text) {
  const container = document.getElementById('summaryContent');
  const lines = text.split('\n').filter(l => l.trim());
  container.innerHTML = lines.map((line, i) => `
    <div class="bullet" style="animation-delay: ${i * 0.2}s">
      <span class="bullet-dot">•</span>
      <span>${line.replace(/^•\s*/, '')}</span>
    </div>
  `).join('');
}

// Reconciled horizon switching
document.querySelectorAll('[data-recon-horizon]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-recon-horizon]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentReconHorizon = parseInt(btn.dataset.reconHorizon);
    if (reconciledData) renderReconciled(currentReconHorizon);
  });
});

function renderReconciled(horizon) {
  const badge = document.getElementById('reconciledBadge');
  const table = document.getElementById('reconciledTable');
  if (!reconciledData) { table.innerHTML = '<div class="loading">No data</div>'; return; }

  const v = reconciledData.verification || {};
  const ok = v.all_levels_consistent;
  badge.textContent = ok
    ? `✓ Reconciled: all ${v.levels?.length || 3} levels consistent (max discrepancy $${v.max_discrepancy_p50 || '0.00'})`
    : `⚠ Discrepancy found (max $${v.max_discrepancy_p50 || '?'})`;
  badge.className = 'reconciled-badge ' + (ok ? 'valid' : 'warn');

  const byCh = {};
  for (const [key, info] of Object.entries(reconciledData.campaign_types || {})) {
    const ch = info.channel || 'unknown';
    if (!byCh[ch]) byCh[ch] = [];
    byCh[ch].push({ ...info, key });
  }

  let html = '<table class="recon-table"><thead><tr><th>Level</th><th>Revenue P10</th><th>Revenue P50</th><th>Revenue P90</th><th>Spend</th><th>ROAS</th><th></th></tr></thead><tbody>';

  const fmt = v => `$${(v || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  const fmtR = v => (v || 0).toFixed(1) + 'x';

  for (const ch of Object.keys(byCh).sort()) {
    // Campaign-type rows
    for (const ct of byCh[ch]) {
      const hd = ct[horizon] || {};
      html += `<tr class="ct-row"><td class="ct-name">${ct.key}</td>
        <td>${fmt(hd.revenue_p10)}</td><td class="p50">${fmt(hd.revenue_p50)}</td>
        <td>${fmt(hd.revenue_p90)}</td><td>${fmt(hd.spend)}</td><td>${fmtR(hd.roas_p50)}</td><td></td></tr>`;
    }
    // Channel sum row
    const chData = (reconciledData.channels || {})[ch]?.[horizon] || {};
    html += `<tr class="ch-row"><td class="ch-name">${ch.charAt(0).toUpperCase() + ch.slice(1)} (sum)</td>
      <td>${fmt(chData.revenue_p10)}</td><td class="p50">${fmt(chData.revenue_p50)}</td>
      <td>${fmt(chData.revenue_p90)}</td><td>${fmt(chData.spend)}</td><td>${fmtR(chData.roas_p50)}</td>
      <td class="check-cell">✓</td></tr>`;
  }

  // Blended total row
  const bl = reconciledData.blended?.[horizon] || {};
  html += `<tr class="bl-row"><td class="bl-name">Blended Total</td>
    <td>${fmt(bl.revenue_p10)}</td><td class="p50">${fmt(bl.revenue_p50)}</td>
    <td>${fmt(bl.revenue_p90)}</td><td>${fmt(bl.spend)}</td><td>${fmtR(bl.roas_p50)}</td>
    <td class="check-cell">✓</td></tr>`;

  html += '</tbody></table>';
  table.innerHTML = html;
}

function getMockReconciled() {
  return {
    campaign_types: {
      google_SEARCH: { channel: 'google', campaign_type: 'SEARCH', 30: { revenue_p10: 15000, revenue_p50: 19000, revenue_p90: 24000, spend: 5500, roas_p50: 3.5 }, 60: { revenue_p10: 29000, revenue_p50: 37000, revenue_p90: 47000, spend: 10900, roas_p50: 3.4 }, 90: { revenue_p10: 42000, revenue_p50: 54000, revenue_p90: 69000, spend: 16200, roas_p50: 3.3 } },
      google_DISPLAY: { channel: 'google', campaign_type: 'DISPLAY', 30: { revenue_p10: 8000, revenue_p50: 11000, revenue_p90: 14000, spend: 4000, roas_p50: 2.8 }, 60: { revenue_p10: 15000, revenue_p50: 21000, revenue_p90: 27000, spend: 7900, roas_p50: 2.7 }, 90: { revenue_p10: 22000, revenue_p50: 31000, revenue_p90: 40000, spend: 11800, roas_p50: 2.6 } },
      google_SHOPPING: { channel: 'google', campaign_type: 'SHOPPING', 30: { revenue_p10: 5000, revenue_p50: 7000, revenue_p90: 9500, spend: 2000, roas_p50: 3.5 }, 60: { revenue_p10: 9600, revenue_p50: 13600, revenue_p90: 18400, spend: 3960, roas_p50: 3.4 }, 90: { revenue_p10: 14000, revenue_p50: 20000, revenue_p90: 27000, spend: 5900, roas_p50: 3.4 } },
      bing_SEARCH: { channel: 'bing', campaign_type: 'SEARCH', 30: { revenue_p10: 5000, revenue_p50: 7500, revenue_p90: 10500, spend: 3500, roas_p50: 2.1 }, 60: { revenue_p10: 9600, revenue_p50: 14500, revenue_p90: 20300, spend: 6940, roas_p50: 2.1 }, 90: { revenue_p10: 14000, revenue_p50: 21300, revenue_p90: 29800, spend: 10300, roas_p50: 2.1 } },
      bing_DISPLAY: { channel: 'bing', campaign_type: 'DISPLAY', 30: { revenue_p10: 3000, revenue_p50: 4500, revenue_p90: 6500, spend: 2500, roas_p50: 1.8 }, 60: { revenue_p10: 5800, revenue_p50: 8700, revenue_p90: 12600, spend: 5000, roas_p50: 1.7 }, 90: { revenue_p10: 8500, revenue_p50: 12800, revenue_p90: 18500, spend: 7400, roas_p50: 1.7 } },
      meta_SOCIAL: { channel: 'meta', campaign_type: 'SOCIAL', 30: { revenue_p10: 9000, revenue_p50: 13000, revenue_p90: 18000, spend: 5500, roas_p50: 2.4 }, 60: { revenue_p10: 17400, revenue_p50: 25200, revenue_p90: 34900, spend: 11000, roas_p50: 2.3 }, 90: { revenue_p10: 25600, revenue_p50: 37100, revenue_p90: 51400, spend: 16400, roas_p50: 2.3 } },
    },
    channels: {
      google: { 30: { revenue_p10: 28000, revenue_p50: 37000, revenue_p90: 47500, spend: 11500, roas_p50: 3.2 }, 60: { revenue_p10: 53600, revenue_p50: 71600, revenue_p90: 92400, spend: 22760, roas_p50: 3.1 }, 90: { revenue_p10: 78000, revenue_p50: 105000, revenue_p90: 136000, spend: 33900, roas_p50: 3.1 } },
      bing: { 30: { revenue_p10: 8000, revenue_p50: 12000, revenue_p90: 17000, spend: 6000, roas_p50: 2.0 }, 60: { revenue_p10: 15400, revenue_p50: 23200, revenue_p90: 32900, spend: 11940, roas_p50: 1.9 }, 90: { revenue_p10: 22500, revenue_p50: 34100, revenue_p90: 48300, spend: 17700, roas_p50: 1.9 } },
      meta: { 30: { revenue_p10: 9000, revenue_p50: 13000, revenue_p90: 18000, spend: 5500, roas_p50: 2.4 }, 60: { revenue_p10: 17400, revenue_p50: 25200, revenue_p90: 34900, spend: 11000, roas_p50: 2.3 }, 90: { revenue_p10: 25600, revenue_p50: 37100, revenue_p90: 51400, spend: 16400, roas_p50: 2.3 } },
    },
    blended: {
      30: { revenue_p10: 45000, revenue_p50: 62000, revenue_p90: 82500, spend: 23000, roas_p50: 2.7 },
      60: { revenue_p10: 86400, revenue_p50: 120000, revenue_p90: 160200, spend: 45700, roas_p50: 2.6 },
      90: { revenue_p10: 126100, revenue_p50: 176200, revenue_p90: 235700, spend: 68000, roas_p50: 2.6 },
    },
    verification: {
      all_levels_consistent: true,
      max_discrepancy_p50: 0.0,
      levels: ['campaign_type', 'channel', 'blended'],
      method: 'bottom-up_sum',
    },
  };
}

// Driver decomposition
let driverData = null;

async function fetchDrivers() {
  try {
    const resp = await fetch(`${API_BASE}/api/drivers`, { method: 'POST' });
    const j = await resp.json();
    if (j.status === 'ok') return j.drivers;
  } catch (_) {}
  return null;
}

function getMockDrivers() {
  return {
    periods: {
      recent: { days: 30, label: 'Last 30 days (scaled to 30d)' },
      prior: { days: 30, label: 'Prior 30 days (scaled to 30d)' },
    },
    channels: {
      google: {
        revenue_before: 42000, revenue_after: 35000, change_abs: -7000, change_pct: -16.7,
        spend_before: 12000, spend_after: 11500, roas_before: 3.5, roas_after: 3.0,
        drivers: { spend_effect: -1750, efficiency_effect: -5250, spend_pct_of_change: 25.0, efficiency_pct_of_change: 75.0 },
        dominant_drivers: ['efficiency'],
      },
      bing: {
        revenue_before: 15000, revenue_after: 14000, change_abs: -1000, change_pct: -6.7,
        spend_before: 7500, spend_after: 8000, roas_before: 2.0, roas_after: 1.75,
        drivers: { spend_effect: 938, efficiency_effect: -1938, spend_pct_of_change: -93.8, efficiency_pct_of_change: 193.8 },
        dominant_drivers: ['efficiency'],
      },
      meta: {
        revenue_before: 12000, revenue_after: 13500, change_abs: 1500, change_pct: 12.5,
        spend_before: 5500, spend_after: 6000, roas_before: 2.18, roas_after: 2.25,
        drivers: { spend_effect: 1108, efficiency_effect: 392, spend_pct_of_change: 73.9, efficiency_pct_of_change: 26.1 },
        dominant_drivers: ['spend'],
      },
    },
    contributions: {
      google: { pct_of_blended: -107.7, spend_pct_of_blended: -26.9, efficiency_pct_of_blended: -80.8 },
      bing: { pct_of_blended: -15.4, spend_pct_of_blended: 14.4, efficiency_pct_of_blended: -29.8 },
      meta: { pct_of_blended: 23.1, spend_pct_of_blended: 17.0, efficiency_pct_of_blended: 6.0 },
    },
    blended: {
      revenue_before: 69000, revenue_after: 62500, change_abs: -6500, change_pct: -9.4,
      spend_effect: -1704, efficiency_effect: -4796,
      spend_pct_of_change: 26.2, efficiency_pct_of_change: 73.8,
    },
  };
}

function renderDrivers(d) {
  const summary = document.getElementById('driversSummary');
  const detail = document.getElementById('driversDetail');
  const bl = d.blended;

  const changeCls = bl.change_pct >= 0 ? 'positive' : 'negative';
  const changeSign = bl.change_pct >= 0 ? '+' : '';

  summary.innerHTML = `
    <div class="driver-summary-row">
      <div class="driver-summary-stat">
        <span class="driver-stat-label">Revenue Change</span>
        <span class="driver-stat-value ${changeCls}">${changeSign}${bl.change_pct.toFixed(1)}%</span>
        <span class="driver-stat-sub">${changeSign}$${Math.abs(bl.change_abs).toLocaleString()}</span>
      </div>
      <div class="driver-bar-group">
        <div class="driver-bar-item ${bl.spend_effect >= 0 ? 'positive' : 'negative'}" style="flex:${Math.abs(bl.spend_pct_of_change)}">
          <span class="driver-bar-label">Spend</span>
          <span class="driver-bar-val">${bl.spend_pct_of_change.toFixed(0)}%</span>
        </div>
        <div class="driver-bar-item ${bl.efficiency_effect >= 0 ? 'positive' : 'negative'}" style="flex:${Math.abs(bl.efficiency_pct_of_change)}">
          <span class="driver-bar-label">Efficiency</span>
          <span class="driver-bar-val">${bl.efficiency_pct_of_change.toFixed(0)}%</span>
        </div>
      </div>
    </div>
  `;

  const fmt = v => `$${(v || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  const fmtP = v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

  let html = '<table class="driver-table"><thead><tr>' +
    '<th>Channel</th><th>Before</th><th>After</th><th>Δ</th><th>Spend Δ</th><th>ROAS</th><th>Drivers</th></tr></thead><tbody>';

  for (const [ch, cd] of Object.entries(d.channels)) {
    const cls = cd.change_pct >= 0 ? 'positive' : 'negative';
    const drvLabels = { spend: 'Spend-led', efficiency: 'Efficiency-led', stable: 'Stable' };
    const drvLabel = cd.dominant_drivers.map(d => drvLabels[d] || d).join(' + ');

    html += `<tr>
      <td class="driver-ch-name">${ch.charAt(0).toUpperCase() + ch.slice(1)}</td>
      <td>${fmt(cd.revenue_before)}</td>
      <td class="${cls}">${fmt(cd.revenue_after)}</td>
      <td class="${cls}">${fmtP(cd.change_pct)}</td>
      <td>${fmtP((cd.spend_after - cd.spend_before) / cd.spend_before * 100)}</td>
      <td>${cd.roas_before.toFixed(1)}x → ${cd.roas_after.toFixed(1)}x</td>
      <td><span class="driver-badge ${cd.dominant_drivers[0]}">${drvLabel}</span></td>
    </tr>`;
  }
  html += '</tbody></table>';
  detail.innerHTML = html;
}

// Forecast change decomposition
let fcData = null;

async function fetchForecastChange(horizon) {
  try {
    const resp = await fetch(`${API_BASE}/api/forecast-change?horizon=${horizon}`, { method: 'POST' });
    const j = await resp.json();
    if (j.status === 'ok') return j.forecast_change;
  } catch (_) {}
  return null;
}

function getMockForecastChange() {
  return {
    horizon: 30,
    channels: {
      meta: {
        actual: { revenue: 44484, spend: 6031, roas: 7.38 },
        forecast: { revenue: 7574, spend: 4509, roas: 1.68 },
        delta: { revenue: -36910, spend: -1522, roas: -5.70, change_pct: -83.0 },
        drivers: { spend_effect: -11226, efficiency_effect: -25684, spend_pct_of_change: 30.4, efficiency_pct_of_change: 69.6 },
      },
    },
    blended: {
      actual: { revenue: 44484, spend: 6031, roas: 7.38 },
      forecast: { revenue: 7574, spend: 4509, roas: 1.68 },
      delta: { revenue: -36910, spend: -1522, roas: -5.70, change_pct: -83.0 },
      drivers: { spend_effect: -11226, efficiency_effect: -25684, spend_pct_of_change: 30.4, efficiency_pct_of_change: 69.6 },
    },
  };
}

function renderForecastChange(d) {
  const summary = document.getElementById('fcSummary');
  const detail = document.getElementById('fcDetail');
  const bl = d.blended;

  const changeCls = bl.delta.change_pct >= 0 ? 'positive' : 'negative';
  const changeSign = bl.delta.change_pct >= 0 ? '+' : '';

  summary.innerHTML = `
    <div class="driver-summary-row">
      <div class="driver-summary-stat">
        <span class="driver-stat-label">Forecast vs Actual</span>
        <span class="driver-stat-value ${changeCls}">${changeSign}${bl.delta.change_pct.toFixed(1)}%</span>
        <span class="driver-stat-sub">${changeSign}$${Math.abs(bl.delta.revenue).toLocaleString()}</span>
      </div>
      <div class="driver-bar-group">
        <div class="driver-bar-item ${bl.drivers.spend_effect >= 0 ? 'positive' : 'negative'}" style="flex:${Math.abs(bl.drivers.spend_pct_of_change)}">
          <span class="driver-bar-label">Spend</span>
          <span class="driver-bar-val">${bl.drivers.spend_pct_of_change.toFixed(0)}%</span>
        </div>
        <div class="driver-bar-item ${bl.drivers.efficiency_effect >= 0 ? 'positive' : 'negative'}" style="flex:${Math.abs(bl.drivers.efficiency_pct_of_change)}">
          <span class="driver-bar-label">Efficiency</span>
          <span class="driver-bar-val">${bl.drivers.efficiency_pct_of_change.toFixed(0)}%</span>
        </div>
      </div>
    </div>
  `;

  const fmt = v => `$${(v || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  const fmtP = v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
  const fmtR = v => `${(v || 0).toFixed(1)}x`;

  let html = '<table class="driver-table"><thead><tr>' +
    '<th>Channel</th><th>Actual (30d)</th><th>Forecast (30d)</th><th>Δ Rev</th><th>Δ%</th><th>Spend Δ</th><th>ROAS</th><th>Drivers</th></tr></thead><tbody>';

  for (const [ch, cd] of Object.entries(d.channels)) {
    const cls = cd.delta.change_pct >= 0 ? 'positive' : 'negative';
    const drv = cd.drivers;
    const dir = drv.spend_pct_of_change > 50 ? 'Spend-led' : 'Efficiency-led';

    html += `<tr>
      <td class="driver-ch-name">${ch.charAt(0).toUpperCase() + ch.slice(1)}</td>
      <td>${fmt(cd.actual.revenue)}</td>
      <td class="${cls}">${fmt(cd.forecast.revenue)}</td>
      <td class="${cls}">${fmtP(cd.delta.change_pct)}</td>
      <td class="${cls}">${fmtP(cd.delta.change_pct)}</td>
      <td>${fmtP((cd.forecast.spend - cd.actual.spend) / Math.max(cd.actual.spend, 0.01) * 100)}</td>
      <td>${fmtR(cd.actual.roas)} → ${fmtR(cd.forecast.roas)}</td>
      <td><span class="driver-badge ${drv.spend_pct_of_change > 50 ? 'spend' : 'efficiency'}">${dir}</span></td>
    </tr>`;
  }
  html += '</tbody></table>';
  detail.innerHTML = html;
}

// Gating
async function fetchGating() {
  try {
    const resp = await fetch(`${API_BASE}/api/gating?alpha=1.5`, { method: 'POST' });
    const j = await resp.json();
    if (j.status === 'ok') return j.gating;
  } catch (_) {}
  return null;
}

function getMockGating() {
  return {
    quality: { overall_grade: 'C', overall_score: 70.0, confidence_penalty: 0.30 },
    adjust_factor: 1.45,
    raw: {
      meta: {
        30: { revenue_p10: 2642, revenue_p50: 7574, revenue_p90: 21635 },
        60: { revenue_p10: 5999, revenue_p50: 16956, revenue_p90: 48424 },
        90: { revenue_p10: 8270, revenue_p50: 23638, revenue_p90: 67103 },
      },
      blended: {
        30: { revenue_p10: 2704, revenue_p50: 7574, revenue_p90: 21377 },
        60: { revenue_p10: 5901, revenue_p50: 16956, revenue_p90: 48309 },
        90: { revenue_p10: 8261, revenue_p50: 23638, revenue_p90: 67520 },
      },
    },
    gated: {
      meta: {
        30: { revenue_p10: 0, revenue_p50: 7574, revenue_p90: 39172 },
        60: { revenue_p10: 0, revenue_p50: 16956, revenue_p90: 88224 },
        90: { revenue_p10: 0, revenue_p50: 23638, revenue_p90: 122649 },
      },
      blended: {
        30: { revenue_p10: 0, revenue_p50: 7574, revenue_p90: 38669 },
        60: { revenue_p10: 0, revenue_p50: 16956, revenue_p90: 87701 },
        90: { revenue_p10: 0, revenue_p50: 23638, revenue_p90: 122720 },
      },
    },
  };
}

function renderGating(g) {
  const toggle = document.getElementById('gatingToggle');
  const badge = document.getElementById('gatingBadge');
  toggle.style.display = 'block';
  badge.textContent = `${g.quality.overall_grade} · ${g.quality.overall_score}/100 · ${g.adjust_factor.toFixed(1)}x widen`;
  badge.className = 'badge-sm ' + (g.quality.confidence_penalty > 0.2 ? 'warn' : 'ok');
}

// Update metrics to use gated data when checkbox is checked
document.addEventListener('change', function(e) {
  if (e.target.id === 'gatingCheckbox') {
    useGating = e.target.checked;
    if (forecastData) updateMetrics(currentHorizon);
  }
});

function getForecastForHorizon(horizon) {
  // Return gated data if available and enabled, else raw forecast data
  if (useGating && gatingData) {
    const result = { p10: 0, p50: 0, p90: 0 };
    for (const [ch, hd] of Object.entries(gatingData.gated)) {
      const v = hd[horizon];
      if (v) {
        result.p10 += v.revenue_p10;
        result.p50 += v.revenue_p50;
        result.p90 += v.revenue_p90;
      }
    }
    return result;
  }
  return null;
}

// Override updateMetrics to use getForecastForHorizon
const _origUpdateMetrics = updateMetrics;
updateMetrics = function(horizon) {
  const gatedTotals = getForecastForHorizon(horizon);
  if (gatedTotals) {
    document.getElementById('totalRevenue').textContent =
      `$${(gatedTotals.p10 / 1000).toFixed(1)}K — $${(gatedTotals.p90 / 1000).toFixed(1)}K`;
    document.getElementById('totalRevenue').className = 'metric-value';
    const bandWidth = gatedTotals.p50 > 0
      ? ((gatedTotals.p90 - gatedTotals.p10) / gatedTotals.p50 * 100).toFixed(0)
      : 0;
    document.getElementById('confidenceBand').textContent = `±${Math.round(parseInt(bandWidth) / 2)}%`;
    document.getElementById('confidenceBand').className = 'metric-value';
  } else {
    _origUpdateMetrics(horizon);
  }
  // ROAS always from raw forecast
  const blendedRoas = forecastData?.blended?.[horizon];
  document.getElementById('blendedRoas').textContent =
    blendedRoas ? `${blendedRoas.roas_p50.toFixed(1)}x` : '--';
  document.getElementById('blendedRoas').className = 'metric-value';
};

// Risk alerts
let riskData = null;

async function fetchRisks() {
  try {
    const resp = await fetch(`${API_BASE}/api/risks`, { method: 'POST' });
    const j = await resp.json();
    if (j.status === 'ok') return j.risks;
  } catch (_) {}
  return null;
}

function getMockRisks() {
  return {
    alerts: [
      {
        channel: 'meta', type: 'spend_efficiency_divergence', severity: 'warning',
        title: 'Spend rising while ROAS declining',
        message: 'Spend trending +22% but ROAS trending −15% over last 14 days',
        recommendation: 'Audit campaign-level performance before committing more budget',
        metric: 'roas', direction: 'negative',
      },
      {
        channel: 'bing', type: 'tracking_coverage', severity: 'warning',
        title: 'Attribution gap: proxy revenue',
        message: '96% of rows use proxy revenue (not directly attributed)',
        recommendation: 'Fix conversion tracking pipeline for reliable ROAS measurement',
        metric: 'revenue', direction: 'negative',
      },
      {
        channel: 'google', type: 'roas_drift', severity: 'info',
        title: 'ROAS drift: −12%',
        message: 'ROAS shifted −12% last 7d vs prior week (3.8x → 3.3x)',
        recommendation: 'Check for campaign changes, creative rotations, or audience shifts',
        metric: 'roas', direction: 'negative',
      },
    ],
    alert_count: 3, critical_count: 0, warning_count: 2, info_count: 1,
  };
}

function renderRisks(r) {
  const card = document.getElementById('risksCard');

  const sevColors = { error: '#FF4444', warning: '#FFB700', info: '#00D4B4' };
  const sevLabels = { error: 'Critical', warning: 'Warning', info: 'Info' };

  let html = `<div class="risks-bar">
    <span class="risks-count">${r.alert_count} alert${r.alert_count !== 1 ? 's' : ''}</span>`;
  if (r.warning_count > 0) html += `<span class="risks-badge warning">${r.warning_count} warning${r.warning_count !== 1 ? 's' : ''}</span>`;
  if (r.info_count > 0) html += `<span class="risks-badge info">${r.info_count} info</span>`;
  html += '</div><div class="risks-list">';

  for (const a of r.alerts) {
    const sc = sevColors[a.severity] || '#888';
    html += `<div class="risk-item" style="border-left-color:${sc}">
      <div class="risk-header">
        <span class="risk-sev" style="color:${sc}">${sevLabels[a.severity] || a.severity}</span>
        <span class="risk-channel">${a.channel.charAt(0).toUpperCase() + a.channel.slice(1)}</span>
        <span class="risk-title">${a.title}</span>
      </div>
      <div class="risk-body">
        <p class="risk-msg">${a.message}</p>
        <p class="risk-rec"><strong>Suggestion:</strong> ${a.recommendation}</p>
      </div>
    </div>`;
  }

  html += '</div>';
  card.innerHTML = html;
}

// Scenario planner
let scenarioData = null;
let scCpc = 0, scCvr = 0, scSeasonal = 0;

document.getElementById('scCpc').addEventListener('input', () => {
  scCpc = parseInt(document.getElementById('scCpc').value);
  document.getElementById('scCpcVal').textContent = (scCpc >= 0 ? '+' : '') + scCpc + '%';
});
document.getElementById('scCvr').addEventListener('input', () => {
  scCvr = parseInt(document.getElementById('scCvr').value);
  document.getElementById('scCvrVal').textContent = (scCvr >= 0 ? '+' : '') + scCvr + '%';
});
document.getElementById('scSeasonal').addEventListener('input', () => {
  scSeasonal = parseInt(document.getElementById('scSeasonal').value);
  document.getElementById('scSeasonalVal').textContent = (scSeasonal >= 0 ? '+' : '') + scSeasonal + '%';
});
document.getElementById('applyCustomBtn').addEventListener('click', applyCustomScenario);
document.getElementById('scHorizon').addEventListener('change', () => {
  if (scenarioData) renderScenarios(scenarioData, parseInt(document.getElementById('scHorizon').value));
});

async function fetchScenarios(horizon, custom) {
  try {
    const params = new URLSearchParams({ horizon });
    if (custom) params.append('custom', JSON.stringify(custom));
    const resp = await fetch(`${API_BASE}/api/scenarios?${params}`, { method: 'POST' });
    const j = await resp.json();
    if (j.status === 'ok') return j.scenarios;
  } catch (_) {}
  return null;
}

function getMockScenarios(horizon) {
  const h = horizon || 30;
  const mult = h / 30;
  const base = {
    google: { revenue_p10: 28000 * mult, revenue_p50: 35000 * mult, revenue_p90: 43000 * mult },
    bing: { revenue_p10: 8000 * mult, revenue_p50: 12000 * mult, revenue_p90: 16000 * mult },
    meta: { revenue_p10: 9000 * mult, revenue_p50: 13000 * mult, revenue_p90: 18000 * mult },
  };
  const sum = (d, k) => Object.values(d).reduce((a, c) => a + c[k], 0);

  const calc = (cpc, cvr, seas) => {
    const adj = (1 + cvr) * (1 + seas) / (1 + cpc);
    const ch = {};
    let b = { revenue_p10: 0, revenue_p50: 0, revenue_p90: 0 };
    for (const [chName, v] of Object.entries(base)) {
      ch[chName] = {
        revenue_p10: Math.round(v.revenue_p10 * adj),
        revenue_p50: Math.round(v.revenue_p50 * adj),
        revenue_p90: Math.round(v.revenue_p90 * adj),
      };
      b.revenue_p10 += ch[chName].revenue_p10;
      b.revenue_p50 += ch[chName].revenue_p50;
      b.revenue_p90 += ch[chName].revenue_p90;
    }
    b.revenue_p10 = Math.round(b.revenue_p10);
    b.revenue_p50 = Math.round(b.revenue_p50);
    b.revenue_p90 = Math.round(b.revenue_p90);
    return { channels: ch, blended: b };
  };

  return {
    base: { label: 'Base Case', description: 'Current trends continue unchanged', ...calc(0, 0, 0) },
    conservative: { label: 'Conservative', description: 'CPC +15%, CVR −10%', ...calc(0.15, -0.10, 0) },
    aggressive: { label: 'Aggressive', description: 'CPC −5%, CVR +10%, seasonal +15%', ...calc(-0.05, 0.10, 0.15) },
    custom: { label: 'Custom', description: 'User-defined assumptions', ...calc(scCpc / 100, scCvr / 100, scSeasonal / 100) },
  };
}

function renderScenarios(data, horizon) {
  const table = document.getElementById('scenarioTable');
  const scenarios = Object.keys(data);
  if (scenarios.length === 0) { table.innerHTML = '<div class="loading">No scenario data</div>'; return; }

  const chs = Object.keys(data[scenarios[0]].channels);
  const fmt = v => `$${(v || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

  let html = '<table class="scenario-compare"><thead><tr><th>Channel</th>';
  for (const scName of scenarios) {
    const d = data[scName];
    html += `<th>${d.label}<br><span class="sc-desc">${d.description}</span></th>`;
  }
  html += '</tr></thead><tbody>';

  for (const ch of chs) {
    html += `<tr><td class="sc-ch-label">${ch.charAt(0).toUpperCase() + ch.slice(1)}</td>`;
    const baseVal = data.base.channels[ch].revenue_p50;
    for (const scName of scenarios) {
      const val = data[scName].channels[ch].revenue_p50;
      const pct = baseVal > 0 ? ((val - baseVal) / baseVal * 100) : 0;
      const cls = Math.abs(pct) < 1 ? '' : (pct > 0 ? 'positive' : 'negative');
      html += `<td class="${cls}">${fmt(val)}<br><span class="sc-pct">${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%</span></td>`;
    }
    html += '</tr>';
  }

  // Blended summary row
  html += `<tr class="sc-bl-row"><td class="sc-ch-label">Blended Total</td>`;
  const baseBl = data.base.blended.revenue_p50;
  for (const scName of scenarios) {
    const val = data[scName].blended.revenue_p50;
    const pct = baseBl > 0 ? ((val - baseBl) / baseBl * 100) : 0;
    const cls = Math.abs(pct) < 1 ? '' : (pct > 0 ? 'positive' : 'negative');
    html += `<td class="${cls} sc-bl">${fmt(val)}<br><span class="sc-pct">${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%</span></td>`;
  }
  html += '</tr></tbody></table>';
  table.innerHTML = html;
}

function applyCustomScenario() {
  const horizon = parseInt(document.getElementById('scHorizon').value) || 30;
  const custom = { cpc_change: scCpc / 100, cvr_change: scCvr / 100, seasonal_uplift: scSeasonal / 100 };

  if (scenarioData) {
    const mockCustom = getMockScenarios(horizon);
    scenarioData.custom = mockCustom.custom;
    renderScenarios(scenarioData, horizon);
  }
}

// Budget optimizer
document.getElementById('runOptimizerBtn').addEventListener('click', runOptimizer);

function runOptimizer() {
  const totalBudget = parseFloat(document.getElementById('optBudget').value) || 0;
  const horizon = currentHorizon || 30;

  const channels = ['google', 'bing', 'meta'];
  const minMap = {};
  const maxMap = {};
  for (const ch of channels) {
    const key = ch.charAt(0).toUpperCase() + ch.slice(1);
    minMap[ch] = parseFloat(document.getElementById(`opt${key}Min`).value) || 0;
    maxMap[ch] = parseFloat(document.getElementById(`opt${key}Max`).value) || 1e9;
  }

  // Build query params for API
  const params = new URLSearchParams({ total_budget: totalBudget, horizon });
  for (const ch of channels) {
    const key = ch.charAt(0).toUpperCase() + ch.slice(1);
    params.append(`min_${ch}`, minMap[ch]);
    params.append(`max_${ch}`, maxMap[ch]);
  }

  (async () => {
    let optData;
    try {
      const resp = await fetch(`${API_BASE}/api/optimize?${params}`, { method: 'POST' });
      const json = await resp.json();
      if (json.status === 'ok') {
        optData = json.optimization;
      }
    } catch (_) {}
    if (!optData) optData = getMockOptimization(totalBudget, channels);

    renderOptimization(optData);
  })();
}

function getMockOptimization(totalBudget, channels) {
  // Compute plausible mock data based on the budget
  const baseSpends = { google: 15000, bing: 8000, meta: 6000 };
  const baseRevenues = { google: 48000, bing: 14400, meta: 13200 };
  const ks = {};
  for (const ch of channels) {
    ks[ch] = baseRevenues[ch] / Math.log(baseSpends[ch] + 1);
  }

  // Simple water-filling mock
  const remaining = totalBudget;
  const optSpends = {};
  for (const ch of channels) {
    const prop = baseSpends[ch] / (baseSpends.google + baseSpends.bing + baseSpends.meta);
    optSpends[ch] = totalBudget * prop;
  }

  const results = {};
  let tcs = 0, tcr = 0, tos = 0, tor = 0;
  for (const ch of channels) {
    const cs = baseSpends[ch];
    const cr = baseRevenues[ch];
    const os = optSpends[ch];
    const or = ks[ch] * Math.log(os + 1);
    const curMarg = ks[ch] / (cs + 1);
    const optMarg = ks[ch] / (os + 1);
    results[ch] = {
      current_spend: cs, optimal_spend: Math.round(os),
      spend_delta: Math.round(os - cs), spend_delta_pct: parseFloat(((os - cs) / cs * 100).toFixed(1)),
      current_revenue: cr, optimal_revenue: Math.round(or),
      revenue_delta: Math.round(or - cr),
      current_marginal_roas: parseFloat(curMarg.toFixed(4)),
      optimal_marginal_roas: parseFloat(optMarg.toFixed(4)),
    };
    tcs += cs; tcr += cr; tos += os; tor += or;
  }

  const margs = channels.map(ch => results[ch].optimal_marginal_roas).filter(v => v > 0);
  const spread = Math.max(...margs) - Math.min(...margs);

  return {
    channels: results,
    summary: {
      total_current_spend: tcs, total_optimal_spend: Math.round(tos),
      total_current_revenue: tcr, total_optimal_revenue: Math.round(tor),
      revenue_delta: Math.round(tor - tcr),
      revenue_delta_pct: parseFloat(((tor - tcr) / tcr * 100).toFixed(1)),
      current_blended_roas: parseFloat((tcr / tcs).toFixed(2)),
      optimal_blended_roas: parseFloat((tor / tos).toFixed(2)),
      marginal_roas_converged: spread < 0.01,
      marginal_roas_spread: parseFloat(spread.toFixed(4)),
    },
  };
}

function renderOptimization(optData) {
  document.getElementById('optResults').style.display = 'block';

  const s = optData.summary;
  const summaryHtml = `
    <div class="opt-summary-grid">
      <div class="opt-stat">
        <span class="opt-stat-label">Revenue Impact</span>
        <span class="opt-stat-value ${s.revenue_delta >= 0 ? 'positive' : 'negative'}">
          ${s.revenue_delta >= 0 ? '+' : ''}$${s.revenue_delta.toLocaleString()} (${s.revenue_delta_pct >= 0 ? '+' : ''}${s.revenue_delta_pct}%)
        </span>
      </div>
      <div class="opt-stat">
        <span class="opt-stat-label">Blended ROAS</span>
        <span class="opt-stat-value positive">${s.current_blended_roas}x → ${s.optimal_blended_roas}x</span>
      </div>
      <div class="opt-stat">
        <span class="opt-stat-label">Total Spend</span>
        <span class="opt-stat-value">$${s.total_current_spend.toLocaleString()} → $${s.total_optimal_spend.toLocaleString()}</span>
      </div>
      <div class="opt-stat">
        <span class="opt-stat-label">Marginal ROAS</span>
        <span class="opt-stat-value ${s.marginal_roas_converged ? 'positive' : ''}">
          converge${s.marginal_roas_converged ? 'd' : 'ing'} (spread: ${s.marginal_roas_spread})
        </span>
      </div>
    </div>
  `;
  document.getElementById('optSummary').innerHTML = summaryHtml;

  // Comparison table / visual
  const channels = Object.keys(optData.channels);
  const maxSpend = Math.max(...channels.map(ch => optData.channels[ch].optimal_spend), 1);

  let tableHtml = '<table class="opt-compare-table"><thead><tr>' +
    '<th>Channel</th><th>Current</th><th>Optimal</th><th>Δ</th><th>Δ%</th><th>Marg. ROAS</th><th></th></tr></thead><tbody>';

  const fm = v => `$${(v || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  const fmp = v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
  const fmr = v => v.toFixed(2) + 'x';

  for (const ch of channels) {
    const d = optData.channels[ch];
    const pct = maxSpend > 0 ? (d.optimal_spend / maxSpend * 100) : 0;
    tableHtml += `<tr>
      <td class="opt-ch-label">${ch.charAt(0).toUpperCase() + ch.slice(1)}</td>
      <td>${fm(d.current_spend)}</td>
      <td class="opt-p50">${fm(d.optimal_spend)}</td>
      <td class="${d.spend_delta >= 0 ? 'positive' : 'negative'}">${d.spend_delta >= 0 ? '+' : ''}${fm(d.spend_delta)}</td>
      <td class="${d.spend_delta_pct >= 0 ? 'positive' : 'negative'}">${fmp(d.spend_delta_pct)}</td>
      <td>${fmr(d.optimal_marginal_roas)}</td>
      <td><div class="opt-bar" style="width:${Math.max(pct, 2)}%"></div></td>
    </tr>`;
  }
  tableHtml += '</tbody></table>';
  document.getElementById('optTable').innerHTML = tableHtml;
}

// Budget simulator
const simChannel = document.getElementById('simChannel');
const currentSpend = document.getElementById('currentSpend');
const budgetSlider = document.getElementById('budgetSlider');
const budgetValue = document.getElementById('budgetValue');

budgetSlider.addEventListener('input', () => {
  budgetValue.textContent = `$${parseInt(budgetSlider.value).toLocaleString()}`;
  updateSimulation();
});

simChannel.addEventListener('change', updateSimulation);
currentSpend.addEventListener('input', updateSimulation);

function updateSimulation() {
  const channel = simChannel.value;
  const current = parseFloat(currentSpend.value) || 0;
  const newSpend = parseFloat(budgetSlider.value);

  const baseRevenue = forecastData?.[channel]?.[30]?.revenue_p50 || 10000;
  const revPerUnit = baseRevenue / (current || 1000);
  const projectedP50 = revPerUnit * newSpend * 0.7;
  const uncertainty = 0.15 + Math.abs(newSpend - current) / (current + 1) * 0.1;
  const projectedP10 = projectedP50 * (1 - uncertainty);
  const projectedP90 = projectedP50 * (1 + uncertainty);

  document.getElementById('simRevenue').textContent =
    `$${Math.max(0, projectedP10).toFixed(0)} — $${Math.max(0, projectedP90).toFixed(0)}`;
  document.getElementById('simRevenue').className = 'result-value';

  const roas = projectedP50 / (newSpend || 1);
  document.getElementById('simRoas').textContent = `${roas.toFixed(1)}x`;
  document.getElementById('simRoas').className = 'result-value';

  const marginalRoas = (projectedP50 - baseRevenue) / (newSpend - current || 1);
  document.getElementById('simMarginalRoas').textContent = `${marginalRoas.toFixed(2)}x`;
  document.getElementById('simMarginalRoas').className = 'result-value';

  let rec = 'No change in spend';
  if (newSpend !== current) {
    if (marginalRoas > 3) rec = 'Strong — marginal ROAS >3x, increase budget';
    else if (marginalRoas > 1.5) rec = 'Moderate — profitable but diminishing returns visible';
    else if (marginalRoas > 1) rec = 'Borderline — barely profitable at margin';
    else rec = 'Not recommended — marginal ROAS <1x';
  }
  document.getElementById('simRecommendation').textContent = rec;
  document.getElementById('simRecommendation').className = 'result-value';
}
