"""
csv_parser.py — Parser robusto para CSV exportado do Google Ads Manager.

Formatos suportados:
  - Relatório de campanhas (colunas Campaign / Campanha)
  - Relatório diário      (com coluna Day / Data / Dia)
  - Relatório misto       (campanha + dia juntos)

O Google Ads exporta CSV com:
  - Linhas de cabeçalho da plataforma (ignoradas automaticamente)
  - Linha de Total geral no final (ignorada)
  - Números no formato pt-BR: ponto como milhar, vírgula como decimal
  - Prefixo "R$" nos valores monetários
  - Sufixo "%" nas taxas

Retorna dict:
  {
    "campaigns": [{"name", "impressions", "clicks", "ctr", "avg_cpc",
                   "cost", "conversions", "conv_rate", "cost_per_conv", "roas"}],
    "daily":     [{"date", "impressions", "clicks", "ctr", "avg_cpc",
                   "cost", "conversions", "conv_rate", "cost_per_conv"}],
    "date_from": "YYYY-MM-DD" | "",
    "date_to":   "YYYY-MM-DD" | "",
    "raw_columns": [str],   # nomes originais das colunas encontradas
    "warnings":    [str],   # avisos não-fatais
  }
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime


# ── Mapeamento de colunas (inglês e português) ─────────────────────────────────

_COL_MAP: dict[str, str] = {
    # Data
    "day":              "date",
    "data":             "date",
    "dia":              "date",
    "week":             "date",
    "semana":           "date",
    "month":            "date",
    "mês":              "date",
    # Campanha
    "campaign":         "campaign",
    "campanha":         "campaign",
    "campaign name":    "campaign",
    # Grupo de anúncios
    "ad group":         "ad_group",
    "grupo de anúncios": "ad_group",
    "ad group name":    "ad_group",
    # Anúncio
    "ad":               "ad",
    "anúncio":          "ad",
    # Impressões
    "impressions":      "impressions",
    "impressões":       "impressions",
    "impr.":            "impressions",
    # Cliques
    "clicks":           "clicks",
    "cliques":          "clicks",
    # CTR
    "ctr":              "ctr",
    # CPC médio
    "avg. cpc":         "avg_cpc",
    "cpc méd.":         "avg_cpc",
    "cpc médio":        "avg_cpc",
    "average cpc":      "avg_cpc",
    # Custo
    "cost":             "cost",
    "custo":            "cost",
    "spend":            "cost",
    # Conversões
    "conversions":      "conversions",
    "conv.":            "conversions",
    "conversões":       "conversions",
    "all conv.":        "conversions",
    "todas conv.":      "conversions",
    # Taxa de conversão
    "conv. rate":       "conv_rate",
    "taxa de conv.":    "conv_rate",
    "conversion rate":  "conv_rate",
    # Custo por conversão
    "cost / conv.":     "cost_per_conv",
    "custo / conv.":    "cost_per_conv",
    "cost per conversion": "cost_per_conv",
    "cpa":              "cost_per_conv",
    # ROAS
    "conv. value / cost": "roas",
    "valor de conv. / custo": "roas",
    "roas":             "roas",
    "return on ad spend": "roas",
    # Parcela de impressões
    "search impr. share":      "search_impr_share",
    "parcela de impr. de pesquisa": "search_impr_share",
    # Topo absoluto
    "impr. (abs. top) %":      "abs_top_impr_pct",
    "impr. (topo abs.) %":     "abs_top_impr_pct",
    # Índice de qualidade
    "quality score":           "quality_score",
    "índice de qualidade":     "quality_score",
}


def _normalize_col(name: str) -> str:
    """Normaliza nome de coluna para lookup no mapeamento."""
    return name.strip().lower().replace("\xa0", " ")


def _parse_number(val: str) -> float:
    """
    Converte valor textual do Google Ads para float.
    Lida com todos os formatos:
      pt-BR: "1.234,56" → 1234.56 | "1.234" → 1234 | "36,97%" → 36.97
      en-US: "1,234.56" → 1234.56 | "1,234" → 1234 | "36.97%" → 36.97
      moeda: "R$ 1,25" → 1.25 | "R$ 1.234,56" → 1234.56
    """
    if not val or val.strip() in ("--", "—", "-", "n/a", "n.a.", ""):
        return 0.0
    s = val.strip()
    # Remove prefixos de moeda e sufixo %
    s = re.sub(r"[R$€£¥\s%]", "", s)
    s = s.strip()
    if not s or s in ("--", "—", "-"):
        return 0.0

    last_dot   = s.rfind(".")
    last_comma = s.rfind(",")

    try:
        if last_dot > 0 and last_comma > last_dot:
            # Formato pt-BR com decimal: "1.234,56" → ponto=milhar, vírgula=decimal
            s = s.replace(".", "").replace(",", ".")
        elif last_comma > 0 and last_dot > last_comma:
            # Formato en-US com decimal: "1,234.56" → vírgula=milhar, ponto=decimal
            s = s.replace(",", "")
        elif last_comma > 0 and last_dot < 0:
            # Só vírgula — pode ser pt-BR decimal ("36,97") ou pt-BR milhar ("1,234")
            # Heurística: se 3 dígitos após vírgula → milhar; caso contrário → decimal
            after_comma = s[last_comma + 1:]
            if len(after_comma) == 3 and after_comma.isdigit():
                s = s.replace(",", "")   # milhar pt-BR: "1,234" → 1234
            else:
                s = s.replace(",", ".")  # decimal pt-BR: "36,97" → 36.97
        elif last_dot > 0 and last_comma < 0:
            # Só ponto — pode ser en-US decimal ("36.97") ou pt-BR milhar ("1.234")
            # Heurística: 3 dígitos após ponto → milhar; caso contrário → decimal
            after_dot = s[last_dot + 1:]
            if len(after_dot) == 3 and after_dot.isdigit():
                s = s.replace(".", "")   # milhar: "12.345" → 12345
            # else: já é float válido ("36.97")
        # Caso sem separador de grupo: "1234" ou "36" → float diretamente
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(val: str) -> str:
    """Tenta converter data do Google Ads para YYYY-MM-DD. Retorna '' em falha."""
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y",
                "%d de %b. de %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Tenta extrair data de strings como "2025-05-19 – 2025-05-25" (semanas)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
    if m:
        return m.group(1)
    return ""


def _is_data_row(row: list[str]) -> bool:
    """Retorna True se a linha parece ser uma linha de dado (não cabeçalho/total/vazia)."""
    joined = " ".join(row).strip().lower()
    if not joined:
        return False
    skip_patterns = [
        "total", "google ads", "relatório", "report", "período",
        "account", "conta", "downloaded", "baixado",
    ]
    for p in skip_patterns:
        if joined.startswith(p):
            return False
    return True


def _find_header_row(rows: list[list[str]]) -> int:
    """
    Encontra o índice da linha de cabeçalho verdadeira.
    Critério: primeira linha onde alguma célula normalizada aparece no _COL_MAP.
    """
    for i, row in enumerate(rows):
        normalized = [_normalize_col(c) for c in row]
        hits = sum(1 for c in normalized if c in _COL_MAP)
        if hits >= 2:
            return i
    return -1


def parse(file_content: str | bytes) -> dict:
    """
    Parseia o CSV do Google Ads e retorna dict estruturado.

    Args:
        file_content: conteúdo do arquivo como str ou bytes (UTF-8 ou latin-1)

    Returns:
        dict com "campaigns", "daily", "date_from", "date_to", "raw_columns", "warnings"
    """
    warnings: list[str] = []

    # Decodifica se bytes
    if isinstance(file_content, bytes):
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                file_content = file_content.decode(enc)
                break
            except UnicodeDecodeError:
                pass

    # Remove BOM e normaliza quebras de linha
    file_content = file_content.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")

    # Lê todas as linhas como CSV
    reader = csv.reader(io.StringIO(file_content))
    all_rows: list[list[str]] = list(reader)

    # Encontra cabeçalho
    header_idx = _find_header_row(all_rows)
    if header_idx < 0:
        warnings.append("Não foi possível identificar o cabeçalho do CSV. Verifique se o arquivo é um export do Google Ads.")
        return {
            "campaigns": [], "daily": [],
            "date_from": "", "date_to": "",
            "raw_columns": [], "warnings": warnings,
        }

    raw_cols = all_rows[header_idx]
    normalized_cols = [_normalize_col(c) for c in raw_cols]

    # Mapeia índice → nome interno
    col_idx: dict[str, int] = {}
    for i, nc in enumerate(normalized_cols):
        internal = _COL_MAP.get(nc)
        if internal and internal not in col_idx:
            col_idx[internal] = i

    data_rows = all_rows[header_idx + 1:]

    campaigns: dict[str, dict] = {}  # name → acumulador
    daily:     list[dict]      = []
    all_dates: list[str]       = []

    def _get(row: list[str], key: str, default: str = "") -> str:
        idx = col_idx.get(key, -1)
        if idx < 0 or idx >= len(row):
            return default
        return row[idx].strip()

    def _num(row: list[str], key: str) -> float:
        return _parse_number(_get(row, key))

    for row in data_rows:
        if not any(c.strip() for c in row):
            continue  # linha vazia
        # Detecta "Total geral" ou "Grand Total"
        first_cell = row[0].strip().lower() if row else ""
        if re.match(r"(total|grand total|total geral)", first_cell):
            continue

        campaign_name = _get(row, "campaign") or "Sem campanha"
        date_str      = _parse_date(_get(row, "date"))
        impressions   = int(_num(row, "impressions"))
        clicks        = int(_num(row, "clicks"))
        ctr           = _num(row, "ctr")
        avg_cpc       = _num(row, "avg_cpc")
        cost          = _num(row, "cost")
        conversions   = _num(row, "conversions")
        conv_rate     = _num(row, "conv_rate")
        cost_per_conv = _num(row, "cost_per_conv")
        roas          = _num(row, "roas")

        # Acumula por campanha
        if campaign_name not in campaigns:
            campaigns[campaign_name] = {
                "name":         campaign_name,
                "impressions":  0,
                "clicks":       0,
                "cost":         0.0,
                "conversions":  0.0,
                "_ctr_sum":     0.0,
                "_ctr_n":       0,
                "_cpc_sum":     0.0,
                "_cpc_n":       0,
                "roas":         0.0,
                "_roas_n":      0,
            }
        c = campaigns[campaign_name]
        c["impressions"] += impressions
        c["clicks"]      += clicks
        c["cost"]        += cost
        c["conversions"] += conversions
        if ctr > 0:
            c["_ctr_sum"] += ctr;  c["_ctr_n"] += 1
        if avg_cpc > 0:
            c["_cpc_sum"] += avg_cpc; c["_cpc_n"] += 1
        if roas > 0:
            c["roas"] += roas * impressions; c["_roas_n"] += impressions

        # Agrega por data (se coluna date presente)
        if date_str:
            all_dates.append(date_str)
            # Procura se já temos entrada para essa data
            existing = next((d for d in daily if d["date"] == date_str), None)
            if existing:
                existing["impressions"] += impressions
                existing["clicks"]      += clicks
                existing["cost"]        += cost
                existing["conversions"] += conversions
            else:
                daily.append({
                    "date":        date_str,
                    "impressions": impressions,
                    "clicks":      clicks,
                    "cost":        cost,
                    "conversions": conversions,
                })

    # Pós-processa campanhas
    campaign_list = []
    for c in campaigns.values():
        impr = c["impressions"]
        clk  = c["clicks"]
        cost = c["cost"]
        conv = c["conversions"]
        ctr_calc  = round(clk / impr * 100, 2) if impr else (
                    c["_ctr_sum"] / c["_ctr_n"] if c["_ctr_n"] else 0.0)
        cpc_calc  = round(cost / clk, 2) if clk else (
                    c["_cpc_sum"] / c["_cpc_n"] if c["_cpc_n"] else 0.0)
        cpa_calc  = round(cost / conv, 2) if conv else 0.0
        roas_calc = round(c["roas"] / c["_roas_n"], 2) if c["_roas_n"] else 0.0
        cr_calc   = round(conv / clk * 100, 2) if clk else 0.0
        campaign_list.append({
            "name":         c["name"],
            "impressions":  impr,
            "clicks":       clk,
            "ctr":          ctr_calc,
            "avg_cpc":      cpc_calc,
            "cost":         round(cost, 2),
            "conversions":  round(conv, 1),
            "conv_rate":    cr_calc,
            "cost_per_conv": cpa_calc,
            "roas":         roas_calc,
        })

    # Ordena campanhas por custo (desc)
    campaign_list.sort(key=lambda x: x["cost"], reverse=True)

    # Ordena daily por data
    daily.sort(key=lambda x: x["date"])
    # Adiciona CTR e CPC aos daily
    for d in daily:
        d["ctr"]     = round(d["clicks"] / d["impressions"] * 100, 2) if d["impressions"] else 0.0
        d["avg_cpc"] = round(d["cost"] / d["clicks"], 2) if d["clicks"] else 0.0

    date_from = min(all_dates) if all_dates else ""
    date_to   = max(all_dates) if all_dates else ""

    if not campaign_list:
        warnings.append("Nenhuma campanha encontrada no CSV. Verifique se o arquivo contém dados de campanhas.")

    return {
        "campaigns":   campaign_list,
        "daily":       daily,
        "date_from":   date_from,
        "date_to":     date_to,
        "raw_columns": raw_cols,
        "warnings":    warnings,
    }
