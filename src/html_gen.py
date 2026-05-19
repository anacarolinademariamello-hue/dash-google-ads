"""
html_gen.py — Gerador de relatório HTML para Google Ads.

Mesmo estilo visual dos outros apps da Dash Digital (dash-relatorios-app).
Gera relatório completo standalone com Chart.js 4.4.0.
"""
from __future__ import annotations

import json
from datetime import datetime


# ── Helpers ────────────────────────────────────────────────────────────────────

def _br(v, decimals: int = 0) -> str:
    """Formata número no padrão pt-BR."""
    try:
        s = f"{float(v):,.{decimals}f}" if decimals else f"{int(round(float(v))):,}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


def _js(v) -> str:
    """Serializa para JSON seguro (arrays, strings)."""
    return json.dumps(v, ensure_ascii=False)


# ── Seções do relatório ────────────────────────────────────────────────────────

def _header(client: dict, data: dict, generated_at: str) -> str:
    name   = client.get("name", "")
    industry = client.get("industry", "")
    period = data.get("period_label", "")
    days   = data.get("days", 0)
    return f"""
  <div class="report-header">
    <div class="header-content">
      <div class="header-icon">📊</div>
      <div>
        <h1 class="client-name">{name}</h1>
        {f'<div class="client-industry">{industry}</div>' if industry else ''}
        <div class="header-meta">
          <span class="meta-badge">📅 {period}</span>
          <span class="meta-badge">{days} dias</span>
          <span class="meta-badge">Google Ads</span>
        </div>
      </div>
    </div>
    <div class="generated-at">Relatório gerado em {generated_at} · Dash Digital</div>
  </div>"""


def _kpis(data: dict) -> str:
    imp       = _br(data.get("total_impressions", 0))
    clicks    = _br(data.get("total_clicks", 0))
    ctr       = _br(data.get("avg_ctr", 0), 2)
    cost      = _br(data.get("total_cost", 0), 2)
    cpc       = _br(data.get("avg_cpc", 0), 2)
    conv      = _br(data.get("total_conversions", 0), 1)
    conv_rate = _br(data.get("conv_rate", 0), 2)
    cpa       = data.get("cost_per_conv", 0)
    roas      = data.get("avg_roas", 0)

    cpa_card = ""
    if cpa and cpa > 0:
        cpa_card = f"""
    <div class="kpi-card">
      <span class="kpi-icon">💰</span>
      <div class="kpi-val">R${_br(cpa, 2)}</div>
      <div class="kpi-label">CPA</div>
      <span class="kpi-badge badge-orange">custo por convers&#227;o</span>
    </div>"""

    roas_card = ""
    if roas and roas > 0:
        roas_card = f"""
    <div class="kpi-card">
      <span class="kpi-icon">📊</span>
      <div class="kpi-val">{_br(roas, 2)}x</div>
      <div class="kpi-label">ROAS</div>
      <span class="kpi-badge badge-green">retorno sobre investimento</span>
    </div>"""

    return f"""
  <section class="section">
    <h2 class="section-title">&#128200; M&#233;tricas do Per&#237;odo</h2>
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-icon">👁️</span>
        <div class="kpi-val">{imp}</div>
        <div class="kpi-label">Impress&#245;es</div>
        <span class="kpi-badge badge-blue">visualiza&#231;&#245;es do an&#250;ncio</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">🖱️</span>
        <div class="kpi-val">{clicks}</div>
        <div class="kpi-label">Cliques</div>
        <span class="kpi-badge badge-blue">visitas geradas</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">🎯</span>
        <div class="kpi-val">{ctr}%</div>
        <div class="kpi-label">CTR</div>
        <span class="kpi-badge badge-green">taxa de clique</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">💵</span>
        <div class="kpi-val">R${cost}</div>
        <div class="kpi-label">Investimento</div>
        <span class="kpi-badge badge-orange">custo total</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">🏷️</span>
        <div class="kpi-val">R${cpc}</div>
        <div class="kpi-label">CPC M&#233;dio</div>
        <span class="kpi-badge badge-blue">custo por clique</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">✅</span>
        <div class="kpi-val">{conv}</div>
        <div class="kpi-label">Convers&#245;es</div>
        <span class="kpi-badge badge-green">{conv_rate}% taxa de conv.</span>
      </div>
      {cpa_card}
      {roas_card}
    </div>
  </section>"""


def _daily_charts(data: dict) -> str:
    labels    = data.get("daily_labels", [])
    if not labels:
        return ""  # sem breakdown diário → não mostra esta seção

    impressions = data.get("daily_impressions", [])
    clicks      = data.get("daily_clicks", [])
    cost        = data.get("daily_cost", [])
    conversions = data.get("daily_conversions", [])

    return f"""
  <section class="section">
    <h2 class="section-title">&#128197; Evolu&#231;&#227;o Di&#225;ria</h2>

    <div class="chart-container">
      <div class="chart-title">Impress&#245;es e Cliques por Dia</div>
      <canvas id="chartDaily" height="90"></canvas>
    </div>

    <div class="chart-container" style="margin-top:24px;">
      <div class="chart-title">Investimento Di&#225;rio (R$)</div>
      <canvas id="chartCost" height="70"></canvas>
    </div>

    {f'''<div class="chart-container" style="margin-top:24px;">
      <div class="chart-title">Convers&#245;es por Dia</div>
      <canvas id="chartConv" height="70"></canvas>
    </div>''' if any(v > 0 for v in conversions) else ''}

    <script>
    (function() {{
      const labels = {_js(labels)};

      // Gráfico 1 — Impressões + Cliques
      new Chart(document.getElementById('chartDaily').getContext('2d'), {{
        type: 'bar',
        data: {{
          labels,
          datasets: [
            {{
              label: 'Impressões',
              data: {_js(impressions)},
              backgroundColor: 'rgba(234,179,8,.55)',
              borderColor: '#ca8a04',
              borderWidth: 1,
              yAxisID: 'y',
            }},
            {{
              label: 'Cliques',
              data: {_js(clicks)},
              type: 'line',
              borderColor: '#003f7c',
              backgroundColor: 'rgba(0,63,124,.12)',
              borderWidth: 2,
              pointRadius: 3,
              fill: true,
              yAxisID: 'y2',
              tension: .35,
            }},
          ]
        }},
        options: {{
          responsive: true,
          interaction: {{ mode: 'index', intersect: false }},
          plugins: {{ legend: {{ position: 'top' }} }},
          scales: {{
            y:  {{ position: 'left',  title: {{ display: true, text: 'Impressões' }} }},
            y2: {{ position: 'right', title: {{ display: true, text: 'Cliques' }}, grid: {{ drawOnChartArea: false }} }},
          }},
        }}
      }});

      // Gráfico 2 — Custo
      new Chart(document.getElementById('chartCost').getContext('2d'), {{
        type: 'line',
        data: {{
          labels,
          datasets: [{{
            label: 'Custo (R$)',
            data: {_js(cost)},
            borderColor: '#f97316',
            backgroundColor: 'rgba(249,115,22,.12)',
            borderWidth: 2,
            fill: true,
            tension: .35,
            pointRadius: 3,
          }}]
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ position: 'top' }} }},
          scales: {{ y: {{ title: {{ display: true, text: 'R$' }} }} }},
        }}
      }});

      {'// Gráfico 3 — Conversões' if any(v > 0 for v in conversions) else ''}
      {f"""new Chart(document.getElementById('chartConv').getContext('2d'), {{
        type: 'bar',
        data: {{
          labels,
          datasets: [{{
            label: 'Conversões',
            data: {_js(conversions)},
            backgroundColor: 'rgba(22,163,74,.6)',
            borderColor: '#15803d',
            borderWidth: 1,
          }}]
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ position: 'top' }} }},
          scales: {{ y: {{ title: {{ display: true, text: 'Conversões' }} }} }},
        }}
      }});""" if any(v > 0 for v in conversions) else ''}
    }})();
    </script>
  </section>"""


def _campaigns_table(data: dict) -> str:
    campaigns = data.get("campaigns", [])
    if not campaigns:
        return ""

    rows_html = ""
    for c in campaigns:
        status = c.get("status", "ok")
        status_map = {
            "best":    ("badge-green",  "🏆 Melhor CTR"),
            "warning": ("badge-red",    "⚠️ CTR baixo"),
            "ok":      ("badge-gray",   "✅ Regular"),
        }
        badge_class, badge_label = status_map.get(status, ("badge-gray", "—"))

        cpa_cell = f"R${_br(c.get('cost_per_conv', 0), 2)}" if c.get("cost_per_conv", 0) > 0 else "—"
        roas_cell = f"{_br(c.get('roas', 0), 2)}x" if c.get("roas", 0) > 0 else "—"

        rows_html += f"""
        <tr>
          <td class="td-campaign">{c['name']}</td>
          <td class="td-num">{_br(c['impressions'])}</td>
          <td class="td-num">{_br(c['clicks'])}</td>
          <td class="td-num">{_br(c['ctr'], 2)}%</td>
          <td class="td-num">R${_br(c['avg_cpc'], 2)}</td>
          <td class="td-num">R${_br(c['cost'], 2)}</td>
          <td class="td-num">{_br(c['conversions'], 1)}</td>
          <td class="td-num">{_br(c['conv_rate'], 2)}%</td>
          <td class="td-num">{cpa_cell}</td>
          <td class="td-num">{roas_cell}</td>
          <td><span class="status-pill {badge_class}">{badge_label}</span></td>
        </tr>"""

    # Gráfico de barras horizontais — custo por campanha
    camp_names = [c["name"][:30] for c in campaigns[:8]]
    camp_costs = [round(c["cost"], 2) for c in campaigns[:8]]
    camp_ctrs  = [round(c["ctr"], 2) for c in campaigns[:8]]

    return f"""
  <section class="section">
    <h2 class="section-title">&#128202; Performance por Campanha</h2>

    <div style="overflow-x:auto;margin-bottom:24px;">
      <table class="data-table">
        <thead>
          <tr>
            <th>Campanha</th>
            <th>Impress&#245;es</th>
            <th>Cliques</th>
            <th>CTR</th>
            <th>CPC M&#233;d.</th>
            <th>Custo</th>
            <th>Conv.</th>
            <th>Taxa Conv.</th>
            <th>CPA</th>
            <th>ROAS</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:4px;">
      <div class="chart-container">
        <div class="chart-title">Distribui&#231;&#227;o de Custo por Campanha</div>
        <canvas id="chartCampCost" height="160"></canvas>
      </div>
      <div class="chart-container">
        <div class="chart-title">CTR por Campanha (%)</div>
        <canvas id="chartCampCtr" height="160"></canvas>
      </div>
    </div>

    <script>
    (function() {{
      const campNames = {_js(camp_names)};

      new Chart(document.getElementById('chartCampCost').getContext('2d'), {{
        type: 'bar',
        data: {{
          labels: campNames,
          datasets: [{{
            label: 'Custo (R$)',
            data: {_js(camp_costs)},
            backgroundColor: ['#f97316','#fb923c','#fdba74','#fed7aa','#fef3c7','#fef9c3','#fefce8','#fffbeb'],
            borderRadius: 4,
          }}]
        }},
        options: {{
          indexAxis: 'y',
          responsive: true,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{ x: {{ title: {{ display: true, text: 'R$' }} }} }},
        }}
      }});

      new Chart(document.getElementById('chartCampCtr').getContext('2d'), {{
        type: 'bar',
        data: {{
          labels: campNames,
          datasets: [{{
            label: 'CTR (%)',
            data: {_js(camp_ctrs)},
            backgroundColor: ['#003f7c','#1a5a9a','#2563eb','#3b82f6','#60a5fa','#93c5fd','#bfdbfe','#dbeafe'],
            borderRadius: 4,
          }}]
        }},
        options: {{
          indexAxis: 'y',
          responsive: true,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{ x: {{ title: {{ display: true, text: '%' }} }} }},
        }}
      }});
    }})();
    </script>
  </section>"""


def _strategic_section(ai_analysis: dict | None) -> str:
    """Seção de análise estratégica — gerada pela IA ou retornada vazia."""
    if not ai_analysis:
        return ""

    import re as _re

    def _strip(text: str) -> str:
        return _re.sub(r"<[^>]+>", "", text or "")

    strengths  = ai_analysis.get("strengths", [])
    attentions = ai_analysis.get("attentions", [])

    if not strengths and not attentions:
        return ""

    def _items(items, icon_color: str, bg: str, border: str) -> str:
        html = ""
        for item in items:
            emoji = item[0] if isinstance(item, (list, tuple)) else item.get("emoji", "•")
            text  = item[1] if isinstance(item, (list, tuple)) else item.get("text", "")
            html += (
                f'<div class="strategic-item" style="background:{bg};border-left:4px solid {border};">'
                f'<span class="strategic-emoji">{emoji}</span>'
                f'<span class="strategic-text">{text}</span>'
                f'</div>'
            )
        return html

    strengths_html  = _items(strengths,  "#16a34a", "#f0fdf4", "#86efac")
    attentions_html = _items(attentions, "#d97706", "#fffbeb", "#fcd34d")

    return f"""
  <section class="section">
    <h2 class="section-title">&#129517; An&#225;lise Estrat&#233;gica</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
      <div>
        <div class="strategic-header" style="color:#16a34a;">&#9989; Pontos Fortes</div>
        {strengths_html}
      </div>
      <div>
        <div class="strategic-header" style="color:#d97706;">&#9888;&#65039; Pontos de Aten&#231;&#227;o</div>
        {attentions_html}
      </div>
    </div>
  </section>"""


def _footer(client: dict, data: dict) -> str:
    name   = client.get("name", "")
    period = data.get("period_label", "")
    return f"""
  <footer class="report-footer">
    Relat&#243;rio gerado para <strong>{name}</strong> por Dash Digital &nbsp;|&nbsp;
    Per&#237;odo: {period} &nbsp;|&nbsp; Dados: Google Ads Manager
  </footer>"""


# ── CSS e template base ────────────────────────────────────────────────────────

_CSS = """
:root {
  --brand-primary:   #f8b940;  /* gold Dash Digital */
  --brand-dark:      #003f7c;  /* azul Dash Digital */
  --brand-blue:      #003f7c;
  --text-primary:    #111827;
  --text-secondary:  #6b7280;
  --bg-page:         #f0f3f8;
  --bg-section:      #ffffff;
  --border:          #e5e7eb;
  --radius:          12px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg-page);
  color: var(--text-primary);
  line-height: 1.6;
}

.report-wrapper { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }

/* Header */
.report-header {
  background: linear-gradient(135deg, #003f7c, #1a5a9a);
  border-radius: 16px;
  padding: 32px 36px;
  color: #fff;
  margin-bottom: 24px;
}
.header-content { display: flex; align-items: center; gap: 20px; margin-bottom: 12px; }
.header-icon { font-size: 3.5rem; line-height: 1; }
.client-name { font-size: 1.8rem; font-weight: 800; margin-bottom: 4px; }
.client-industry { font-size: .95rem; opacity: .8; margin-bottom: 10px; }
.header-meta { display: flex; gap: 10px; flex-wrap: wrap; }
.meta-badge {
  background: rgba(255,255,255,.2);
  border-radius: 8px;
  padding: 4px 14px;
  font-size: .82rem;
  font-weight: 600;
}
.generated-at { font-size: .75rem; opacity: .65; margin-top: 8px; }

/* Sections */
.section {
  background: var(--bg-section);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 28px 32px;
  margin-bottom: 20px;
}
.section-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--brand-dark);
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--brand-primary);
}

/* KPI Cards */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 14px;
}
.kpi-card {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}
.kpi-icon { font-size: 1.4rem; display: block; margin-bottom: 6px; }
.kpi-val  { font-size: 1.5rem; font-weight: 800; color: var(--brand-dark); }
.kpi-label { font-size: .78rem; color: var(--text-secondary); margin: 4px 0 6px; }
.kpi-badge {
  display: inline-block;
  font-size: .68rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.badge-blue   { background: #dbeafe; color: #1e40af; }
.badge-green  { background: #dcfce7; color: #14532d; }
.badge-orange { background: #ffedd5; color: #9a3412; }
.badge-red    { background: #fee2e2; color: #7f1d1d; }
.badge-gray   { background: #f3f4f6; color: #374151; }

/* Charts */
.chart-container {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
}
.chart-title {
  font-size: .85rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

/* Data table */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: .83rem;
}
.data-table thead tr { background: #f8fafc; }
.data-table th {
  padding: 10px 12px;
  text-align: left;
  font-size: .75rem;
  color: var(--text-secondary);
  font-weight: 600;
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
}
.data-table td {
  padding: 9px 12px;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: middle;
}
.data-table tr:hover td { background: #fafafa; }
.td-campaign { font-weight: 500; max-width: 220px; }
.td-num { text-align: right; font-variant-numeric: tabular-nums; }

/* Status pill */
.status-pill {
  font-size: .7rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 8px;
  white-space: nowrap;
}

/* Strategic */
.strategic-header {
  font-size: .8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: 12px;
}
.strategic-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 8px;
}
.strategic-emoji { font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }
.strategic-text  { font-size: .86rem; color: #374151; line-height: 1.65; }

/* Health score — vem de health_score.py */

/* Footer */
.report-footer {
  text-align: center;
  font-size: .78rem;
  color: var(--text-secondary);
  margin-top: 32px;
  padding: 16px;
  border-top: 1px solid var(--border);
}

@media (max-width: 640px) {
  .section { padding: 18px 16px; }
  .kpi-val { font-size: 1.3rem; }
  .header-content { flex-direction: column; text-align: center; }
  .data-table th, .data-table td { padding: 7px 8px; }
  .strategic-item { flex-direction: column; }
  div[style*="grid-template-columns:1fr 1fr"] { display: block !important; }
  div[style*="grid-template-columns:1fr 1fr"] > div:last-child { margin-top: 16px; }
}
"""


def generate(
    client:       dict,
    data:         dict,
    health:       dict | None = None,
    ai_analysis:  dict | None = None,
    generated_at: str         = "",
) -> str:
    """
    Gera o relatório HTML completo do Google Ads.

    Args:
        client:      dict do cliente (name, industry, goals, ...)
        data:        dict retornado por processor.process()
        health:      dict retornado por health_score.calculate() — opcional
        ai_analysis: dict retornado por ai_analysis.generate_analysis() — opcional
        generated_at: timestamp string

    Returns:
        HTML completo como string
    """
    if not generated_at:
        generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")

    from src.health_score import render_card_html as _health_card

    sections = [
        _header(client, data, generated_at),
        _kpis(data),
        _daily_charts(data),
        _campaigns_table(data),
        _health_card(health) if health else "",
        _strategic_section(ai_analysis),
        _footer(client, data),
    ]

    body = "\n".join(s for s in sections if s)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatório Google Ads — {client.get('name', '')} · {data.get('period_label', '')}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>{_CSS}</style>
</head>
<body>
<div class="report-wrapper">
{body}
</div>
</body>
</html>"""
