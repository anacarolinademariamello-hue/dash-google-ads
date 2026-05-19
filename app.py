"""
app.py — Dash Google Ads · Relatório de campanhas Google Ads

Fluxo:
  1. Seleciona cliente (cadastrado no Supabase via Gerenciador de Clientes)
  2. Faz upload do CSV exportado do Google Ads Manager
  3. Clica em "Gerar Relatório"
  4. Visualiza o relatório + Score de Saúde + Análise IA
  5. Baixa o HTML e/ou salva no histórico

Tabs:
  📊 Relatório    — gerar e visualizar
  📜 Histórico    — relatórios anteriores do cliente
"""
from __future__ import annotations

import re
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

from src import csv_parser, processor, html_gen, ai_analysis, supabase_db
from src import health_score as hs

# ── Configuração da página ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="Google Ads Reports · Dash Digital",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS customizado ────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Fundo geral ────────────────────────────────── */
[data-testid="stAppViewContainer"] { background: #f0f3f8; }

/* ── Sidebar escura (mesmo padrão do Relatório Meta) */
[data-testid="stSidebar"] {
  background: #0d2137 !important;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stFileUploader label,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown div { color: #cbd5e1 !important; }
/* Upload dropzone com contraste na sidebar escura */
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] {
  background: #1a3350 !important;
  border: 2px dashed #4a7fa8 !important;
  border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] *,
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] small,
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] span,
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] p {
  color: #94b8d4 !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] svg {
  fill: #94b8d4 !important;
  stroke: #94b8d4 !important;
}
/* Botão "Upload" dentro do dropzone — alvo por kind=secondary e por role=button */
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] button,
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] [role="button"],
[data-testid="stSidebar"] [data-testid="stFileUploader"] button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
  background: #f8b940 !important;
  color: #003f7c !important;
  border: none !important;
  font-weight: 700 !important;
  border-radius: 6px !important;
  opacity: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] button span,
[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] button span {
  color: #003f7c !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: #1a3350 !important;
  border-color: #2e5070 !important;
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] hr { border-color: #2e5070 !important; }
[data-testid="stSidebar"] .stButton > button {
  background: linear-gradient(135deg, #f8b940, #d99a20) !important;
  color: #003f7c !important;
  border: none !important;
  font-weight: 700 !important;
}
[data-testid="stSidebar"] .stButton > button:disabled {
  background: #2e5070 !important;
  color: #6b8aa8 !important;
}

/* ── Tabs ──────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
  border-radius: 8px;
  padding: 8px 18px;
  font-weight: 600;
}
.stTabs [aria-selected="true"] {
  background: #003f7c;
  color: #fff;
}

/* ── Botões na área principal ──────────────────── */
div.stButton > button {
  background: linear-gradient(135deg, #003f7c, #1a5a9a);
  color: #fff !important;
  border: none;
  border-radius: 10px;
  font-weight: 700;
  padding: 10px 24px;
  width: 100%;
}
div.stButton > button:hover { opacity: .9; }
div.stButton > button:disabled {
  background: #e5e7eb !important;
  color: #9ca3af !important;
  cursor: not-allowed;
}

/* ── Cards de métricas ─────────────────────────── */
.metric-box {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
}
.metric-val { font-size: 1.4rem; font-weight: 800; color: #003f7c; }
.metric-lbl { font-size: .75rem; color: #6b7280; margin-top: 3px; }

/* ── Avisos ────────────────────────────────────── */
.info-box {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 10px;
  padding: 14px 18px;
  font-size: .88rem;
  color: #92400e;
  margin: 12px 0;
}
.success-box {
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 10px;
  padding: 14px 18px;
  font-size: .88rem;
  color: #14532d;
  margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _br(v, d=0):
    try:
        s = f"{float(v):,.{d}f}" if d else f"{int(round(float(v))):,}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)


@st.cache_data(ttl=120)
def _load_clients():
    return supabase_db.get_clients()


# ── Sidebar ─────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        "<div style='padding:16px 4px 12px;'>"
        "<span style='font-size:1.5rem;'>📊</span> "
        "<span style='font-size:1.1rem;font-weight:800;color:#f8b940;'>Google Ads</span>"
        "<br><span style='font-size:.75rem;color:#94a3b8;'>Dash Digital · Relatórios</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    clients_sidebar = _load_clients()

    if not clients_sidebar:
        st.markdown(
            '<div style="background:#1a3350;border:1px solid #2e5070;border-radius:8px;'
            'padding:12px;font-size:.82rem;color:#94b8d4;">'
            '⚠️ Nenhum cliente com Google Ads configurado.<br>'
            '<a href="https://dash-clientes-app.streamlit.app/" target="_blank" '
            'style="color:#f8b940;">Cadastrar no Gerenciador →</a>'
            '</div>',
            unsafe_allow_html=True,
        )
        selected_client = None
    else:
        client_names = [c["name"] for c in clients_sidebar]
        chosen_name  = st.selectbox("Cliente", client_names)
        selected_client = next((c for c in clients_sidebar if c["name"] == chosen_name), None)
        if selected_client and selected_client.get("google_ads_account_id"):
            st.markdown(
                f'<div style="font-size:.72rem;color:#64748b;margin-top:2px;">'
                f'🔵 Conta: <code style="color:#94b8d4;">{selected_client["google_ads_account_id"]}</code>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.78rem;color:#94a3b8;margin-bottom:6px;'>"
        "<strong style='color:#cbd5e1;'>📂 Upload do CSV</strong><br>"
        "Exporte pelo Google Ads Manager:<br>"
        "<strong>Relatórios → Pré-definidos → Desempenho → Campanha</strong><br>"
        "Selecione o período e baixe como CSV."
        "</div>",
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Arquivo CSV do Google Ads",
        type=["csv"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    gerar = st.button("🚀 Gerar Relatório", disabled=(not selected_client or not uploaded_file))

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.72rem;color:#64748b;'>"
        "Clientes gerenciados no "
        "<a href='https://dash-clientes-app.streamlit.app/' target='_blank' "
        "style='color:#f8b940;'>Gerenciador de Clientes</a>"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Layout ─────────────────────────────────────────────────────────────────────

# Cabeçalho
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("<div style='font-size:2.8rem;line-height:1;padding-top:8px;'>📊</div>", unsafe_allow_html=True)
with col_title:
    st.markdown(
        "<h1 style='margin:0;font-size:1.6rem;color:#003f7c;'>Google Ads Reports</h1>"
        "<div style='color:#6b7280;font-size:.85rem;margin-top:2px;'>Dash Digital · Relatórios de campanhas Google Ads</div>",
        unsafe_allow_html=True,
    )

st.divider()

# Tabs principais
tab_report, tab_history = st.tabs(["📊 Relatório", "📜 Histórico"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RELATÓRIO
# ══════════════════════════════════════════════════════════════════════════════

with tab_report:
    if not selected_client:
        st.markdown(
            '<div class="info-box">👈 Selecione um cliente na barra lateral e faça upload do CSV para gerar o relatório.</div>',
            unsafe_allow_html=True,
        )
    elif not uploaded_file:
        st.markdown(
            '<div class="info-box">📂 Faça upload do CSV exportado do Google Ads Manager para continuar.</div>',
            unsafe_allow_html=True,
        )
    elif gerar:
        with st.spinner("🔄 Processando CSV..."):
            raw_content = uploaded_file.read()
            parsed      = csv_parser.parse(raw_content)

        # Avisos do parser
        for w in parsed.get("warnings", []):
            st.warning(w)

        if not parsed["campaigns"]:
            st.error("❌ Nenhuma campanha encontrada no CSV. Verifique o arquivo e tente novamente.")
            st.stop()

        with st.spinner("📊 Calculando métricas..."):
            data = processor.process(parsed)

        # Preview rápido de métricas
        st.markdown("#### 📈 Resumo do Período")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        metrics_preview = [
            (c1, "Impressões", _br(data["total_impressions"])),
            (c2, "Cliques",    _br(data["total_clicks"])),
            (c3, "CTR",        f"{_br(data['avg_ctr'], 2)}%"),
            (c4, "Investimento", f"R${_br(data['total_cost'], 2)}"),
            (c5, "Conversões", _br(data["total_conversions"], 1)),
            (c6, "CPC Médio",  f"R${_br(data['avg_cpc'], 2)}"),
        ]
        for col, label, val in metrics_preview:
            with col:
                st.markdown(
                    f'<div class="metric-box"><div class="metric-val">{val}</div>'
                    f'<div class="metric-lbl">{label}</div></div>',
                    unsafe_allow_html=True,
                )

        # Score de saúde
        with st.spinner("🏥 Calculando Score de Saúde..."):
            prev_metrics = supabase_db.get_previous_metrics(
                selected_client["key"],
                data["date_from"] or datetime.now().strftime("%Y-%m-%d"),
                data["date_to"]   or datetime.now().strftime("%Y-%m-%d"),
            )
            health = hs.calculate(data, prev_metrics)

        st.markdown("#### 🏥 Score de Saúde das Campanhas")
        score_col, grade_col = st.columns([1, 3])
        with score_col:
            score_color = health["color"]
            delta       = health.get("delta")
            delta_html  = ""
            if delta is not None:
                d_sign  = "+" if delta >= 0 else ""
                d_color = "#16a34a" if delta >= 0 else "#dc2626"
                d_arrow = "▲" if delta >= 0 else "▼"
                delta_html = (
                    f'<div style="font-size:.75rem;font-weight:600;color:{d_color};margin-top:4px;">'
                    f'{d_arrow} {d_sign}{delta} pts vs período anterior</div>'
                )
            st.markdown(
                f'<div style="text-align:center;background:#fff;border:2px solid {score_color};'
                f'border-radius:12px;padding:20px;">'
                f'<div style="font-size:.7rem;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;">Score de Saúde</div>'
                f'<div style="font-size:3rem;font-weight:800;color:{score_color};line-height:1.2;">'
                f'{health["score"]}<span style="font-size:1rem;color:#9ca3af;">/100</span></div>'
                f'<div style="font-weight:700;color:{score_color};">{health["grade"]}</div>'
                f'{delta_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with grade_col:
            bd = health.get("breakdown", {})
            breakdown_labels = {
                "ctr":          ("CTR", 25),
                "conv_rate":    ("Taxa de conversão", 25),
                "roas":         ("ROAS", 20),
                "eficiencia":   ("Eficiência / CPA", 15),
                "consistencia": ("Consistência", 15),
            }
            for key, (label, max_pts) in breakdown_labels.items():
                val = bd.get(key, 0)
                pct = val / max_pts if max_pts else 0
                bar_color = "#16a34a" if pct >= .7 else "#d97706" if pct >= .4 else "#dc2626"
                st.markdown(
                    f'<div style="margin-bottom:6px;">'
                    f'<div style="display:flex;justify-content:space-between;font-size:.78rem;color:#6b7280;">'
                    f'<span>{label}</span><span style="font-weight:700;color:#374151;">{val}/{max_pts}</span></div>'
                    f'<div style="background:#f3f4f6;border-radius:4px;height:6px;margin-top:3px;">'
                    f'<div style="background:{bar_color};width:{int(pct*100)}%;height:6px;border-radius:4px;"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

        # Análise IA
        ai_result = None
        with st.spinner("🤖 Gerando análise estratégica com IA..."):
            ai_result = ai_analysis.generate_analysis(data, selected_client, prev_metrics)

        if ai_result:
            st.markdown("#### 🧭 Análise Estratégica (IA)")
            col_str, col_att = st.columns(2)
            with col_str:
                st.markdown("**✅ Pontos Fortes**")
                for emoji, text in ai_result.get("strengths", []):
                    clean_text = re.sub(r"<[^>]+>", "", text)
                    st.markdown(f"- {emoji} {clean_text}")
            with col_att:
                st.markdown("**⚠️ Pontos de Atenção**")
                for emoji, text in ai_result.get("attentions", []):
                    clean_text = re.sub(r"<[^>]+>", "", text)
                    st.markdown(f"- {emoji} {clean_text}")

        # Gera HTML do relatório
        with st.spinner("🎨 Gerando relatório HTML..."):
            generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")
            html_report  = html_gen.generate(
                client=selected_client,
                data=data,
                health=health,
                ai_analysis=ai_result,
                generated_at=generated_at,
            )

        # Preview e Download
        st.markdown("---")
        col_dl, col_save = st.columns(2)
        period_slug = data.get("period_label", "").replace("/", "-").replace(" ", "_").replace("–", "a")
        filename    = f"google-ads_{selected_client['key']}_{period_slug}.html"

        with col_dl:
            st.download_button(
                label="⬇️ Baixar Relatório HTML",
                data=html_report.encode("utf-8"),
                file_name=filename,
                mime="text/html",
            )

        with col_save:
            if st.button("💾 Salvar no Histórico"):
                _ai_safe = None
                if ai_result and isinstance(ai_result, dict):
                    try:
                        _ai_safe = {
                            "strengths":  [[e, t] for e, t in (ai_result.get("strengths") or [])],
                            "attentions": [[e, t] for e, t in (ai_result.get("attentions") or [])],
                        }
                    except Exception:
                        pass
                ok = supabase_db.save_report_metrics(
                    client_key   = selected_client["key"],
                    week_from    = data.get("date_from", ""),
                    week_to      = data.get("date_to", ""),
                    data         = data,
                    ai_analysis  = _ai_safe,
                    health_score = health["score"],
                )
                if ok:
                    st.markdown(
                        '<div class="success-box">'
                        '✅ <strong>Salvo no histórico!</strong> '
                        'No próximo relatório deste cliente, o Score de Saúde e a Análise IA '
                        'usarão automaticamente estes dados como comparativo de período anterior.'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.error("❌ Falha ao salvar. Verifique as credenciais do Supabase.")

        # Aviso de histórico disponível / ausente
        if prev_metrics:
            st.markdown(
                '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;'
                'padding:10px 14px;font-size:.8rem;color:#1e40af;margin-top:8px;">'
                '📊 <strong>Dados históricos encontrados.</strong> '
                'O Score de Saúde e a Análise IA já incluem comparativo com o período anterior.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#fafafa;border:1px solid #e5e7eb;border-radius:8px;'
                'padding:10px 14px;font-size:.8rem;color:#6b7280;margin-top:8px;">'
                '💡 <strong>Primeiro relatório deste cliente.</strong> '
                'Salve-o no histórico para que o próximo relatório tenha comparativo automático e análise IA mais precisa.'
                '</div>',
                unsafe_allow_html=True,
            )

        # Preview do relatório
        with st.expander("👁️ Pré-visualizar relatório", expanded=False):
            components.html(html_report, height=800, scrolling=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — HISTÓRICO
# ══════════════════════════════════════════════════════════════════════════════

with tab_history:
    st.markdown("### 📜 Histórico de Relatórios")

    if not supabase_db.is_configured():
        st.warning("⚠️ Supabase não configurado.")
    else:
        hist_clients = _load_clients()
        if not hist_clients:
            st.info("Nenhum cliente cadastrado.")
        else:
            chosen_hist = st.selectbox(
                "Cliente",
                [c["name"] for c in hist_clients],
                key="hist_client",
            )
            sel_hist = next((c for c in hist_clients if c["name"] == chosen_hist), None)

            if sel_hist:
                history = supabase_db.get_history_list(sel_hist["key"], limit=12)
                if not history:
                    st.info("Nenhum relatório salvo para este cliente ainda.")
                else:
                    for entry in history:
                        wf = entry.get("week_from", "")
                        wt = entry.get("week_to", "")
                        gen = entry.get("generated_at", "")[:16].replace("T", " ") if entry.get("generated_at") else ""
                        m  = entry.get("metrics") or {}
                        score       = m.get("health_score", 0)
                        score_color = "#16a34a" if score >= 70 else "#d97706" if score >= 55 else "#dc2626"

                        with st.expander(f"📅 {wf} → {wt}  |  Score: {score}/100  |  Gerado: {gen}"):
                            c1, c2, c3, c4, c5 = st.columns(5)
                            preview_metrics = [
                                (c1, "Impressões",   _br(m.get("total_impressions", 0))),
                                (c2, "Cliques",      _br(m.get("total_clicks", 0))),
                                (c3, "CTR",          f"{_br(m.get('avg_ctr', 0), 2)}%"),
                                (c4, "Investimento", f"R${_br(m.get('total_cost', 0), 2)}"),
                                (c5, "Score",        f"{score}/100"),
                            ]
                            for col, label, val in preview_metrics:
                                with col:
                                    color = score_color if label == "Score" else "#92400e"
                                    st.markdown(
                                        f'<div class="metric-box">'
                                        f'<div class="metric-val" style="color:{color};">{val}</div>'
                                        f'<div class="metric-lbl">{label}</div></div>',
                                        unsafe_allow_html=True,
                                    )

                            camps = m.get("top_campaigns", [])
                            if camps:
                                st.markdown("**Campanhas do período:**")
                                for camp in camps[:3]:
                                    st.markdown(
                                        f"- **{camp.get('name','')}** — "
                                        f"CTR {camp.get('ctr',0):.2f}% | "
                                        f"Custo R${camp.get('cost',0):.2f} | "
                                        f"Conv. {camp.get('conversions',0):.1f}"
                                    )
