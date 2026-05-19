"""
ai_analysis.py — Análise estratégica gerada pelo Claude com base nos dados reais do Google Ads.

Retorna: {"strengths": [(emoji, html_text), ...], "attentions": [(emoji, html_text), ...]}
Fallback: None (html_gen.py usa lógica estática nesse caso)
"""
from __future__ import annotations

import json
import re


def _build_prompt(data: dict, client: dict, prev_metrics: dict | None) -> str:
    name     = client.get("name", "o cliente")
    industry = client.get("industry", "")
    goals    = client.get("goals") or {}
    period   = data.get("period_label", "")
    gads_id  = client.get("google_ads_account_id", "")

    def _br(v, d=0):
        try:
            s = f"{float(v):,.{d}f}" if d else f"{int(round(float(v))):,}"
            return s.replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return str(v)

    # Métricas principais
    metrics_lines = [
        f"- Impressões: {_br(data.get('total_impressions', 0))}",
        f"- Cliques: {_br(data.get('total_clicks', 0))}",
        f"- CTR médio: {_br(data.get('avg_ctr', 0), 2)}%",
        f"- Custo total: R${_br(data.get('total_cost', 0), 2)}",
        f"- CPC médio: R${_br(data.get('avg_cpc', 0), 2)}",
        f"- Conversões: {_br(data.get('total_conversions', 0), 1)}",
        f"- Taxa de conversão: {_br(data.get('conv_rate', 0), 2)}%",
    ]
    cpa = data.get("cost_per_conv", 0)
    if cpa and cpa > 0:
        metrics_lines.append(f"- CPA (custo por conversão): R${_br(cpa, 2)}")
    roas = data.get("avg_roas", 0)
    if roas and roas > 0:
        metrics_lines.append(f"- ROAS médio: {_br(roas, 2)}x")

    # Campanhas individuais
    camp_lines = []
    for c in data.get("campaigns", [])[:6]:
        status_label = {"best": "melhor CTR", "warning": "CTR abaixo da média", "ok": "regular"}.get(c.get("status", ""), "")
        camp_lines.append(
            f"- '{c['name']}': impressões {_br(c['impressions'])} | "
            f"cliques {_br(c['clicks'])} | CTR {c.get('ctr', 0):.2f}% | "
            f"CPC R${c.get('avg_cpc', 0):.2f} | custo R${c.get('cost', 0):.2f} | "
            f"conversões {c.get('conversions', 0):.1f} | {status_label}"
        )

    # Comparativo com período anterior
    prev_lines = []
    if prev_metrics:
        prev_ctr  = float(prev_metrics.get("avg_ctr", 0) or 0)
        prev_conv = float(prev_metrics.get("conv_rate", 0) or 0)
        prev_cost = float(prev_metrics.get("total_cost", 0) or 0)
        curr_ctr  = float(data.get("avg_ctr", 0) or 0)
        curr_conv = float(data.get("conv_rate", 0) or 0)
        curr_cost = float(data.get("total_cost", 0) or 0)
        if prev_ctr > 0:
            delta = curr_ctr - prev_ctr
            sign  = "+" if delta >= 0 else ""
            prev_lines.append(f"- CTR: {sign}{delta:.2f}% vs período anterior ({prev_ctr:.2f}% → {curr_ctr:.2f}%)")
        if prev_conv > 0:
            delta = curr_conv - prev_conv
            sign  = "+" if delta >= 0 else ""
            prev_lines.append(f"- Taxa de conversão: {sign}{delta:.2f}% ({prev_conv:.2f}% → {curr_conv:.2f}%)")
        if prev_cost > 0:
            delta_pct = (curr_cost - prev_cost) / prev_cost * 100
            sign  = "+" if delta_pct >= 0 else ""
            prev_lines.append(f"- Custo: {sign}{delta_pct:.1f}% vs período anterior")

    # Metas do cliente (chaves salvas pelo Gerenciador de Clientes)
    goals_lines = []
    for goal_key, data_key, label, higher_is_better in [
        ("gads_ctr_alvo",   "avg_ctr",       "CTR alvo (%)",      True),
        ("gads_cpa_alvo",   "cost_per_conv", "CPA alvo (R$)",     False),
        ("gads_roas_alvo",  "avg_roas",      "ROAS alvo (x)",     True),
        ("gads_cpc_maximo", "avg_cpc",       "CPC máximo (R$)",   False),
    ]:
        g = float(goals.get(goal_key) or 0)
        if g <= 0:
            continue
        r = float(data.get(data_key, 0) or 0)
        if r > 0:
            met = (r >= g) if higher_is_better else (r <= g)
            status = "✅ dentro da meta" if met else "❌ fora da meta"
            goals_lines.append(f"- {label}: meta {g:.2f} | real {r:.2f} → {status}")

    metrics_section  = "\n".join(metrics_lines)
    camp_section     = "\n".join(camp_lines)  if camp_lines  else "Sem detalhes de campanha."
    prev_section     = "\n".join(prev_lines)  if prev_lines  else "Sem dados do período anterior."
    goals_section    = "\n".join(goals_lines) if goals_lines else "Sem metas configuradas."

    return f"""Você é um especialista sênior em Google Ads no mercado brasileiro. Analise os dados abaixo de um relatório real de campanhas e gere uma análise estratégica honesta, específica e acionável.

## CLIENTE
- Nome: {name}
- Setor / Indústria: {industry or "Não informado"}
- Conta Google Ads: {gads_id or "Não informado"}
- Período: {period}

## MÉTRICAS DO PERÍODO
{metrics_section}

## CAMPANHAS INDIVIDUAIS
{camp_section}

## COMPARATIVO COM PERÍODO ANTERIOR
{prev_section}

## METAS VS REAL
{goals_section}

## SUA TAREFA

Gere uma análise estratégica com EXATAMENTE este formato JSON. Não adicione nada fora do JSON.

Regras:
- Mínimo 4 e máximo 6 itens em cada lista
- Cada item DEVE ser baseado nos dados reais acima — nada genérico
- Use <strong> para destacar números e termos-chave
- Texto em português brasileiro, tom profissional e direto
- "attentions" deve incluir recomendações concretas com ações específicas
- Considere benchmarks reais de Google Ads: CTR busca ~3-5%, display ~0,5%, conversão ~3-5%
- Se uma campanha tem CTR abaixo da média, sugira ajuste de copy/lance/segmentação
- Mencione oportunidades de otimização de lance, palavras-chave negativas, extensões de anúncio

```json
{{
  "strengths": [
    {{"emoji": "🎯", "text": "Texto com <strong>números reais</strong> e contexto específico."}},
    {{"emoji": "📈", "text": "..."}}
  ],
  "attentions": [
    {{"emoji": "⚠️", "text": "Texto com recomendação concreta baseada nos dados."}},
    {{"emoji": "💡", "text": "..."}}
  ]
}}
```"""


def generate_analysis(data: dict, client: dict, prev_metrics: dict | None = None) -> dict | None:
    """
    Chama Claude para gerar análise estratégica de Google Ads.
    Retorna dict com "strengths" e "attentions" como listas de (emoji, html_text).
    Retorna None em caso de erro.
    """
    try:
        import streamlit as st
        api_key = st.secrets.get("ANTHROPIC_API_KEY") or st.secrets.get("anthropic_api_key")
    except Exception:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return None

    try:
        import anthropic
        client_ai = anthropic.Anthropic(api_key=api_key)
        prompt    = _build_prompt(data, client, prev_metrics)
        message   = client_ai.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            return None
        parsed = json.loads(json_match.group(0))

        def _to_tuples(items):
            result = []
            for item in items:
                if isinstance(item, dict):
                    result.append((item.get("emoji", "•"), item.get("text", "")))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    result.append(tuple(item))
            return result

        strengths  = _to_tuples(parsed.get("strengths", []))
        attentions = _to_tuples(parsed.get("attentions", []))

        if len(strengths) >= 2 and len(attentions) >= 2:
            return {"strengths": strengths, "attentions": attentions}

        return None

    except Exception:
        return None
