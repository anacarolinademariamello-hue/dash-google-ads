"""
processor.py — Agrega dados parseados do CSV em métricas prontas para o relatório.

Entrada:  dict retornado por csv_parser.parse()
Saída:    dict com totais, médias, séries temporais e metadados do período
"""
from __future__ import annotations

from datetime import datetime, timedelta


def _br_date(d: str) -> str:
    """YYYY-MM-DD → DD/MM"""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m")
    except Exception:
        return d


def process(parsed: dict) -> dict:
    """
    Processa o dict retornado por csv_parser.parse() e retorna métricas consolidadas.

    Returns dict com:
      Totais: impressions, clicks, cost, conversions
      Médias: ctr, avg_cpc, cost_per_conv, roas, conv_rate
      Campanhas: lista com status calculado
      Diário: arrays para gráficos
      Metadados: period_label, days, date_from, date_to
    """
    campaigns = parsed.get("campaigns", [])
    daily     = parsed.get("daily", [])
    date_from = parsed.get("date_from", "")
    date_to   = parsed.get("date_to", "")

    # ── Totais ────────────────────────────────────────────────────────────────
    total_impressions = sum(c["impressions"] for c in campaigns)
    total_clicks      = sum(c["clicks"]      for c in campaigns)
    total_cost        = sum(c["cost"]         for c in campaigns)
    total_conversions = sum(c["conversions"]  for c in campaigns)

    # Médias ponderadas / calculadas dos totais
    avg_ctr       = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0.0
    avg_cpc       = round(total_cost / total_clicks, 2)              if total_clicks      else 0.0
    conv_rate     = round(total_conversions / total_clicks * 100, 2) if total_clicks      else 0.0
    cost_per_conv = round(total_cost / total_conversions, 2)         if total_conversions else 0.0

    # ROAS: média ponderada por custo de campanha
    roas_num = sum(c["roas"] * c["cost"] for c in campaigns if c["roas"] and c["cost"])
    roas_den = sum(c["cost"] for c in campaigns if c["roas"] and c["cost"])
    avg_roas  = round(roas_num / roas_den, 2) if roas_den else 0.0

    # ── Período ───────────────────────────────────────────────────────────────
    if date_from and date_to:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            dt = datetime.strptime(date_to,   "%Y-%m-%d")
            days = (dt - df).days + 1
            period_label = f"{df.strftime('%d/%m')} – {dt.strftime('%d/%m/%Y')}"
        except Exception:
            days = len(daily) or 7
            period_label = f"{date_from} → {date_to}"
    else:
        days = len(daily) or 7
        period_label = ""

    # ── Status de campanhas ────────────────────────────────────────────────────
    # Classifica cada campanha como best / warning / ok
    if campaigns:
        best_ctr = max(c["ctr"] for c in campaigns)
        for c in campaigns:
            if c["ctr"] >= best_ctr * 0.95 and best_ctr > 0:
                c["status"] = "best"
            elif c["ctr"] < avg_ctr * 0.7 and avg_ctr > 0:
                c["status"] = "warning"
            else:
                c["status"] = "ok"

    # ── Séries diárias para gráficos ──────────────────────────────────────────
    # Se não há dados diários, gera série vazia com datas no período
    if daily:
        daily_dates       = [d["date"]       for d in daily]
        daily_labels      = [_br_date(d["date"]) for d in daily]
        daily_impressions = [d["impressions"] for d in daily]
        daily_clicks      = [d["clicks"]      for d in daily]
        daily_cost        = [d["cost"]        for d in daily]
        daily_conversions = [d.get("conversions", 0) for d in daily]
        daily_ctr         = [d.get("ctr", 0)  for d in daily]
    else:
        # Sem breakdown diário — arrays vazios
        daily_dates = daily_labels = []
        daily_impressions = daily_clicks = daily_cost = []
        daily_conversions = daily_ctr = []

    # ── Top campanhas (máx 10 para o relatório) ────────────────────────────────
    top_campaigns = campaigns[:10]

    return {
        # Totais
        "total_impressions": total_impressions,
        "total_clicks":      total_clicks,
        "total_cost":        round(total_cost, 2),
        "total_conversions": round(total_conversions, 1),
        # Médias
        "avg_ctr":        avg_ctr,
        "avg_cpc":        avg_cpc,
        "conv_rate":      conv_rate,
        "cost_per_conv":  cost_per_conv,
        "avg_roas":       avg_roas,
        # Campanhas
        "campaigns":      top_campaigns,
        "total_campaigns": len(campaigns),
        # Séries diárias
        "daily_dates":        daily_dates,
        "daily_labels":       daily_labels,
        "daily_impressions":  daily_impressions,
        "daily_clicks":       daily_clicks,
        "daily_cost":         daily_cost,
        "daily_conversions":  daily_conversions,
        "daily_ctr":          daily_ctr,
        # Período
        "date_from":     date_from,
        "date_to":       date_to,
        "days":          days,
        "period_label":  period_label,
    }
