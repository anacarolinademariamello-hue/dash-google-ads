"""
health_score.py — Cálculo do Score de Saúde de campanhas Google Ads (0–100).

Critérios:
  CTR                   → 25 pts  (qualidade do anúncio vs busca)
  Taxa de conversão     → 25 pts  (relevância landing page + oferta)
  ROAS                  → 20 pts  (retorno sobre o investimento)
  Custo / eficiência    → 15 pts  (CPA vs período anterior)
  Consistência semanal  → 15 pts  (estabilidade de impressões)
"""
from __future__ import annotations


def calculate(data: dict, prev_metrics: dict | None = None) -> dict:
    """
    Calcula o score de saúde do período Google Ads.

    Args:
        data:         dict retornado por src.processor.process()
        prev_metrics: dict de métricas do período anterior (de google_ads_report_history)
                      ou None se não houver histórico.

    Returns:
        {
            "score":     int,        # 0–100
            "grade":     str,        # "Excelente" | "Bom" | "Regular" | "Atenção" | "Crítico"
            "color":     str,        # cor hex
            "breakdown": dict,       # pontos por critério
            "delta":     int | None, # variação vs período anterior
        }
    """
    scores: dict[str, int] = {}

    # 1. CTR (25 pts) — taxa de clique nas campanhas
    ctr = float(data.get("avg_ctr", 0) or 0)
    if   ctr >= 5.0: scores["ctr"] = 25
    elif ctr >= 3.0: scores["ctr"] = 20
    elif ctr >= 2.0: scores["ctr"] = 14
    elif ctr >= 1.0: scores["ctr"] = 8
    elif ctr >= 0.5: scores["ctr"] = 4
    else:            scores["ctr"] = 0

    # 2. Taxa de conversão (25 pts)
    # Benchmark geral Google Ads: ~3-5% para busca
    conv_rate = float(data.get("conv_rate", 0) or 0)
    has_conversions = float(data.get("total_conversions", 0) or 0) > 0
    if not has_conversions:
        scores["conv_rate"] = 12  # neutro — sem rastreamento de conversão
    elif conv_rate >= 5.0:  scores["conv_rate"] = 25
    elif conv_rate >= 3.0:  scores["conv_rate"] = 20
    elif conv_rate >= 1.5:  scores["conv_rate"] = 13
    elif conv_rate >= 0.5:  scores["conv_rate"] = 7
    else:                   scores["conv_rate"] = 2

    # 3. ROAS (20 pts)
    roas = float(data.get("avg_roas", 0) or 0)
    if roas <= 0:        scores["roas"] = 10  # neutro — sem valor de conversão rastreado
    elif roas >= 5.0:    scores["roas"] = 20
    elif roas >= 3.5:    scores["roas"] = 16
    elif roas >= 2.5:    scores["roas"] = 12
    elif roas >= 1.5:    scores["roas"] = 7
    elif roas >= 1.0:    scores["roas"] = 4
    else:                scores["roas"] = 0

    # 4. Eficiência de custo / CPA (15 pts)
    # Compara CPA atual com o período anterior (se disponível)
    if prev_metrics:
        prev_cpa  = float(prev_metrics.get("cost_per_conv", 0) or 0)
        curr_cpa  = float(data.get("cost_per_conv", 0) or 0)
        if prev_cpa > 0 and curr_cpa > 0:
            cpa_change = (curr_cpa - prev_cpa) / prev_cpa * 100
            if   cpa_change <= -10: scores["eficiencia"] = 15   # CPA melhorou > 10%
            elif cpa_change <= 5:   scores["eficiencia"] = 10   # CPA estável
            elif cpa_change <= 20:  scores["eficiencia"] = 5    # CPA piorou moderado
            else:                   scores["eficiencia"] = 0    # CPA piorou muito
        elif curr_cpa == 0 and not has_conversions:
            scores["eficiencia"] = 7  # sem conversões → neutro
        else:
            scores["eficiencia"] = 7  # sem histórico → neutro
    else:
        scores["eficiencia"] = 7  # sem histórico → neutro

    # 5. Consistência semanal de impressões (15 pts)
    if prev_metrics:
        prev_impressions = int(prev_metrics.get("total_impressions", 0) or 0)
        curr_impressions = int(data.get("total_impressions", 0) or 0)
        if prev_impressions > 0:
            variation = (curr_impressions - prev_impressions) / prev_impressions * 100
            if   variation >= 10:   scores["consistencia"] = 15  # crescendo
            elif variation >= -5:   scores["consistencia"] = 12  # estável
            elif variation >= -20:  scores["consistencia"] = 6   # queda moderada
            else:                   scores["consistencia"] = 0   # queda forte
        else:
            scores["consistencia"] = 7
    else:
        scores["consistencia"] = 7  # sem histórico → neutro

    total = sum(scores.values())

    if   total >= 85: grade, color = "Excelente", "#16a34a"
    elif total >= 70: grade, color = "Bom",       "#16a34a"
    elif total >= 55: grade, color = "Regular",   "#d97706"
    elif total >= 35: grade, color = "Atenção",   "#ea580c"
    else:             grade, color = "Crítico",   "#dc2626"

    prev_score = int(prev_metrics.get("health_score", 0) or 0) if prev_metrics else None
    delta      = (total - prev_score) if prev_score else None

    return {
        "score":     total,
        "grade":     grade,
        "color":     color,
        "breakdown": scores,
        "delta":     delta,
    }


def render_card_html(health: dict) -> str:
    """Gera o HTML do card de Score de Saúde para injetar no relatório."""
    if not health:
        return ""

    score     = health["score"]
    grade     = health["grade"]
    color     = health["color"]
    delta     = health.get("delta")
    breakdown = health.get("breakdown", {})

    delta_html = ""
    if delta is not None:
        d_sign  = "+" if delta >= 0 else ""
        d_color = "#16a34a" if delta >= 0 else "#dc2626"
        d_arrow = "&#9650;" if delta >= 0 else "&#9660;"
        delta_html = (
            f'<span style="font-size:.85rem;font-weight:600;color:{d_color};margin-left:12px;">'
            f'{d_arrow} {d_sign}{delta} pts vs per&#237;odo anterior</span>'
        )

    emoji = "&#129001;" if score >= 70 else "&#128993;" if score >= 55 else "&#129000;" if score >= 35 else "&#128308;"

    label_map = [
        ("ctr",         "CTR das campanhas <span style='font-weight:400;color:#9ca3af;'>(taxa de clique nos an&#250;ncios)</span>",                                    25),
        ("conv_rate",   "Taxa de convers&#227;o <span style='font-weight:400;color:#9ca3af;'>(cliques que viraram convers&#245;es — neutro 12/25 sem rastreamento)</span>", 25),
        ("roas",        "ROAS <span style='font-weight:400;color:#9ca3af;'>(retorno sobre investimento — neutro 10/20 sem valor rastreado)</span>",                    20),
        ("eficiencia",  "Efici&#234;ncia de custo/CPA <span style='font-weight:400;color:#9ca3af;'>(varia&#231;&#227;o do CPA vs per&#237;odo anterior)</span>",       15),
        ("consistencia","Consist&#234;ncia de impress&#245;es <span style='font-weight:400;color:#9ca3af;'>(estabilidade vs per&#237;odo anterior)</span>",            15),
    ]

    bars_html = ""
    for key, label, max_val in label_map:
        val       = breakdown.get(key, 0)
        pct       = int(val / max_val * 100) if max_val else 0
        bar_color = "#16a34a" if pct >= 70 else "#d97706" if pct >= 40 else "#dc2626"
        bars_html += (
            f'<div style="margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
            f'<span style="font-size:.82rem;color:#6b7280;">{label}</span>'
            f'<span style="font-size:.82rem;font-weight:700;color:#374151;">{val}/{max_val}</span>'
            f'</div>'
            f'<div style="background:#f3f4f6;border-radius:6px;height:8px;">'
            f'<div style="background:{bar_color};width:{pct}%;height:8px;border-radius:6px;"></div>'
            f'</div></div>'
        )

    return (
        '<section class="section">'
        '<h2 class="section-title">&#127973; Score de Sa&#250;de das Campanhas</h2>'
        f'<div style="background:#fff;border:2px solid {color};border-radius:16px;padding:28px 32px;">'
        f'<div style="display:flex;align-items:center;gap:24px;margin-bottom:24px;flex-wrap:wrap;">'
        f'<div style="font-size:5rem;line-height:1;">{emoji}</div>'
        f'<div>'
        f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:4px;">Score de Sa&#250;de</div>'
        f'<div style="display:flex;align-items:baseline;gap:4px;">'
        f'<span style="font-size:4rem;font-weight:800;color:{color};line-height:1;">{score}</span>'
        f'<span style="font-size:1.4rem;color:#9ca3af;">/100</span>'
        f'{delta_html}'
        f'</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:{color};margin-top:4px;">{grade}</div>'
        f'</div></div>'
        f'<div style="max-width:600px;">{bars_html}</div>'
        f'<div style="margin-top:16px;padding:12px 16px;background:#f8fafc;border-radius:10px;font-size:.8rem;color:#6b7280;">'
        f'&#128161; Score calculado com base no per&#237;odo selecionado. ROAS e Taxa de Convers&#227;o s&#227;o neutros quando n&#227;o h&#225; rastreamento configurado.'
        f'</div></div></section>'
    )
