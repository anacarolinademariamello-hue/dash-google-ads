"""
supabase_db.py — Integração com Supabase para o dash-google-ads.

Usa o MESMO projeto Supabase dos outros apps (dash-relatorios, dash-copy-ads).
Tabelas próprias (não conflita com as existentes):
  google_ads_clients       — clientes com campanhas Google Ads
  google_ads_report_history — histórico de relatórios por cliente/semana

SQL para criar as tabelas (rode no Supabase SQL editor):
─────────────────────────────────────────────────────────────────────────────
  create table google_ads_clients (
    id         serial primary key,
    key        text unique not null,
    name       text not null,
    industry   text default '',
    goals      jsonb default '{}',
    notes      text default '',
    active     boolean default true,
    created_at timestamptz default now()
  );

  create table google_ads_report_history (
    id           serial primary key,
    client_key   text not null,
    week_from    date not null,
    week_to      date not null,
    metrics      jsonb,
    generated_at timestamptz default now()
  );

  create index on google_ads_report_history (client_key, week_from);
─────────────────────────────────────────────────────────────────────────────

Secrets necessários (mesmo .streamlit/secrets.toml):
  supabase_url         = "https://<project>.supabase.co"
  supabase_service_key = "<service_role key>"
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

import requests


# ── Credenciais ────────────────────────────────────────────────────────────────

def _get_creds() -> tuple[str, str]:
    try:
        import streamlit as st
        url = st.secrets.get("supabase_url", "") or ""
        key = st.secrets.get("supabase_service_key", "") or ""
        return url, key
    except Exception:
        import os
        return (
            os.environ.get("SUPABASE_URL", ""),
            os.environ.get("SUPABASE_SERVICE_KEY", ""),
        )


def is_configured() -> bool:
    url, key = _get_creds()
    return bool(url and key)


def _headers(prefer: str = "return=representation") -> dict:
    _, key = _get_creds()
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        prefer,
    }


def _rest(table: str) -> str:
    url, _ = _get_creds()
    return f"{url}/rest/v1/{table}"


# ── Clientes ───────────────────────────────────────────────────────────────────

def get_clients() -> list[dict]:
    """
    Carrega clientes ativos da tabela central `clients` que possuem
    google_ads_account_id preenchido — só esses aparecem no app Google Ads.
    """
    if not is_configured():
        return []
    try:
        resp = requests.get(
            _rest("clients"),
            headers=_headers(),
            params={
                "active":                 "eq.true",
                "google_ads_account_id":  "neq.",          # só quem tem ID preenchido
                "order":                  "name.asc",
                "select":                 "key,name,nicho,goals,observations,google_ads_account_id",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        result = []
        for r in rows:
            goals = r.get("goals") or {}
            if isinstance(goals, str):
                try:
                    goals = json.loads(goals)
                except Exception:
                    goals = {}
            result.append({
                "key":                   r["key"],
                "name":                  r["name"],
                "industry":              r.get("nicho") or "",   # nicho → industry
                "goals":                 goals,
                "notes":                 r.get("observations") or "",
                "google_ads_account_id": r.get("google_ads_account_id") or "",
            })
        return result
    except Exception:
        return []


# ── Histórico de relatórios ────────────────────────────────────────────────────

def save_report_metrics(
    client_key: str,
    week_from:  str,
    week_to:    str,
    data:       dict,
    ai_analysis: Optional[dict] = None,
    health_score: int = 0,
) -> bool:
    """
    Salva snapshot de métricas do período no histórico.
    Colunas espelham os campos de processor.process() + campos derivados.
    """
    if not is_configured():
        return False

    top_campaigns = [
        {
            "name":         c.get("name", ""),
            "impressions":  c.get("impressions", 0),
            "clicks":       c.get("clicks", 0),
            "ctr":          round(float(c.get("ctr", 0)), 2),
            "avg_cpc":      round(float(c.get("avg_cpc", 0)), 2),
            "cost":         round(float(c.get("cost", 0)), 2),
            "conversions":  round(float(c.get("conversions", 0)), 1),
            "conv_rate":    round(float(c.get("conv_rate", 0)), 2),
            "cost_per_conv": round(float(c.get("cost_per_conv", 0)), 2),
            "roas":         round(float(c.get("roas", 0)), 2),
            "status":       c.get("status", ""),
        }
        for c in data.get("campaigns", [])[:5]
    ]

    metrics = {
        "total_impressions": data.get("total_impressions", 0),
        "total_clicks":      data.get("total_clicks", 0),
        "total_cost":        data.get("total_cost", 0),
        "total_conversions": data.get("total_conversions", 0),
        "avg_ctr":           data.get("avg_ctr", 0),
        "avg_cpc":           data.get("avg_cpc", 0),
        "conv_rate":         data.get("conv_rate", 0),
        "cost_per_conv":     data.get("cost_per_conv", 0),
        "avg_roas":          data.get("avg_roas", 0),
        "days":              data.get("days", 0),
        "total_campaigns":   data.get("total_campaigns", 0),
        "top_campaigns":     top_campaigns,
        "health_score":      health_score,
        "ai_analysis":       ai_analysis,
    }

    payload = {
        "client_key": client_key,
        "week_from":  week_from,
        "week_to":    week_to,
        "metrics":    json.dumps(metrics),
    }

    try:
        resp = requests.post(
            _rest("google_ads_report_history"),
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def get_previous_metrics(
    client_key: str,
    week_from:  str,
    week_to:    str,
) -> Optional[dict]:
    """
    Busca métricas do período anterior (mesma duração, imediatamente anterior).
    Ex: atual = 12/05–18/05 (7 dias) → busca 05/05–11/05
    """
    if not is_configured():
        return None
    try:
        df    = date.fromisoformat(week_from)
        dt    = date.fromisoformat(week_to)
        n     = (dt - df).days + 1
        p_to  = (df - timedelta(days=1)).isoformat()
        p_from = (df - timedelta(days=n)).isoformat()

        resp = requests.get(
            _rest("google_ads_report_history"),
            headers=_headers(),
            params={
                "client_key": f"eq.{client_key}",
                "week_from":  f"eq.{p_from}",
                "week_to":    f"eq.{p_to}",
                "order":      "generated_at.desc",
                "limit":      "1",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            raw = rows[0].get("metrics", {})
            if isinstance(raw, str):
                raw = json.loads(raw)
            return raw
    except Exception:
        pass
    return None


def get_history_list(client_key: str, limit: int = 10) -> list[dict]:
    """Retorna os últimos N relatórios do cliente."""
    if not is_configured():
        return []
    try:
        resp = requests.get(
            _rest("google_ads_report_history"),
            headers=_headers(),
            params={
                "client_key": f"eq.{client_key}",
                "order":      "generated_at.desc",
                "limit":      str(limit),
                "select":     "week_from,week_to,generated_at,metrics",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json()
        for r in rows:
            if isinstance(r.get("metrics"), str):
                try:
                    r["metrics"] = json.loads(r["metrics"])
                except Exception:
                    pass
        return rows
    except Exception:
        return []


def get_all_clients_last_upload(client_keys: list[str]) -> dict[str, Optional[str]]:
    """
    Para cada client_key, retorna a data do último upload (week_to do último relatório).
    Usado pelo script de lembrete semanal.
    Retorna dict: {client_key: "YYYY-MM-DD" | None}
    """
    result = {k: None for k in client_keys}
    if not is_configured() or not client_keys:
        return result
    try:
        # Busca o mais recente de cada cliente em uma única query
        # Supabase não suporta GROUP BY direto, então buscamos os últimos N e filtramos
        resp = requests.get(
            _rest("google_ads_report_history"),
            headers=_headers(),
            params={
                "order":  "generated_at.desc",
                "limit":  str(len(client_keys) * 3),  # margem
                "select": "client_key,week_to",
            },
            timeout=10,
        )
        resp.raise_for_status()
        for row in resp.json():
            ck = row.get("client_key", "")
            if ck in result and result[ck] is None:
                result[ck] = row.get("week_to")
    except Exception:
        pass
    return result
