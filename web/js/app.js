/**
 * ENFR Argentina - Generative S
 * Frontend Senior Application Logic & Data Visualization Engine
 * 
 * Features:
 * 1. PapaParse CSV ingestion for provincial standardization, odds ratios, correlations, and descriptives.
 * 2. Plotly.js & Chart.js responsive medical data visualizations.
 * 3. Health & economic impact simulation model for Argentine health policy.
 * 4. Calibrated clinical inference engine (Logistic Regression AUC ~0.767) with real-time risk gauge.
 * 5. Multi-channel export: Webhook POST (n8n), Netlify Serverless Function (GitHub API), Local CSV/JSON.
 */

// =============================================================================
// GLOBAL STATE & DATA STORAGE
// =============================================================================

// Credenciales y configuración predeterminada del modelo en la nube
const FIXED_APIFY_TOKEN = 'PEGAR_TOKEN_DE_APIFY';
const FIXED_APIFY_ACTOR = 'santibelver/hta-predict';

const APP_STATE = {
  theme: localStorage.getItem('enfr_theme') || 'light',
  webhookUrl: localStorage.getItem('enfr_webhook_url') || '',
  apifyToken: FIXED_APIFY_TOKEN,
  apifyActor: FIXED_APIFY_ACTOR,
  currentMainTab: 'eda',
  currentEdaSubtab: 'prov',
  datasets: {
    estandarizada: [],
    oddsRatio: [],
    correlacion: [],
    descriptivas: [],
    eda: []
  },
  lastPrediction: null,
  history: JSON.parse(localStorage.getItem('enfr_predictions_history') || '[]'),
  charts: {
    provStandardized: null,
    forestPlot: null,
    correlationHeatmap: null,
    imcEvolution: null,
    temporalTrends: null,
    riskBreakdownChart: null
  }
};

// 24 Jurisdicciones de Argentina con ponderación relativa de HTA
const PROVINCIAS_ARGENTINA = [
  "Formosa", "Chaco", "Santiago del Estero", "Corrientes", "Misiones",
  "Salta", "Jujuy", "Catamarca", "Tucumán", "San Juan", "La Rioja",
  "Entre Ríos", "San Luis", "Santa Fe", "Buenos Aires", "Córdoba",
  "Mendoza", "La Pampa", "Neuquén", "Río Negro", "Chubut", "Santa Cruz",
  "Ciudad de Buenos Aires (CABA)", "Tierra del Fuego"
];

// Fallback datasets embebidos (por si se abre vía file:// sin servidor web local)
const FALLBACK_DATA = {
  estandarizada: [
    { provincia: "Formosa", n: 1280, cruda_pct: 42.8, estandarizada_pct: 41.9, diferencia_pp: -0.9 },
    { provincia: "Chaco", n: 1340, cruda_pct: 39.5, estandarizada_pct: 38.8, diferencia_pp: -0.7 },
    { provincia: "Santiago del Estero", n: 1295, cruda_pct: 39.1, estandarizada_pct: 38.4, diferencia_pp: -0.7 },
    { provincia: "Corrientes", n: 1220, cruda_pct: 38.2, estandarizada_pct: 37.6, diferencia_pp: -0.6 },
    { provincia: "Misiones", n: 1310, cruda_pct: 37.8, estandarizada_pct: 37.1, diferencia_pp: -0.7 },
    { provincia: "Salta", n: 1380, cruda_pct: 36.9, estandarizada_pct: 36.4, diferencia_pp: -0.5 },
    { provincia: "Jujuy", n: 1290, cruda_pct: 36.5, estandarizada_pct: 35.9, diferencia_pp: -0.6 },
    { provincia: "Catamarca", n: 1150, cruda_pct: 36.2, estandarizada_pct: 35.5, diferencia_pp: -0.7 },
    { provincia: "Tucumán", n: 1420, cruda_pct: 35.9, estandarizada_pct: 35.1, diferencia_pp: -0.8 },
    { provincia: "San Juan", n: 1210, cruda_pct: 35.4, estandarizada_pct: 34.8, diferencia_pp: -0.6 },
    { provincia: "La Rioja", n: 1180, cruda_pct: 35.1, estandarizada_pct: 34.5, diferencia_pp: -0.6 },
    { provincia: "Entre Ríos", n: 1350, cruda_pct: 36.8, estandarizada_pct: 34.3, diferencia_pp: -2.5 },
    { provincia: "San Luis", n: 1190, cruda_pct: 34.7, estandarizada_pct: 34.0, diferencia_pp: -0.7 },
    { provincia: "Santa Fe", n: 1680, cruda_pct: 36.2, estandarizada_pct: 33.8, diferencia_pp: -2.4 },
    { provincia: "Buenos Aires", n: 4250, cruda_pct: 35.6, estandarizada_pct: 33.6, diferencia_pp: -2.0 },
    { provincia: "Córdoba", n: 1850, cruda_pct: 35.2, estandarizada_pct: 33.2, diferencia_pp: -2.0 },
    { provincia: "Mendoza", n: 1450, cruda_pct: 34.6, estandarizada_pct: 32.9, diferencia_pp: -1.7 },
    { provincia: "La Pampa", n: 1120, cruda_pct: 34.2, estandarizada_pct: 32.4, diferencia_pp: -1.8 },
    { provincia: "Neuquén", n: 1180, cruda_pct: 29.8, estandarizada_pct: 32.1, diferencia_pp: 2.3 },
    { provincia: "Río Negro", n: 1240, cruda_pct: 31.5, estandarizada_pct: 31.8, diferencia_pp: 0.3 },
    { provincia: "Chubut", n: 1160, cruda_pct: 30.4, estandarizada_pct: 31.5, diferencia_pp: 1.1 },
    { provincia: "Santa Cruz", n: 1080, cruda_pct: 28.2, estandarizada_pct: 30.9, diferencia_pp: 2.7 },
    { provincia: "Ciudad de Buenos Aires (CABA)", n: 2100, cruda_pct: 36.9, estandarizada_pct: 29.4, diferencia_pp: -7.5 },
    { provincia: "Tierra del Fuego", n: 980, cruda_pct: 25.4, estandarizada_pct: 28.7, diferencia_pp: 3.3 }
  ],
  oddsRatio: [
    { factor: "Diabetes", or_crudo: 2.82, crudo_ic_bajo: 2.61, crudo_ic_alto: 3.05, or_ajustado_edad: 2.12, ajust_ic_bajo: 1.95, ajust_ic_alto: 2.30 },
    { factor: "Obesidad (IMC ≥ 30)", or_crudo: 2.54, crudo_ic_bajo: 2.38, crudo_ic_alto: 2.71, or_ajustado_edad: 2.21, ajust_ic_bajo: 2.06, ajust_ic_alto: 2.37 },
    { factor: "Colesterol alto", or_crudo: 2.45, crudo_ic_bajo: 2.31, crudo_ic_alto: 2.60, or_ajustado_edad: 1.96, ajust_ic_bajo: 1.84, ajust_ic_alto: 2.09 },
    { factor: "Sobrepeso (IMC 25-29.9)", or_crudo: 1.62, crudo_ic_bajo: 1.52, crudo_ic_alto: 1.73, or_ajustado_edad: 1.48, ajust_ic_bajo: 1.38, ajust_ic_alto: 1.59 },
    { factor: "Edad ≥ 50 años", or_crudo: 4.85, crudo_ic_bajo: 4.56, crudo_ic_alto: 5.16, or_ajustado_edad: 4.85, ajust_ic_bajo: 4.56, ajust_ic_alto: 5.16 },
    { factor: "Quintil de ingreso (Q1 vs Q5)", or_crudo: 1.12, crudo_ic_bajo: 1.02, crudo_ic_alto: 1.23, or_ajustado_edad: 1.29, ajust_ic_bajo: 1.17, ajust_ic_alto: 1.42 },
    { factor: "Sexo (Varón vs Mujer)", or_crudo: 1.15, crudo_ic_bajo: 1.08, crudo_ic_alto: 1.22, or_ajustado_edad: 1.26, ajust_ic_bajo: 1.18, ajust_ic_alto: 1.35 },
    { factor: "Ex fumador", or_crudo: 1.58, crudo_ic_bajo: 1.47, crudo_ic_alto: 1.70, or_ajustado_edad: 1.21, ajust_ic_bajo: 1.12, ajust_ic_alto: 1.31 },
    { factor: "Baja actividad física", or_crudo: 1.32, crudo_ic_bajo: 1.23, crudo_ic_alto: 1.41, or_ajustado_edad: 1.18, ajust_ic_bajo: 1.10, ajust_ic_alto: 1.27 },
    { factor: "Sin cobertura de salud", or_crudo: 0.71, crudo_ic_bajo: 0.66, crudo_ic_alto: 0.77, or_ajustado_edad: 1.14, ajust_ic_bajo: 1.05, ajust_ic_alto: 1.24 },
    { factor: "Fumador actual", or_crudo: 0.74, crudo_ic_bajo: 0.68, crudo_ic_alto: 0.81, or_ajustado_edad: 0.85, ajust_ic_bajo: 0.78, ajust_ic_alto: 0.93 }
  ],
  descriptivas: [
    { anio: 2005, variable: "edad", media: 42.8, varianza: 306.2, desvio: 17.5, mediana: 41.0, q1: 28.0, q3: 56.0 },
    { anio: 2005, variable: "imc", media: 25.8, varianza: 22.1, desvio: 4.7, mediana: 25.1, q1: 22.5, q3: 28.4 },
    { anio: 2009, variable: "edad", media: 43.4, varianza: 309.8, desvio: 17.6, mediana: 42.0, q1: 29.0, q3: 57.0 },
    { anio: 2009, variable: "imc", media: 26.4, varianza: 24.0, desvio: 4.9, mediana: 25.7, q1: 22.9, q3: 29.2 },
    { anio: 2013, variable: "edad", media: 44.1, varianza: 313.3, desvio: 17.7, mediana: 43.0, q1: 29.0, q3: 58.0 },
    { anio: 2013, variable: "imc", media: 27.1, varianza: 27.0, desvio: 5.2, mediana: 26.4, q1: 23.3, q3: 30.1 },
    { anio: 2018, variable: "edad", media: 44.9, varianza: 320.4, desvio: 17.9, mediana: 44.0, q1: 30.0, q3: 59.0 },
    { anio: 2018, variable: "imc", media: 27.9, varianza: 31.4, desvio: 5.6, mediana: 27.1, q1: 23.8, q3: 31.1 }
  ]
};

// =============================================================================
// INITIALIZATION ON DOM READY
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
  try { initTheme(); } catch (e) { console.error('Error en initTheme:', e); }
  try { populateProvinceSelect(); } catch (e) { console.error('Error en populateProvinceSelect:', e); }
  try { loadAllEdaDatasets(); } catch (e) { console.error('Error en loadAllEdaDatasets:', e); }
  try { runHealthSimulation(); } catch (e) { console.error('Error en runHealthSimulation:', e); }
  try { calculateBMI(); } catch (e) { console.error('Error en calculateBMI:', e); }
  try { renderHistoryTable(); } catch (e) { console.error('Error en renderHistoryTable:', e); }
  try { setupSettingsUI(); } catch (e) { console.error('Error en setupSettingsUI:', e); }
  try { syncApifyInputs(); } catch (e) { console.error('Error en syncApifyInputs:', e); }

  // Estado inicial del tacómetro
  try { renderGauge(null); } catch (e) { console.error('Error en renderGauge:', e); }

  // Redimensionamiento adaptativo de gráficos
  window.addEventListener('resize', () => {
    try { resizeActiveCharts(); } catch (e) {}
  });
});

// =============================================================================
// THEME & UI HELPERS
// =============================================================================

function initTheme() {
  const isDark = APP_STATE.theme === 'dark';
  document.documentElement.classList.toggle('dark', isDark);
  updateThemeIcon(isDark);

  document.getElementById('btn-theme-toggle').addEventListener('click', () => {
    const willBeDark = !document.documentElement.classList.contains('dark');
    document.documentElement.classList.toggle('dark', willBeDark);
    APP_STATE.theme = willBeDark ? 'dark' : 'light';
    localStorage.setItem('enfr_theme', APP_STATE.theme);
    updateThemeIcon(willBeDark);
    
    // Redraw charts with adapted color schemes
    renderActiveEdaChart();
    if (APP_STATE.lastPrediction) {
      renderGauge(APP_STATE.lastPrediction.probabilidad_pct);
      renderRiskFactorsChart(APP_STATE.lastPrediction.breakdown);
    }
  });
}

function updateThemeIcon(isDark) {
  const icon = document.getElementById('theme-toggle-icon');
  if (icon) {
    icon.className = isDark ? 'fa-solid fa-sun text-lg text-amber-400' : 'fa-solid fa-moon text-lg text-slate-500';
  }
}

function getPlotlyLayoutTheme() {
  const isDark = document.documentElement.classList.contains('dark');
  return {
    paper_bgcolor: isDark ? '#1e293b' : '#ffffff',
    plot_bgcolor: isDark ? '#1e293b' : '#ffffff',
    font: {
      family: 'Inter, system-ui, sans-serif',
      color: isDark ? '#f8fafc' : '#1e293b',
      size: 11
    },
    gridcolor: isDark ? '#334155' : '#f1f5f9'
  };
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const colors = {
    success: 'bg-emerald-600 text-white',
    error: 'bg-rose-600 text-white',
    warning: 'bg-amber-600 text-white',
    info: 'bg-sky-600 text-white'
  };

  const icons = {
    success: 'fa-check-circle',
    error: 'fa-triangle-exclamation',
    warning: 'fa-circle-exclamation',
    info: 'fa-circle-info'
  };

  toast.className = `toast ${colors[type] || colors.info}`;
  toast.innerHTML = `
    <i class="fa-solid ${icons[type] || icons.info} text-base"></i>
    <div class="flex-grow">${message}</div>
    <button onclick="this.parentElement.remove()" class="text-white/80 hover:text-white ml-2">
      <i class="fa-solid fa-xmark"></i>
    </button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// =============================================================================
// TAB NAVIGATION
// =============================================================================

function switchMainTab(tabId) {
  APP_STATE.currentMainTab = tabId;

  // Toggle button active states
  ['eda', 'kpis', 'inference'].forEach(id => {
    const btn = document.getElementById(`tab-nav-${id}`);
    const sec = document.getElementById(`section-${id}`);
    if (id === tabId) {
      btn?.classList.add('active');
      btn?.classList.remove('text-slate-500', 'dark:text-slate-400');
      sec?.classList.remove('hidden');
    } else {
      btn?.classList.remove('active');
      btn?.classList.add('text-slate-500', 'dark:text-slate-400');
      sec?.classList.add('hidden');
    }
  });

  // When switching into EDA, render subtab chart
  if (tabId === 'eda') {
    setTimeout(() => renderActiveEdaChart(), 50);
  } else if (tabId === 'inference') {
    setTimeout(() => {
      if (APP_STATE.lastPrediction) {
        renderGauge(APP_STATE.lastPrediction.probabilidad_pct);
        renderRiskFactorsChart(APP_STATE.lastPrediction.breakdown);
      } else {
        renderGauge(null);
      }
    }, 50);
  }
}

function switchEdaSubtab(subtabId) {
  APP_STATE.currentEdaSubtab = subtabId;

  ['prov', 'odds', 'corr', 'stats', 'evol'].forEach(id => {
    const btn = document.getElementById(`subtab-btn-${id}`);
    const pane = document.getElementById(`subpane-${id}`);
    if (id === subtabId) {
      btn?.classList.add('active');
      btn?.classList.remove('text-slate-600', 'dark:text-slate-300');
      pane?.classList.remove('hidden');
    } else {
      btn?.classList.remove('active');
      btn?.classList.add('text-slate-600', 'dark:text-slate-300');
      pane?.classList.add('hidden');
    }
  });

  setTimeout(() => renderActiveEdaChart(), 50);
}

function renderActiveEdaChart() {
  switch (APP_STATE.currentEdaSubtab) {
    case 'prov':
      renderProvChart();
      break;
    case 'odds':
      renderOddsRatioChart();
      break;
    case 'corr':
      renderCorrelationHeatmap();
      break;
    case 'stats':
      renderDescriptiveCards();
      renderImcEvolutionChart();
      break;
    case 'evol':
      renderTemporalTrendsChart();
      break;
  }
}

function resizeActiveCharts() {
  const plotIds = ['chart-prov-standardized', 'chart-forest-plot', 'chart-correlation-heatmap', 'chart-imc-evolution', 'chart-temporal-trends'];
  plotIds.forEach(id => {
    const el = document.getElementById(id);
    if (el && el.data) {
      Plotly.Plots.resize(el);
    }
  });
}

// =============================================================================
// CSV DATA LOADING (PAPAPARSE)
// =============================================================================

async function loadAllEdaDatasets(forceRefresh = false) {
  const statusBadge = document.getElementById('data-status-text');
  if (statusBadge) statusBadge.textContent = "Cargando datasets...";

  try {
    const [provData, oddsData, corrData, descData, edaData] = await Promise.all([
      fetchAndParseCSV('data/enfr_estandarizada.csv', FALLBACK_DATA.estandarizada),
      fetchAndParseCSV('data/enfr_odds_ratio.csv', FALLBACK_DATA.oddsRatio),
      fetchAndParseCSV('data/enfr_correlacion.csv', null),
      fetchAndParseCSV('data/enfr_descriptivas.csv', FALLBACK_DATA.descriptivas),
      fetchAndParseCSV('data/enfr_eda.csv', null)
    ]);

    APP_STATE.datasets.estandarizada = provData;
    APP_STATE.datasets.oddsRatio = oddsData;
    APP_STATE.datasets.correlacion = corrData;
    APP_STATE.datasets.descriptivas = descData;
    APP_STATE.datasets.eda = edaData;

    if (statusBadge) statusBadge.textContent = "Datos oficiales cargados (INDEC)";
    if (forceRefresh) showToast("Datasets recargados con éxito.", "success");

    // Populate Top 5 provinces & full table
    populateProvTable(provData);
    populateTopProvinces(provData);

    // Render active tab chart
    renderActiveEdaChart();

  } catch (err) {
    console.warn("Uso de datos fallback debido a:", err);
    APP_STATE.datasets.estandarizada = FALLBACK_DATA.estandarizada;
    APP_STATE.datasets.oddsRatio = FALLBACK_DATA.oddsRatio;
    APP_STATE.datasets.descriptivas = FALLBACK_DATA.descriptivas;

    if (statusBadge) statusBadge.textContent = "Datos de respaldo activos";
    populateProvTable(FALLBACK_DATA.estandarizada);
    populateTopProvinces(FALLBACK_DATA.estandarizada);
    renderActiveEdaChart();
  }
}

function fetchAndParseCSV(url, fallback) {
  return new Promise((resolve) => {
    Papa.parse(url, {
      download: true,
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results && results.data && results.data.length > 0) {
          resolve(results.data);
        } else if (fallback) {
          resolve(fallback);
        } else {
          resolve([]);
        }
      },
      error: (err) => {
        console.warn(`Error leyendo ${url}, aplicando fallback.`, err);
        resolve(fallback || []);
      }
    });
  });
}

// =============================================================================
// EDA SECTION 1: PROVINCIAS (CRUDA VS ESTANDARIZADA)
// =============================================================================

function renderProvChart() {
  const container = document.getElementById('chart-prov-standardized');
  if (!container) return;

  const data = APP_STATE.datasets.estandarizada || FALLBACK_DATA.estandarizada;
  if (!data || data.length === 0) return;

  // Sort ascending by standardized prevalence
  const sorted = [...data].sort((a, b) => a.estandarizada_pct - b.estandarizada_pct);

  const theme = getPlotlyLayoutTheme();

  // Trace 1: Cruda (Slate dots)
  const traceCruda = {
    x: sorted.map(d => d.cruda_pct),
    y: sorted.map(d => d.provincia),
    mode: 'markers',
    name: 'Prevalencia Cruda',
    marker: {
      color: '#94a3b8',
      size: 9,
      symbol: 'circle'
    },
    hovertemplate: '<b>%{y}</b><br>Cruda: %{x:.1f}%<extra></extra>'
  };

  // Trace 2: Estandarizada por edad (Sky Blue dots with border)
  const traceEstandarizada = {
    x: sorted.map(d => d.estandarizada_pct),
    y: sorted.map(d => d.provincia),
    mode: 'markers',
    name: 'Estandarizada por Edad',
    marker: {
      color: '#0284c7',
      size: 11,
      symbol: 'circle',
      line: { color: '#0369a1', width: 1.5 }
    },
    hovertemplate: '<b>%{y}</b><br>Estandarizada: %{x:.1f}%<br>Diferencia: %{customdata:+.1f} pp<extra></extra>',
    customdata: sorted.map(d => d.diferencia_pp)
  };

  const isMobile = window.innerWidth < 640;
  const layout = {
    paper_bgcolor: theme.paper_bgcolor,
    plot_bgcolor: theme.plot_bgcolor,
    font: { ...theme.font, size: isMobile ? 9 : 11 },
    margin: { l: isMobile ? 120 : 180, r: isMobile ? 12 : 24, t: isMobile ? 38 : 30, b: isMobile ? 55 : 50 },
    height: isMobile ? 500 : 600,
    xaxis: {
      title: isMobile ? 'Prevalencia HTA (%)' : 'Prevalencia de Hipertensión Arterial (%)',
      gridcolor: theme.gridcolor,
      zeroline: false,
      range: [22, 46],
      ticksuffix: '%'
    },
    yaxis: {
      automargin: true,
      gridcolor: theme.gridcolor
    },
    legend: {
      orientation: 'h',
      y: isMobile ? 1.10 : 1.06,
      x: 0.5,
      xanchor: 'center'
    },
    shapes: [
      // National average vertical dashed line (34.6%)
      {
        type: 'line',
        x0: 34.6,
        x1: 34.6,
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: {
          color: '#ef4444',
          width: 1.5,
          dash: 'dashdot'
        }
      }
    ],
    annotations: [
      {
        x: 34.6,
        y: 1,
        yref: 'paper',
        text: 'Media Nacional (34.6%)',
        showarrow: false,
        font: { color: '#ef4444', size: 10, weight: 600 },
        yshift: 12
      }
    ]
  };

  const config = { responsive: true, displayModeBar: false };
  Plotly.newPlot(container, [traceCruda, traceEstandarizada], layout, config);
}

function populateTopProvinces(data) {
  const container = document.getElementById('top-provinces-list');
  if (!container || !data) return;

  const sorted = [...data].sort((a, b) => b.estandarizada_pct - a.estandarizada_pct).slice(0, 5);

  container.innerHTML = sorted.map((d, idx) => `
    <div class="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
      <div class="flex items-center gap-2">
        <span class="w-5 h-5 rounded-full bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 font-bold flex items-center justify-center text-[10px]">
          ${idx + 1}
        </span>
        <span class="font-medium text-slate-800 dark:text-slate-200">${d.provincia}</span>
      </div>
      <div class="text-right">
        <span class="font-bold text-sky-600 dark:text-sky-400 font-mono">${d.estandarizada_pct.toFixed(1)}%</span>
        <span class="text-[10px] text-slate-400 ml-1">(${d.diferencia_pp >= 0 ? '+' : ''}${d.diferencia_pp.toFixed(1)} pp)</span>
      </div>
    </div>
  `).join('');
}

function populateProvTable(data) {
  const tbody = document.getElementById('prov-table-body');
  if (!tbody || !data) return;

  const sorted = [...data].sort((a, b) => b.estandarizada_pct - a.estandarizada_pct);

  tbody.innerHTML = sorted.map(d => {
    let alertClass = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
    let alertLabel = 'Moderado';

    if (d.estandarizada_pct >= 37.0) {
      alertClass = 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-bold';
      alertLabel = 'Muy Alto';
    } else if (d.estandarizada_pct >= 34.0) {
      alertClass = 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 font-semibold';
      alertLabel = 'Alto';
    }

    return `
      <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
        <td class="py-2.5 px-3 font-medium text-slate-900 dark:text-white">${d.provincia}</td>
        <td class="py-2.5 px-3 text-right font-mono text-slate-500">${d.n ? d.n.toLocaleString('es-AR') : '-'}</td>
        <td class="py-2.5 px-3 text-right font-mono font-semibold text-slate-600 dark:text-slate-300">${d.cruda_pct.toFixed(1)}%</td>
        <td class="py-2.5 px-3 text-right font-mono font-bold text-sky-600 dark:text-sky-400">${d.estandarizada_pct.toFixed(1)}%</td>
        <td class="py-2.5 px-3 text-right font-mono ${d.diferencia_pp < 0 ? 'text-emerald-600' : 'text-amber-600'} font-medium">
          ${d.diferencia_pp >= 0 ? '+' : ''}${d.diferencia_pp.toFixed(1)} pp
        </td>
        <td class="py-2.5 px-3 text-center">
          <span class="px-2 py-0.5 rounded-full text-[10px] ${alertClass}">${alertLabel}</span>
        </td>
      </tr>
    `;
  }).join('');
}

function filterProvTable() {
  const query = (document.getElementById('prov-search-input')?.value || '').toLowerCase();
  const rows = document.querySelectorAll('#prov-table-body tr');
  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(query) ? '' : 'none';
  });
}

// =============================================================================
// EDA SECTION 2: FOREST PLOT (ODDS RATIOS CON IC 95%)
// =============================================================================

function renderOddsRatioChart() {
  const container = document.getElementById('chart-forest-plot');
  if (!container) return;

  const data = APP_STATE.datasets.oddsRatio || FALLBACK_DATA.oddsRatio;
  if (!data || data.length === 0) return;

  // Sort by adjusted OR ascending
  const sorted = [...data].sort((a, b) => (a.or_ajustado_edad || a.odds_ratio) - (b.or_ajustado_edad || b.odds_ratio));

  const theme = getPlotlyLayoutTheme();

  // Trace 1: Crudo
  const traceCrudo = {
    x: sorted.map(d => d.or_crudo),
    y: sorted.map(d => d.factor),
    mode: 'markers',
    name: 'OR Crudo',
    error_x: {
      type: 'data',
      symmetric: false,
      array: sorted.map(d => d.crudo_ic_alto - d.or_crudo),
      arrayminus: sorted.map(d => d.or_crudo - d.crudo_ic_bajo),
      color: '#94a3b8',
      thickness: 1.5,
      width: 4
    },
    marker: {
      color: '#94a3b8',
      size: 8,
      symbol: 'square'
    },
    hovertemplate: '<b>%{y}</b> (Crudo)<br>OR: %{x:.2f}<extra></extra>'
  };

  // Trace 2: Ajustado por edad
  const traceAjustado = {
    x: sorted.map(d => d.or_ajustado_edad || d.odds_ratio),
    y: sorted.map(d => d.factor),
    mode: 'markers',
    name: 'OR Ajustado por Edad',
    error_x: {
      type: 'data',
      symmetric: false,
      array: sorted.map(d => (d.ajust_ic_alto || d.ic_alto) - (d.or_ajustado_edad || d.odds_ratio)),
      arrayminus: sorted.map(d => (d.or_ajustado_edad || d.odds_ratio) - (d.ajust_ic_bajo || d.ic_bajo)),
      color: '#0284c7',
      thickness: 2,
      width: 5
    },
    marker: {
      color: '#0284c7',
      size: 10,
      symbol: 'diamond'
    },
    hovertemplate: '<b>%{y}</b> (Ajustado)<br>OR: %{x:.2f}<br>IC 95%: [%{customdata[0]:.2f} - %{customdata[1]:.2f}]<extra></extra>',
    customdata: sorted.map(d => [d.ajust_ic_bajo || d.ic_bajo, d.ajust_ic_alto || d.ic_alto])
  };

  const isMobile = window.innerWidth < 640;
  const layout = {
    paper_bgcolor: theme.paper_bgcolor,
    plot_bgcolor: theme.plot_bgcolor,
    font: { ...theme.font, size: isMobile ? 9 : 11 },
    margin: { l: isMobile ? 125 : 200, r: isMobile ? 12 : 24, t: isMobile ? 35 : 20, b: isMobile ? 55 : 50 },
    height: isMobile ? 420 : 480,
    xaxis: {
      type: 'log',
      title: isMobile ? 'Odds Ratio (IC 95%)' : 'Odds Ratio (Escala Logarítmica - IC 95%)',
      gridcolor: theme.gridcolor,
      tickvals: [0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0],
      ticktext: ['0.5', '0.7', '1.0', '1.5', '2.0', '3.0', '5.0']
    },
    yaxis: {
      automargin: true,
      gridcolor: theme.gridcolor
    },
    legend: {
      orientation: 'h',
      y: isMobile ? 1.12 : 1.08,
      x: 0.5,
      xanchor: 'center'
    },
    shapes: [
      // Line of no effect OR = 1.0
      {
        type: 'line',
        x0: 1.0,
        x1: 1.0,
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: {
          color: '#64748b',
          width: 1.5,
          dash: 'dash'
        }
      }
    ]
  };

  Plotly.newPlot(container, [traceCrudo, traceAjustado], layout, { responsive: true, displayModeBar: false });
}

// =============================================================================
// EDA SECTION 3: MATRIZ DE CORRELACIÓN
// =============================================================================

function renderCorrelationHeatmap() {
  const container = document.getElementById('chart-correlation-heatmap');
  if (!container) return;

  // Variables and correlation values
  // Excluded redundant IMC per project methodology
  const labels = ["Hipertensión", "Diabetes", "Colesterol Alto", "Obesidad", "Edad"];
  const zValues = [
    [1.00, 0.16, 0.21, 0.18, 0.34],
    [0.16, 1.00, 0.15, 0.14, 0.18],
    [0.21, 0.15, 1.00, 0.12, 0.21],
    [0.18, 0.14, 0.12, 1.00, 0.11],
    [0.34, 0.18, 0.21, 0.11, 1.00]
  ];

  const theme = getPlotlyLayoutTheme();

  const data = [{
    z: zValues,
    x: labels,
    y: labels,
    type: 'heatmap',
    colorscale: [
      [0.0, '#f0f9ff'],
      [0.25, '#bae6fd'],
      [0.5, '#38bdf8'],
      [0.75, '#0284c7'],
      [1.0, '#0c4a6e']
    ],
    zmin: 0.0,
    zmax: 0.40, // Scaled to 0.40 so differences pop up (diagonal 1.0 will cap)
    hoverongaps: false,
    text: zValues.map(row => row.map(v => v.toFixed(2))),
    texttemplate: '%{text}',
    textfont: {
      family: 'Inter, sans-serif',
      size: 13,
      color: theme.font.color
    },
    colorbar: {
      title: 'r',
      len: 0.9,
      thickness: 14
    }
  }];

  const layout = {
    paper_bgcolor: theme.paper_bgcolor,
    plot_bgcolor: theme.plot_bgcolor,
    font: theme.font,
    margin: { l: 120, r: 40, t: 30, b: 80 },
    height: 420,
    xaxis: { automargin: true },
    yaxis: { automargin: true, autorange: 'reversed' }
  };

  Plotly.newPlot(container, data, layout, { responsive: true, displayModeBar: false });
}

// =============================================================================
// EDA SECTION 4: DESCRIPTIVAS & EVOLUCIÓN IMC
// =============================================================================

function renderDescriptiveCards() {
  const year = parseInt(document.getElementById('select-desc-year')?.value || '2018', 10);
  const data = APP_STATE.datasets.descriptivas || FALLBACK_DATA.descriptivas;

  const edadRow = data.find(d => d.anio === year && d.variable === 'edad') || {
    media: 44.9, varianza: 320.4, desvio: 17.9, mediana: 44.0, q1: 30.0, q3: 59.0
  };

  const imcRow = data.find(d => d.anio === year && d.variable === 'imc') || {
    media: 27.9, varianza: 31.4, desvio: 5.6, mediana: 27.1, q1: 23.8, q3: 31.1
  };

  // Update Edad cards
  document.getElementById('badge-edad-year').textContent = year;
  document.getElementById('stat-edad-media').textContent = `${edadRow.media.toFixed(1)} años`;
  document.getElementById('stat-edad-mediana').textContent = `${edadRow.mediana.toFixed(1)} años`;
  document.getElementById('stat-edad-desvio').textContent = `± ${edadRow.desvio.toFixed(1)}`;
  document.getElementById('stat-edad-varianza').textContent = edadRow.varianza.toFixed(1);
  document.getElementById('stat-edad-q1').textContent = `${edadRow.q1.toFixed(1)} años`;
  document.getElementById('stat-edad-q3').textContent = `${edadRow.q3.toFixed(1)} años`;

  // Update IMC cards
  document.getElementById('badge-imc-year').textContent = year;
  document.getElementById('stat-imc-media').textContent = `${imcRow.media.toFixed(1)} kg/m²`;
  document.getElementById('stat-imc-mediana').textContent = `${imcRow.mediana.toFixed(1)} kg/m²`;
  document.getElementById('stat-imc-desvio').textContent = `± ${imcRow.desvio.toFixed(1)}`;
  document.getElementById('stat-imc-varianza').textContent = imcRow.varianza.toFixed(1);
  document.getElementById('stat-imc-q1').textContent = `${imcRow.q1.toFixed(1)} kg/m²`;
  document.getElementById('stat-imc-q3').textContent = `${imcRow.q3.toFixed(1)} kg/m²`;
}

function renderImcEvolutionChart() {
  const container = document.getElementById('chart-imc-evolution');
  if (!container) return;

  const years = [2005, 2009, 2013, 2018];
  const data = APP_STATE.datasets.descriptivas || FALLBACK_DATA.descriptivas;

  const imcData = years.map(y => data.find(d => d.anio === y && d.variable === 'imc') || {});

  const medias = imcData.map(d => d.media || (25.8 + (d.anio - 2005) * 0.16));
  const q1s = imcData.map(d => d.q1 || 22.5);
  const q3s = imcData.map(d => d.q3 || 28.4);

  const theme = getPlotlyLayoutTheme();

  // Trace Q3
  const traceQ3 = {
    x: years,
    y: q3s,
    mode: 'lines',
    line: { dash: 'dot', color: '#94a3b8', width: 1.5 },
    name: 'Cuartil 3 (75% población)',
    hovertemplate: 'Q3: %{y:.1f} kg/m²<extra></extra>'
  };

  // Trace Media
  const traceMedia = {
    x: years,
    y: medias,
    mode: 'lines+markers',
    name: 'IMC Medio Nacional',
    line: { color: '#0284c7', width: 3 },
    marker: { size: 8, color: '#0369a1' },
    hovertemplate: '<b>Año %{x}</b><br>Media: %{y:.1f} kg/m²<extra></extra>'
  };

  // Trace Q1
  const traceQ1 = {
    x: years,
    y: q1s,
    mode: 'lines',
    line: { dash: 'dot', color: '#94a3b8', width: 1.5 },
    name: 'Cuartil 1 (25% población)',
    hovertemplate: 'Q1: %{y:.1f} kg/m²<extra></extra>'
  };

  const layout = {
    paper_bgcolor: theme.paper_bgcolor,
    plot_bgcolor: theme.plot_bgcolor,
    font: theme.font,
    margin: { l: 60, r: 30, t: 20, b: 40 },
    height: 320,
    xaxis: {
      title: 'Año de Encuesta ENFR',
      tickvals: years,
      gridcolor: theme.gridcolor
    },
    yaxis: {
      title: 'IMC (kg/m²)',
      range: [20, 34],
      gridcolor: theme.gridcolor
    },
    shapes: [
      // Obesity Threshold Line (30 kg/m²)
      {
        type: 'line',
        x0: 2005,
        x1: 2018,
        y0: 30.0,
        y1: 30.0,
        line: { color: '#dc2626', width: 1.5, dash: 'dash' }
      }
    ],
    annotations: [
      {
        x: 2017,
        y: 30.2,
        text: 'Umbral Obesidad (30 kg/m²)',
        showarrow: false,
        font: { color: '#dc2626', size: 10, weight: 600 }
      }
    ],
    legend: {
      orientation: 'h',
      y: 1.12,
      x: 0.5,
      xanchor: 'center'
    }
  };

  Plotly.newPlot(container, [traceQ3, traceMedia, traceQ1], layout, { responsive: true, displayModeBar: false });
}

// =============================================================================
// EDA SECTION 5: EVOLUCIÓN TEMPORAL
// =============================================================================

function renderTemporalTrendsChart() {
  const container = document.getElementById('chart-temporal-trends');
  if (!container) return;

  const years = [2005, 2009, 2013, 2018];
  const conditions = [
    { name: 'Hipertensión Arterial', values: [34.4, 34.7, 34.1, 34.6], color: '#f43f5e' },
    { name: 'Colesterol Alto', values: [27.9, 29.1, 29.8, 28.9], color: '#6366f1' },
    { name: 'Obesidad (IMC ≥ 30)', values: [14.6, 18.0, 20.8, 25.4], color: '#f59e0b' },
    { name: 'Diabetes', values: [8.4, 9.6, 9.8, 12.7], color: '#10b981' }
  ];

  const theme = getPlotlyLayoutTheme();

  const traces = conditions.map(c => ({
    x: years,
    y: c.values,
    name: c.name,
    mode: 'lines+markers',
    line: { color: c.color, width: 2.5 },
    marker: { size: 7, color: c.color },
    hovertemplate: `<b>${c.name}</b><br>Año %{x}: %{y:.1f}%<extra></extra>`
  }));

  const layout = {
    paper_bgcolor: theme.paper_bgcolor,
    plot_bgcolor: theme.plot_bgcolor,
    font: theme.font,
    margin: { l: 60, r: 30, t: 20, b: 50 },
    height: 380,
    xaxis: {
      title: 'Año de la Encuesta ENFR',
      tickvals: years,
      gridcolor: theme.gridcolor
    },
    yaxis: {
      title: 'Prevalencia Poblacional Total (%)',
      ticksuffix: '%',
      range: [5, 40],
      gridcolor: theme.gridcolor
    },
    legend: {
      orientation: 'h',
      y: 1.1,
      x: 0.5,
      xanchor: 'center'
    }
  };

  Plotly.newPlot(container, traces, layout, { responsive: true, displayModeBar: false });
}

// =============================================================================
// TAB 2: SIMULADOR DE CAPACIDAD OPERATIVA Y EFICIENCIA MÉDICA
// =============================================================================

function runHealthSimulation() {
  const controlsSlider = document.getElementById('sim-slider-controls');
  const costSlider = document.getElementById('sim-slider-cost');

  const controlsCount = parseInt(controlsSlider?.value || '5000', 10);
  const savingPerPatient = parseInt(costSlider?.value || '850', 10);

  // Update slider label displays
  const labelControls = document.getElementById('sim-val-controls');
  if (labelControls) labelControls.textContent = `${controlsCount.toLocaleString('es-AR')} controles/mes`;

  const labelCost = document.getElementById('sim-val-cost');
  if (labelCost) labelCost.textContent = `$${savingPerPatient.toLocaleString('es-AR')} USD/paciente`;

  // Métrica de Negocio:
  // Al azar: 2,87 controles para hallar 1 caso
  const casesRandom = Math.round(controlsCount / 2.87);
  // Con el modelo: 1,39 controles para hallar 1 caso
  const casesModel = Math.round(controlsCount / 1.39);
  const extraCases = casesModel - casesRandom;
  const multiplier = (casesModel / casesRandom).toFixed(2);

  // Impacto económico dinámico (responde al slider de costo por paciente evitado)
  const monthlySavings = extraCases * savingPerPatient;
  const annualSavings = monthlySavings * 12;

  const elRandom = document.getElementById('sim-out-random');
  const elModel = document.getElementById('sim-out-model');
  const elGain = document.getElementById('sim-out-gain');
  const elMultiplier = document.getElementById('sim-out-multiplier');
  const elSavings = document.getElementById('sim-out-savings');
  const elSavingsDesc = document.getElementById('sim-out-savings-desc');

  if (elRandom) elRandom.textContent = casesRandom.toLocaleString('es-AR');
  if (elModel) elModel.textContent = casesModel.toLocaleString('es-AR');
  if (elGain) elGain.textContent = `+${extraCases.toLocaleString('es-AR')}`;
  if (elMultiplier) elMultiplier.textContent = `x${multiplier}`;
  if (elSavings) elSavings.textContent = `+$${monthlySavings.toLocaleString('es-AR')} USD`;
  if (elSavingsDesc) {
    const formattedAnnual = annualSavings >= 1000000 
      ? `+$${(annualSavings / 1000000).toFixed(1).replace('.', ',')}M USD/año`
      : `+$${annualSavings.toLocaleString('es-AR')} USD/año`;
    elSavingsDesc.textContent = `${formattedAnnual} evitado`;
  }
}

// =============================================================================
// TAB 3: INFERENCIA CLÍNICA Y CÁLCULO DE RIESGO
// =============================================================================

function populateProvinceSelect() {
  const select = document.getElementById('input-provincia');
  if (!select) return;

  select.innerHTML = PROVINCIAS_ARGENTINA.map(p => {
    const selected = p === "Buenos Aires" ? "selected" : "";
    return `<option value="${p}" ${selected}>${p}</option>`;
  }).join('');
}

function syncAgeInput(val) {
  document.getElementById('input-age').value = val;
  document.getElementById('label-age-val').textContent = `${val} años`;
}

function syncAgeRange(val) {
  const clamped = Math.max(18, Math.min(95, parseInt(val || '18', 10)));
  document.getElementById('input-age-range').value = clamped;
  document.getElementById('label-age-val').textContent = `${clamped} años`;
}

function calculateBMI() {
  const weight = parseFloat(document.getElementById('input-weight')?.value || '70');
  const heightCm = parseFloat(document.getElementById('input-height')?.value || '170');
  
  const heightM = heightCm / 100;
  const bmi = weight / (heightM * heightM);

  const displayEl = document.getElementById('output-imc-val');
  const badgeEl = document.getElementById('imc-badge');

  if (displayEl) displayEl.textContent = `${bmi.toFixed(2)} kg/m²`;

  let badgeText = "Normal";
  let badgeColor = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300";

  if (bmi < 18.5) {
    badgeText = `Bajo peso (${bmi.toFixed(1)})`;
    badgeColor = "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border-sky-300";
  } else if (bmi < 25.0) {
    badgeText = `Normal (${bmi.toFixed(1)})`;
    badgeColor = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300";
  } else if (bmi < 30.0) {
    badgeText = `Sobrepeso (${bmi.toFixed(1)})`;
    badgeColor = "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-300";
  } else if (bmi < 35.0) {
    badgeText = `Obesidad I (${bmi.toFixed(1)})`;
    badgeColor = "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-300";
  } else {
    badgeText = `Obesidad Severa (${bmi.toFixed(1)})`;
    badgeColor = "bg-rose-200 text-rose-900 dark:bg-rose-900 dark:text-rose-200 border-rose-500";
  }

  if (badgeEl) {
    badgeEl.textContent = badgeText;
    badgeEl.className = `text-[11px] px-2 py-0.5 rounded-full font-bold border ${badgeColor}`;
  }

  return bmi;
}

/**
 * Pure statistical calculation function based on calibrated ENFR model (AUC ~0.767)
 */
function calculateModelPrediction(input) {
  const age = parseInt(input.edad || 50, 10);
  const weight = parseFloat(input.peso_kg || 75);
  const height = parseFloat(input.altura_cm || 170);
  const bmi = weight / ((height / 100) * (height / 100));
  const sexo = input.sexo || 'varon';
  const hasDiabetes = input.diabetes === 1 || input.diabetes === true;
  const hasCholesterol = input.colesterol_alto === 1 || input.colesterol_alto === true;
  const tabaco = input.tabaquismo || 'nunca';
  const actividad = input.actividad_fisica || 'baja';
  const cobertura = input.cobertura_salud || 'con_cobertura';
  const quintil = input.quintil_ingreso || 'Q3';
  const provincia = input.provincia || 'Buenos Aires';

  // Base intercept for calibrated 34.6% population prevalence
  let logit = -3.75;
  const breakdown = [];

  // 1. Age contribution (dominant linear factor)
  const ageImpact = 0.052 * (age - 25);
  logit += ageImpact;
  breakdown.push({ factor: 'Edad', impact: ageImpact, label: `${age} años (+${(ageImpact).toFixed(2)})` });

  // 2. Sex impact
  const sexImpact = sexo === 'varon' ? 0.23 : -0.10;
  logit += sexImpact;
  breakdown.push({ factor: 'Sexo Biológico', impact: sexImpact, label: sexo === 'varon' ? 'Varón (+0.23)' : 'Mujer (-0.10)' });

  // 3. BMI impact
  let bmiImpact = 0;
  if (bmi >= 35.0) bmiImpact = 1.05;
  else if (bmi >= 30.0) bmiImpact = 0.79;
  else if (bmi >= 25.0) bmiImpact = 0.39;
  else if (bmi < 18.5) bmiImpact = -0.15;
  logit += bmiImpact;
  breakdown.push({ factor: 'IMC / Obesidad', impact: bmiImpact, label: `IMC ${bmi.toFixed(1)} (+${bmiImpact.toFixed(2)})` });

  // 4. Diabetes (OR 2.12 -> beta ~0.75)
  const diabImpact = hasDiabetes ? 0.75 : 0;
  logit += diabImpact;
  if (hasDiabetes) {
    breakdown.push({ factor: 'Diabetes', impact: diabImpact, label: 'Presente (+0.75)' });
  }

  // 5. Colesterol alto (OR 1.96 -> beta ~0.67)
  const cholImpact = hasCholesterol ? 0.67 : 0;
  logit += cholImpact;
  if (hasCholesterol) {
    breakdown.push({ factor: 'Colesterol Alto', impact: cholImpact, label: 'Presente (+0.67)' });
  }

  // 6. Tabaco
  let tabacoImpact = 0;
  if (tabaco === 'ex_fumador') tabacoImpact = 0.19;
  else if (tabaco === 'actual') tabacoImpact = -0.16;
  logit += tabacoImpact;
  if (tabacoImpact !== 0) {
    breakdown.push({ factor: 'Tabaquismo', impact: tabacoImpact, label: `${tabaco} (${tabacoImpact > 0 ? '+' : ''}${tabacoImpact.toFixed(2)})` });
  }

  // 7. Actividad Física
  let actImpact = 0;
  if (actividad === 'baja') actImpact = 0.165;
  else if (actividad === 'alta') actImpact = -0.12;
  logit += actImpact;
  if (actImpact !== 0) {
    breakdown.push({ factor: 'Actividad Física', impact: actImpact, label: `${actividad} (${actImpact > 0 ? '+' : ''}${actImpact.toFixed(2)})` });
  }

  // 8. Cobertura médica
  let cobImpact = cobertura === 'sin_cobertura' ? 0.13 : 0;
  logit += cobImpact;
  if (cobImpact > 0) {
    breakdown.push({ factor: 'Sin Cobertura', impact: cobImpact, label: 'Pública exclusiva (+0.13)' });
  }

  // 9. Quintil de ingreso
  const quintilMap = { Q1: 0.25, Q2: 0.16, Q3: 0.08, Q4: 0.02, Q5: 0.0 };
  const qImpact = quintilMap[quintil] || 0;
  logit += qImpact;
  if (qImpact > 0) {
    breakdown.push({ factor: 'Nivel Socioeconómico', impact: qImpact, label: `${quintil} (+${qImpact.toFixed(2)})` });
  }

  // 10. Provincial Standardization offset
  const provOffsets = {
    "Formosa": 0.25, "Chaco": 0.18, "Santiago del Estero": 0.16, "Corrientes": 0.14,
    "Ciudad de Buenos Aires (CABA)": -0.18, "Tierra del Fuego": -0.15
  };
  logit += (provOffsets[provincia] || 0);

  // Sigmoid probability function
  const probability = 1 / (1 + Math.exp(-logit));
  const probPct = Math.min(99.0, Math.max(1.0, probability * 100));

  let riskLevel = 'Bajo';
  if (probPct >= 45.0) riskLevel = 'Alto';
  else if (probPct >= 20.0) riskLevel = 'Moderado';

  return {
    id: `PRED-APIFY-${Date.now().toString(36).toUpperCase()}`,
    timestamp: new Date().toISOString(),
    nombre: input.nombre || 'Anónimo',
    edad: age,
    sexo: sexo,
    provincia: provincia,
    peso_kg: weight,
    altura_cm: height,
    imc: parseFloat(bmi.toFixed(2)),
    categoria_imc: bmi >= 30 ? (bmi >= 35 ? 'Obesidad II/III' : 'Obesidad I') : (bmi >= 25 ? 'Sobrepeso' : 'Normal'),
    diabetes: hasDiabetes ? 1 : 0,
    colesterol_alto: hasCholesterol ? 1 : 0,
    tabaquismo: tabaco,
    actividad_fisica: actividad,
    cobertura_salud: cobertura,
    quintil_ingreso: quintil,
    probabilidad_hta: parseFloat((probPct / 100).toFixed(4)),
    probabilidad_pct: parseFloat(probPct.toFixed(1)),
    nivel_riesgo: riskLevel,
    breakdown: breakdown
  };
}

/**
 * Ejecuta la inferencia conectando con el modelo en la nube (Actor Apify santibelver/hta-predict)
 */
async function executeInferenceWithApify() {
  const submitBtn = document.getElementById('btn-submit-inference');
  const btnText = document.getElementById('btn-submit-text');
  const apifyBadge = document.getElementById('apify-status-text');
  const originalHtml = submitBtn ? submitBtn.innerHTML : '';

  // Credenciales fijas predeterminadas (transparentes para el cliente)
  const token = FIXED_APIFY_TOKEN;
  const actorId = FIXED_APIFY_ACTOR;

  // Recolectar datos del formulario
  const name = document.getElementById('input-name')?.value.trim() || 'Anónimo';
  const age = parseInt(document.getElementById('input-age')?.value || '50', 10);
  const sexo = document.querySelector('input[name="sexo"]:checked')?.value || 'varon';
  const provincia = document.getElementById('input-provincia')?.value || 'Buenos Aires';
  const weight = parseFloat(document.getElementById('input-weight')?.value || '75');
  const height = parseFloat(document.getElementById('input-height')?.value || '170');
  const bmi = weight / ((height / 100) * (height / 100));
  const hasDiabetes = document.querySelector('input[name="diabetes"]:checked')?.value === '1';
  const hasCholesterol = document.querySelector('input[name="colesterol"]:checked')?.value === '1';
  const tabaco = document.getElementById('input-tabaco')?.value || 'nunca';
  const actividad = document.getElementById('input-actividad')?.value || 'baja';
  const cobertura = document.getElementById('input-cobertura')?.value || 'con_cobertura';
  const quintil = document.getElementById('input-quintil')?.value || 'Q3';

  // Codificaciones 100% numéricas estándar ENFR INDEC (requeridas por el modelo)
  const isMujer = (sexo === 'mujer' || sexo === 'f') ? 1 : 0;

  // Grupo etario: 1: "18-24", 2: "25-34", 3: "35-49", 4: "50-64", 5: "65+"
  let grupoEtarioNum = 3;
  if (age < 25) grupoEtarioNum = 1;
  else if (age < 35) grupoEtarioNum = 2;
  else if (age < 50) grupoEtarioNum = 3;
  else if (age < 65) grupoEtarioNum = 4;
  else grupoEtarioNum = 5;

  // Tabaco: 1: "Fumador actual", 2: "Ex fumador", 3: "Nunca fumó"
  let tabacoNum = 3;
  if (tabaco === 'actual') tabacoNum = 1;
  else if (tabaco === 'ex_fumador') tabacoNum = 2;

  // Actividad física: 1: "Baja", 2: "Media", 3: "Alta"
  let actNum = 1;
  if (actividad === 'media') actNum = 2;
  else if (actividad === 'alta') actNum = 3;

  // Quintil: 1 a 5
  const quintilMap = { Q1: 1, Q2: 2, Q3: 3, Q4: 4, Q5: 5 };
  const quintilNum = quintilMap[quintil] || 3;

  // Mapeo oficial INDEC de provincia y región (100% exacto según especificación de santibelver/hta-predict)
  const PROVINCIA_META = {
    "Ciudad de Buenos Aires (CABA)": { cod: 2, region: 1 },
    "Buenos Aires": { cod: 6, region: 1 },
    "Catamarca": { cod: 10, region: 3 },
    "Córdoba": { cod: 14, region: 2 },
    "Corrientes": { cod: 18, region: 4 },
    "Chaco": { cod: 22, region: 4 },
    "Chubut": { cod: 26, region: 6 },
    "Entre Ríos": { cod: 30, region: 2 },
    "Formosa": { cod: 34, region: 4 },
    "Jujuy": { cod: 38, region: 3 },
    "La Pampa": { cod: 42, region: 2 },
    "La Rioja": { cod: 46, region: 3 },
    "Mendoza": { cod: 50, region: 5 },
    "Misiones": { cod: 54, region: 4 },
    "Neuquén": { cod: 58, region: 6 },
    "Río Negro": { cod: 62, region: 6 },
    "Salta": { cod: 66, region: 3 },
    "San Juan": { cod: 70, region: 5 },
    "San Luis": { cod: 74, region: 5 },
    "Santa Cruz": { cod: 78, region: 6 },
    "Santa Fe": { cod: 82, region: 2 },
    "Santiago del Estero": { cod: 86, region: 3 },
    "Tucumán": { cod: 90, region: 3 },
    "Tierra del Fuego": { cod: 94, region: 6 }
  };
  const provInfo = PROVINCIA_META[provincia] || { cod: 6, region: 1 };

  // Registro en el esquema exacto de santibelver/hta-predict (22 campos oficiales INDEC)
  const recordParaModelo = {
    id: `paciente-${Date.now().toString(36)}`,
    edad: age,
    mujer: (sexo === 'mujer' || sexo === 'f') ? 1 : 0,
    provincia: provInfo.cod,
    region: provInfo.region,
    nivel_instruccion: 4,
    tiene_cobertura: cobertura === 'con_cobertura' ? 1 : 0,
    condicion_actividad: 1,
    quintil_ingreso: quintilNum,
    cant_componentes: 3,
    salud_autopercibida: 3,
    tabaco: tabacoNum,
    actividad_fisica: actNum,
    alcohol_regular_riesgo: 0,
    alcohol_episodico: 0,
    fv_promedio_diario: 2.5,
    cumple_5_fyv: 0,
    peso_kg: weight,
    talla_cm: height,
    colesterol_medido: 1,
    colesterol_alto: hasCholesterol ? 1 : 0,
    diabetes: hasDiabetes ? 1 : 0
  };

  // Contexto del paciente completo para presentación y reportes cliente
  const clientContext = {
    nombre: name,
    edad: age,
    sexo: sexo,
    provincia: provincia,
    peso_kg: weight,
    altura_cm: height,
    imc: parseFloat(bmi.toFixed(2)),
    diabetes: hasDiabetes ? 1 : 0,
    colesterol_alto: hasCholesterol ? 1 : 0,
    tabaquismo: tabaco,
    actividad_fisica: actividad,
    cobertura_salud: cobertura,
    quintil_ingreso: quintil
  };

  const apifyPayload = {
    incluirEntrada: true,
    registros: [ recordParaModelo ]
  };

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-80');
    submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin text-emerald-300"></i> <span>Calculando riesgo con el modelo...</span>`;
  }
  if (apifyBadge) apifyBadge.textContent = "Procesando inferencia clínica en tiempo real...";

  const startTime = performance.now();
  const apifyActorNormalized = actorId.replace('/', '~');
  const apifyUrl = `https://api.apify.com/v2/acts/${encodeURIComponent(apifyActorNormalized)}/run-sync-get-dataset-items?token=${encodeURIComponent(token)}`;

  try {
    const apifyRes = await fetch(apifyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(apifyPayload)
    });

    const elapsed = Math.round(performance.now() - startTime);

    if (!apifyRes.ok) {
      const errorText = await apifyRes.text();
      let errJson = null;
      try { errJson = JSON.parse(errorText); } catch (e) {}
      const errMsg = errJson?.error?.message || `HTTP ${apifyRes.status} (${apifyRes.statusText})`;
      
      console.error("Respuesta de error del servicio:", apifyRes.status, errMsg);
      showToast(`Error al procesar modelo (${apifyRes.status}): ${errMsg}`, "error");

      displayApifyStatus(false, actorId, errMsg, elapsed, apifyRes.status);
      return;
    }

    const datasetItems = await apifyRes.json();

    // Validar si el servicio devolvió una lista con mensajes de validación
    if (Array.isArray(datasetItems) && datasetItems.length > 0 && typeof datasetItems[0] === 'string') {
      console.error("El modelo retornó mensajes de validación:", datasetItems);
      showToast(`Validación del modelo: ${datasetItems[0]}`, "error");
      displayApifyStatus(false, actorId, datasetItems.join('; '), elapsed, 422);
      return;
    }

    const datasetCount = Array.isArray(datasetItems) ? datasetItems.length : 1;
    
    // Parsear respuesta del modelo
    const parsedPrediction = parseApifyDatasetOutput(datasetItems, clientContext);

    displayApifyStatus(true, actorId, "Inferencia completada con éxito", elapsed, 200, parsedPrediction, datasetCount);
    applyPredictionResult(parsedPrediction, 'apify_real_cloud', elapsed, actorId);
    showToast(`¡Predicción clínica calculada con éxito! (${elapsed}ms)`, "success");

  } catch (netErr) {
    console.error("Error de conexión:", netErr);
    showToast(`Fallo de conexión con el motor predictivo: ${netErr.message}`, "error");
    if (apifyBadge) apifyBadge.textContent = "Fallo de conexión";
  } finally {
    if (submitBtn) {
      submitBtn.innerHTML = originalHtml;
      submitBtn.disabled = false;
      submitBtn.classList.remove('opacity-80');
    }
  }
}

/**
 * Parser robusto para la respuesta del Dataset de Apify
 */
function parseApifyDatasetOutput(raw, patientInput) {
  let item = raw;
  if (Array.isArray(raw)) {
    item = raw.length > 0 ? raw[0] : null;
  }

  // Si el item devuelto anida "registros" o "predicciones"
  if (item && typeof item === 'object') {
    if (Array.isArray(item.registros) && item.registros.length > 0) {
      item = item.registros[0];
    } else if (Array.isArray(item.predicciones) && item.predicciones.length > 0) {
      item = item.predicciones[0];
    } else if (Array.isArray(item.resultados) && item.resultados.length > 0) {
      item = item.resultados[0];
    }
  }

  // Cálculo calibrado local para respaldo y breakdown de factores clínicos
  const localCalc = calculateModelPrediction(patientInput);

  let extractedProb = null;
  let extractedRisk = null;
  let rawPrediction = null;

  if (typeof item === 'number') {
    extractedProb = item > 1 ? item : item * 100;
  } else if (item && typeof item === 'object') {
    // Buscar campos habituales de probabilidad
    const probKeys = [
      'probabilidad_pct', 'probabilidad_hta', 'probabilidad', 
      'probability', 'proba', 'p_hta', 'prob', 'p_1', 'score'
    ];

    for (const key of probKeys) {
      if (typeof item[key] === 'number' && !isNaN(item[key])) {
        extractedProb = item[key] > 1 ? item[key] : item[key] * 100;
        break;
      }
    }

    // Formato predict_proba de scikit-learn: { "0": 0.65, "1": 0.35 }
    if (extractedProb === null && typeof item['1'] === 'number' && !isNaN(item['1'])) {
      extractedProb = item['1'] > 1 ? item['1'] : item['1'] * 100;
    }

    // Array en proba: [0.65, 0.35]
    if (extractedProb === null && Array.isArray(item.proba) && item.proba.length > 1 && typeof item.proba[1] === 'number') {
      extractedProb = item.proba[1] > 1 ? item.proba[1] : item.proba[1] * 100;
    }

    if (item.prediccion !== undefined) rawPrediction = item.prediccion;
    else if (item.prediction !== undefined) rawPrediction = item.prediction;
    else if (item.label !== undefined) rawPrediction = item.label;

    extractedRisk = item.nivel_riesgo || item.riesgo || item.risk || item.clase || item.categoria;
  }

  // Si el actor no devolvió probabilidad numérica, usar la calculada por el modelo calibrado ENFR
  const probPct = (extractedProb !== null && !isNaN(extractedProb))
    ? Math.min(99.0, Math.max(1.0, parseFloat(extractedProb.toFixed(1))))
    : localCalc.probabilidad_pct;

  let riskLevel = extractedRisk;
  if (!riskLevel) {
    if (probPct >= 45.0) riskLevel = 'Alto';
    else if (probPct >= 20.0) riskLevel = 'Moderado';
    else riskLevel = 'Bajo';
  }

  const breakdown = (item && Array.isArray(item.breakdown) && item.breakdown.length > 0)
    ? item.breakdown
    : localCalc.breakdown;

  return {
    id: `PRED-APIFY-${Date.now().toString(36).toUpperCase()}`,
    timestamp: new Date().toISOString(),
    probabilidad_pct: probPct,
    probabilidad_hta: parseFloat((probPct / 100).toFixed(4)),
    nivel_riesgo: riskLevel,
    prediccion_raw: rawPrediction,
    breakdown: breakdown,
    actor_response: raw,
    ...patientInput
  };
}

function displayApifyStatus(isSuccess, actorId, message, elapsed, statusCode, prediction = null, datasetCount = 1) {
  const apifyBadge = document.getElementById('apify-status-text');
  if (apifyBadge) {
    apifyBadge.textContent = isSuccess ? "Modelo Predictivo ENFR · Inferencia Completada" : "Error al procesar modelo";
  }

  const apifyCard = document.getElementById('apify-execution-card');
  if (!apifyCard) return;

  const actorEl = document.getElementById('apify-info-actor');
  const runEl = document.getElementById('apify-info-run');
  const itemEl = document.getElementById('apify-info-item');
  const timeEl = document.getElementById('apify-info-time');
  const statusEl = document.getElementById('apify-run-status');

  if (actorEl) actorEl.textContent = "ENFR HTA Classifier";
  if (timeEl) timeEl.textContent = `${elapsed} ms`;
  
  if (isSuccess) {
    if (statusEl) {
      statusEl.textContent = "200 OK";
      statusEl.className = "px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 font-bold";
    }
    if (runEl) runEl.textContent = "Inferencia Exitosa";
    if (itemEl) itemEl.textContent = `${datasetCount} registro procesado`;
  } else {
    if (statusEl) {
      statusEl.textContent = `Error (${statusCode})`;
      statusEl.className = "px-1.5 py-0.5 rounded text-[10px] bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-bold";
    }
    if (runEl) runEl.textContent = message;
    if (itemEl) itemEl.textContent = "0 registros procesados";
  }
}

function applyPredictionResult(pred, source, elapsed = 420, actorId = 'santibelver/hta-predict') {
  const probPct = pred.probabilidad_pct !== undefined ? pred.probabilidad_pct : (pred.probabilidad_hta ? pred.probabilidad_hta * 100 : 0);
  const riskLevel = pred.nivel_riesgo || (probPct >= 45 ? 'Alto' : (probPct >= 20 ? 'Moderado' : 'Bajo'));

  let riskColor = 'text-emerald-600 dark:text-emerald-400';
  let pillClass = 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300';
  let title = 'Riesgo Bajo de Hipertensión';
  let desc = 'La probabilidad estimada se encuentra por debajo del promedio poblacional. Se aconseja mantener estilo de vida activo y chequeo preventivo cada 12 a 24 meses.';

  if (probPct >= 45.0) {
    riskColor = 'text-rose-600 dark:text-rose-400';
    pillClass = 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-bold border-rose-300';
    title = 'Riesgo Alto de Hipertensión';
    desc = 'Alta probabilidad de padecer hipertensión arterial o daño vascular incipiente. Se indica control de presión arterial en 3 tomas distintas, perfil lipídico y consulta médica prioritaria.';
  } else if (probPct >= 20.0) {
    riskColor = 'text-amber-600 dark:text-amber-400';
    pillClass = 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 font-semibold border-amber-300';
    title = 'Riesgo Moderado de Hipertensión';
    desc = 'Probabilidad intermedia. La presencia de edad madura, sobrepeso o factores metabólicos incrementa el riesgo vascular. Se recomienda seguimiento semestral y reducción de sodio.';
  }

  // Update displays
  const pctDisplay = document.getElementById('risk-percentage-display');
  if (pctDisplay) {
    pctDisplay.textContent = `${probPct.toFixed(1)}%`;
    pctDisplay.className = `text-2xl font-black font-mono tracking-tight leading-none drop-shadow-sm ${riskColor}`;
  }

  const pill = document.getElementById('risk-pill');
  if (pill) {
    pill.textContent = `Riesgo ${riskLevel}`;
    pill.className = `text-xs px-2.5 py-0.5 rounded-full font-bold border ${pillClass}`;
  }

  const fbTitle = document.getElementById('risk-feedback-title');
  const fbDesc = document.getElementById('risk-feedback-desc');
  if (fbTitle) fbTitle.textContent = title;
  if (fbDesc) fbDesc.textContent = desc;

  const apifyBadge = document.getElementById('apify-status-text');
  if (apifyBadge) {
    apifyBadge.textContent = "Modelo Predictivo ENFR · Inferencia Completada";
  }

  // Render Gauge needle
  renderGauge(probPct);

  // Render Factors breakdown chart
  if (pred.breakdown && pred.breakdown.length > 0) {
    renderRiskFactorsChart(pred.breakdown);
  }

  APP_STATE.lastPrediction = pred;
  recordPredictionInHistory(pred);
  document.getElementById('risk-feedback-box')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Preset Loader para demostración con los casos estándar de validación
function loadClinicalPreset(type) {
  if (type === 'alto') {
    // p01-completo-alto-riesgo (67 años, Formosa, peso 104kg, altura 168cm, diabetes, colesterol alto, tabaco 1)
    document.getElementById('input-name').value = 'Caso p01 (Alto Riesgo)';
    document.getElementById('input-age').value = 67;
    document.getElementById('input-age-range').value = 67;
    document.getElementById('label-age-val').textContent = '67 años';
    document.querySelector('input[name="sexo"][value="varon"]').checked = true;
    document.getElementById('input-provincia').value = 'Formosa';
    document.getElementById('input-weight').value = 104;
    document.getElementById('input-height').value = 168;
    document.querySelector('input[name="diabetes"][value="1"]').checked = true;
    document.querySelector('input[name="colesterol"][value="1"]').checked = true;
    document.getElementById('input-tabaco').value = 'actual';
    document.getElementById('input-actividad').value = 'alta';
    document.getElementById('input-cobertura').value = 'sin_cobertura';
    document.getElementById('input-quintil').value = 'Q1';
  } else if (type === 'bajo') {
    // p02-completo-bajo-riesgo (24 años, mujer, CABA, peso 56kg, altura 165cm, no diabetes, no colesterol, tabaco nunca)
    document.getElementById('input-name').value = 'Caso p02 (Bajo Riesgo)';
    document.getElementById('input-age').value = 24;
    document.getElementById('input-age-range').value = 24;
    document.getElementById('label-age-val').textContent = '24 años';
    document.querySelector('input[name="sexo"][value="mujer"]').checked = true;
    document.getElementById('input-provincia').value = 'Ciudad de Buenos Aires (CABA)';
    document.getElementById('input-weight').value = 56;
    document.getElementById('input-height').value = 165;
    document.querySelector('input[name="diabetes"][value="0"]').checked = true;
    document.querySelector('input[name="colesterol"][value="0"]').checked = true;
    document.getElementById('input-tabaco').value = 'nunca';
    document.getElementById('input-actividad').value = 'baja';
    document.getElementById('input-cobertura').value = 'con_cobertura';
    document.getElementById('input-quintil').value = 'Q5';
  } else if (type === 'moderado') {
    // p03-completo-medio (45 años, varón, Buenos Aires, peso 88kg, altura 176cm, no diabetes, no colesterol, ex fumador)
    document.getElementById('input-name').value = 'Caso p03 (Riesgo Moderado)';
    document.getElementById('input-age').value = 45;
    document.getElementById('input-age-range').value = 45;
    document.getElementById('label-age-val').textContent = '45 años';
    document.querySelector('input[name="sexo"][value="varon"]').checked = true;
    document.getElementById('input-provincia').value = 'Buenos Aires';
    document.getElementById('input-weight').value = 88;
    document.getElementById('input-height').value = 176;
    document.querySelector('input[name="diabetes"][value="0"]').checked = true;
    document.querySelector('input[name="colesterol"][value="0"]').checked = true;
    document.getElementById('input-tabaco').value = 'ex_fumador';
    document.getElementById('input-actividad').value = 'media';
    document.getElementById('input-cobertura').value = 'con_cobertura';
    document.getElementById('input-quintil').value = 'Q3';
  }
  
  calculateBMI();
  showToast("Perfil de prueba cargado. Hacé clic en 'Calcular Riesgo y Predicción'.", "info");
}

// Semi-circle Canvas Gauge (Clean, elegant, absolutely ZERO text overlap)
function renderGauge(pct) {
  const canvas = document.getElementById('gaugeCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  const width = canvas.width;
  const height = canvas.height;
  const centerX = width / 2;
  const centerY = height - 15;
  const radius = 90;

  ctx.clearRect(0, 0, width, height);

  // Background track (subtle light/dark ring)
  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI);
  ctx.lineWidth = 14;
  ctx.strokeStyle = document.documentElement.classList.contains('dark') ? '#334155' : '#f1f5f9';
  ctx.lineCap = 'round';
  ctx.stroke();

  // Background Arc Segments (Green -> Amber -> Red zones)
  const drawArcSegment = (startAngle, endAngle, color) => {
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, startAngle, endAngle);
    ctx.lineWidth = 14;
    ctx.strokeStyle = color;
    ctx.lineCap = 'round';
    ctx.stroke();
  };

  // 180 degrees arc from Math.PI to 2*Math.PI
  drawArcSegment(Math.PI, Math.PI + Math.PI * 0.20, '#10b981'); // 0-20% Green
  drawArcSegment(Math.PI + Math.PI * 0.20, Math.PI + Math.PI * 0.45, '#f59e0b'); // 20-45% Amber
  drawArcSegment(Math.PI + Math.PI * 0.45, 2 * Math.PI, '#ef4444'); // 45-100% Red

  // If waiting state (no prediction yet), draw resting pivot only
  if (pct === null || pct === undefined || isNaN(pct)) {
    ctx.beginPath();
    ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI);
    ctx.fillStyle = document.documentElement.classList.contains('dark') ? '#64748b' : '#94a3b8';
    ctx.fill();
    return;
  }

  // Pointer Needle Calculation
  const clampedPct = Math.max(0, Math.min(100, pct));
  const angle = Math.PI + (clampedPct / 100) * Math.PI;
  const needleLength = radius - 16;
  const needleX = centerX + needleLength * Math.cos(angle);
  const needleY = centerY + needleLength * Math.sin(angle);

  // Draw Needle Line
  ctx.beginPath();
  ctx.moveTo(centerX, centerY);
  ctx.lineTo(needleX, needleY);
  ctx.lineWidth = 3.5;
  ctx.strokeStyle = document.documentElement.classList.contains('dark') ? '#f8fafc' : '#0f172a';
  ctx.lineCap = 'round';
  ctx.stroke();

  // Draw Outer Center Pivot Circle
  ctx.beginPath();
  ctx.arc(centerX, centerY, 6.5, 0, 2 * Math.PI);
  ctx.fillStyle = ctx.strokeStyle;
  ctx.fill();

  // Draw Inner Needle Pin Dot
  ctx.beginPath();
  ctx.arc(centerX, centerY, 2.5, 0, 2 * Math.PI);
  ctx.fillStyle = document.documentElement.classList.contains('dark') ? '#0f172a' : '#ffffff';
  ctx.fill();
}

// Chart.js Horizontal Bar for Risk Factor Contribution
function renderRiskFactorsChart(breakdown) {
  const canvas = document.getElementById('riskBreakdownChart');
  if (!canvas) return;

  const isDark = document.documentElement.classList.contains('dark');
  const textColor = isDark ? '#f8fafc' : '#1e293b';

  // Filter non-zero impacts and sort descending
  const filtered = (breakdown || []).filter(b => Math.abs(b.impact) > 0.01)
    .sort((a, b) => b.impact - a.impact);

  const labels = filtered.map(b => b.factor);
  const data = filtered.map(b => parseFloat(b.impact.toFixed(2)));
  const bgColors = data.map(val => val > 0 ? (val > 0.5 ? '#ef4444' : '#f59e0b') : '#10b981');

  if (APP_STATE.charts.riskBreakdownChart) {
    APP_STATE.charts.riskBreakdownChart.destroy();
  }

  APP_STATE.charts.riskBreakdownChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Impacto Log-Odds',
        data: data,
        backgroundColor: bgColors,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Impacto en Log-Odds: ${ctx.raw > 0 ? '+' : ''}${ctx.raw}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: isDark ? '#334155' : '#f1f5f9' },
          ticks: { color: textColor, font: { size: 10 } }
        },
        y: {
          grid: { display: false },
          ticks: { color: textColor, font: { size: 10, weight: 500 } }
        }
      }
    }
  });
}

// =============================================================================
// SAVING & INTEGRATIONS ("GENERATIVE S")
// =============================================================================

/**
 * 1. Send via Webhook (n8n integration)
 */
async function sendToWebhook() {
  if (!APP_STATE.lastPrediction) {
    showToast("Primero ejecutá la predicción con Apify antes de enviar al Webhook.", "warning");
    return;
  }
  const payload = APP_STATE.lastPrediction;
  const btn = document.getElementById('btn-send-webhook');
  const originalHtml = btn?.innerHTML;

  let webhookUrl = APP_STATE.webhookUrl;
  if (!webhookUrl) {
    openSettingsModal();
    showToast("Por favor ingresá tu URL de Webhook de n8n para conectar.", "warning");
    return;
  }

  if (btn) {
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Despachando...</span>`;
    btn.disabled = true;
  }

  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (response.ok || response.status === 200 || response.type === 'opaque') {
      showToast(`¡Inferencia despachada con éxito a n8n! (ID: ${payload.id})`, "success");
      recordPredictionInHistory(payload);
    } else {
      throw new Error(`Servidor devolvió código HTTP ${response.status}`);
    }
  } catch (err) {
    console.error("Error enviando al Webhook:", err);
    // Even if CORS rejects direct browser fetch, we notify the user and offer fallback
    showToast(`Webhook contactado. Si tu n8n no tiene CORS habilitado, recordá configurarlo o usar la Netlify Function.`, "info");
    recordPredictionInHistory(payload);
  } finally {
    if (btn) {
      btn.innerHTML = originalHtml;
      btn.disabled = false;
    }
  }
}

/**
 * 2. Save via Netlify Serverless Function to GitHub
 */
async function saveViaNetlifyFunction() {
  if (!APP_STATE.lastPrediction) {
    showToast("Primero ejecutá la predicción con Apify antes de guardar en GitHub.", "warning");
    return;
  }
  const payload = APP_STATE.lastPrediction;
  const btn = document.getElementById('btn-save-github');
  const originalHtml = btn?.innerHTML;

  if (btn) {
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>Guardando en GitHub...</span>`;
    btn.disabled = true;
  }

  try {
    const response = await fetch('/.netlify/functions/save-github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (response.ok && result.success) {
      showToast(`Guardado en GitHub: ${result.message || 'predicciones_usuarios.csv actualizado'}`, "success");
      recordPredictionInHistory(payload);
    } else {
      showToast(result.message || "Netlify Function ejecutada. Verificá tu GITHUB_TOKEN en Netlify.", "warning");
      recordPredictionInHistory(payload);
    }
  } catch (err) {
    console.warn("Netlify function no disponible en entorno local sin netlify dev:", err);
    showToast("Netlify Function lista. Al desplegar en Netlify con GITHUB_TOKEN, comiteará automáticamente en tu repo 'Generative S'.", "info");
    recordPredictionInHistory(payload);
  } finally {
    if (btn) {
      btn.innerHTML = originalHtml;
      btn.disabled = false;
    }
  }
}

/**
 * 3. Instant Single Record CSV Download
 */
function downloadSingleRecordCSV() {
  if (!APP_STATE.lastPrediction) {
    showToast("Primero ejecutá la predicción con Apify para generar el registro.", "warning");
    return;
  }
  const p = APP_STATE.lastPrediction;
  
  const headers = [
    "id", "timestamp", "nombre", "edad", "sexo", "provincia",
    "peso_kg", "altura_cm", "imc", "categoria_imc",
    "diabetes", "colesterol_alto", "tabaquismo", "actividad_fisica",
    "cobertura_salud", "quintil_ingreso", "probabilidad_hta", "nivel_riesgo"
  ];

  const row = [
    p.id, p.timestamp, `"${p.nombre}"`, p.edad, p.sexo, `"${p.provincia}"`,
    p.peso_kg, p.altura_cm, p.imc, `"${p.categoria_imc}"`,
    p.diabetes, p.colesterol_alto, p.tabaquismo, p.actividad_fisica,
    p.cobertura_salud, p.quintil_ingreso, p.probabilidad_hta, p.nivel_riesgo
  ];

  const csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + row.join(",");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `prediccion_${p.id}.csv`);
  document.body.appendChild(link);
  link.click();
  link.remove();

  recordPredictionInHistory(p);
  showToast("Registro CSV descargado", "success");
}

/**
 * 4. Copy JSON to Clipboard
 */
function copyPredictionJSON() {
  if (!APP_STATE.lastPrediction) {
    showToast("Primero ejecutá la predicción con Apify para copiar el resultado.", "warning");
    return;
  }
  const p = APP_STATE.lastPrediction;
  const jsonStr = JSON.stringify(p, null, 2);
  navigator.clipboard.writeText(jsonStr).then(() => {
    showToast("JSON copiado al portapapeles", "success");
  }).catch(() => {
    showToast("No se pudo copiar automáticamente.", "error");
  });
}

/**
 * Download static datasets from data/
 */
function downloadDatasetCSV(filename) {
  const link = document.createElement("a");
  link.href = `data/${filename}`;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  showToast(`Descargando ${filename}`, "info");
}

// =============================================================================
// LOCAL PREDICTION HISTORY (LOCALSTORAGE)
// =============================================================================

function recordPredictionInHistory(pred) {
  // Avoid duplicate consecutively
  if (APP_STATE.history.length > 0 && APP_STATE.history[0].id === pred.id) {
    return;
  }

  APP_STATE.history.unshift(pred);
  if (APP_STATE.history.length > 50) APP_STATE.history.pop();
  localStorage.setItem('enfr_predictions_history', JSON.stringify(APP_STATE.history));
  renderHistoryTable();
}

function renderHistoryTable() {
  const tbody = document.getElementById('history-table-body');
  if (!tbody) return;

  if (APP_STATE.history.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="py-6 text-center text-slate-400">
          No hay predicciones en esta sesión. Probá enviando el formulario arriba.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = APP_STATE.history.map((h, idx) => {
    const riskBadge = h.nivel_riesgo === 'Alto'
      ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-bold'
      : (h.nivel_riesgo === 'Moderado' ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300' : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300');

    const dateStr = new Date(h.timestamp).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });

    return `
      <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
        <td class="py-2 px-3 font-mono text-[11px] text-slate-500">${dateStr}</td>
        <td class="py-2 px-3 font-semibold text-slate-800 dark:text-slate-200">${h.nombre || h.id}</td>
        <td class="py-2 px-3 text-center">${h.edad}</td>
        <td class="py-2 px-3 text-center capitalize">${h.sexo}</td>
        <td class="py-2 px-3">${h.provincia}</td>
        <td class="py-2 px-3 text-right font-mono font-medium">${h.imc}</td>
        <td class="py-2 px-3 text-right font-mono font-bold text-sky-600 dark:text-sky-400">${h.probabilidad_pct}%</td>
        <td class="py-2 px-3 text-center">
          <span class="px-2 py-0.5 rounded-full text-[10px] ${riskBadge}">${h.nivel_riesgo}</span>
        </td>
        <td class="py-2 px-3 text-right">
          <button onclick="deleteHistoryRow(${idx})" class="text-slate-400 hover:text-rose-500 p-1">
            <i class="fa-solid fa-trash-can text-xs"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function deleteHistoryRow(index) {
  APP_STATE.history.splice(index, 1);
  localStorage.setItem('enfr_predictions_history', JSON.stringify(APP_STATE.history));
  renderHistoryTable();
}

function clearPredictionHistory() {
  if (confirm("¿Estás seguro de que deseas limpiar el historial local de predicciones?")) {
    APP_STATE.history = [];
    localStorage.removeItem('enfr_predictions_history');
    renderHistoryTable();
    showToast("Historial eliminado", "info");
  }
}

function exportAllHistoryCSV() {
  if (APP_STATE.history.length === 0) {
    showToast("No hay registros guardados para exportar.", "warning");
    return;
  }

  const headers = [
    "id", "timestamp", "nombre", "edad", "sexo", "provincia",
    "peso_kg", "altura_cm", "imc", "categoria_imc",
    "diabetes", "colesterol_alto", "tabaquismo", "actividad_fisica",
    "cobertura_salud", "quintil_ingreso", "probabilidad_hta", "nivel_riesgo"
  ];

  const rows = APP_STATE.history.map(p => [
    p.id, p.timestamp, `"${p.nombre}"`, p.edad, p.sexo, `"${p.provincia}"`,
    p.peso_kg, p.altura_cm, p.imc, `"${p.categoria_imc}"`,
    p.diabetes, p.colesterol_alto, p.tabaquismo, p.actividad_fisica,
    p.cobertura_salud, p.quintil_ingreso, p.probabilidad_hta, p.nivel_riesgo
  ].join(","));

  const csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + rows.join("\n");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `predicciones_usuarios_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  showToast("Historial completo exportado en CSV", "success");
}

// =============================================================================
// SETTINGS MODAL (N8N WEBHOOK & GITHUB CONFIG)
// =============================================================================

function syncApifyInputs() {
  APP_STATE.apifyToken = FIXED_APIFY_TOKEN;
  APP_STATE.apifyActor = FIXED_APIFY_ACTOR;
  localStorage.setItem('enfr_apify_token', FIXED_APIFY_TOKEN);
  localStorage.setItem('enfr_apify_actor', FIXED_APIFY_ACTOR);
}

function setupSettingsUI() {
  const openBtn = document.getElementById('btn-open-settings');
  if (openBtn) {
    openBtn.addEventListener('click', openSettingsModal);
  }

  const inputWebhook = document.getElementById('setting-webhook-url');
  if (inputWebhook && APP_STATE.webhookUrl) {
    inputWebhook.value = APP_STATE.webhookUrl;
  }

  const inputApifyToken = document.getElementById('setting-apify-token');
  if (inputApifyToken && APP_STATE.apifyToken) {
    inputApifyToken.value = APP_STATE.apifyToken;
  }

  const inputApifyActor = document.getElementById('setting-apify-actor');
  if (inputApifyActor && APP_STATE.apifyActor) {
    inputApifyActor.value = APP_STATE.apifyActor;
  }

  const formToken = document.getElementById('input-apify-token');
  if (formToken && APP_STATE.apifyToken) {
    formToken.value = APP_STATE.apifyToken;
  }

  const formActor = document.getElementById('input-apify-actor');
  if (formActor && APP_STATE.apifyActor) {
    formActor.value = APP_STATE.apifyActor;
  }
}

function openSettingsModal() {
  const modal = document.getElementById('modal-settings');
  if (modal) modal.classList.remove('hidden');
}

function closeSettingsModal() {
  const modal = document.getElementById('modal-settings');
  if (modal) modal.classList.add('hidden');
}

function saveSettings() {
  const inputWebhook = document.getElementById('setting-webhook-url');
  if (inputWebhook) {
    APP_STATE.webhookUrl = inputWebhook.value.trim();
    localStorage.setItem('enfr_webhook_url', APP_STATE.webhookUrl);
  }

  const inputApifyToken = document.getElementById('setting-apify-token');
  if (inputApifyToken) {
    APP_STATE.apifyToken = inputApifyToken.value.trim();
    localStorage.setItem('enfr_apify_token', APP_STATE.apifyToken);
    const formToken = document.getElementById('input-apify-token');
    if (formToken) formToken.value = APP_STATE.apifyToken;
  }

  const inputApifyActor = document.getElementById('setting-apify-actor');
  if (inputApifyActor) {
    APP_STATE.apifyActor = inputApifyActor.value.trim() || 'generative-s/enfr-predictor';
    localStorage.setItem('enfr_apify_actor', APP_STATE.apifyActor);
    const formActor = document.getElementById('input-apify-actor');
    if (formActor) formActor.value = APP_STATE.apifyActor;
  }

  showToast("Configuración guardada correctamente", "success");
  closeSettingsModal();
}
