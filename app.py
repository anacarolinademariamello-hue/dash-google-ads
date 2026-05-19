"""
app.py — Dash Google Ads · Relatório de campanhas Google Ads

Fluxo:
  1. Seleciona cliente (cadastrado no Supabase)
  2. Faz upload do CSV exportado do Google Ads Manager
  3. Clica em "Gerar Relatório"
  4. Visualiza o relatório + Score de Saúde + Análise IA
  5. Baixa o HTML e/ou salva no histórico

Tabs:
  📊 Relatório    — gerar e visualizar
  👥 Clientes     — cadastrar / gerenciar clientes Google Ads
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
[data-testid="stAppViewContainer"] { background: #f0f3f8; }
[data-testid="stSidebar"] { background: #fff; border-right: 1px solid #e5e7eb; }

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

.metric-box {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
}
.metric-val { font-size: 1.4rem; font-weight: 800; color: #003f7c; }
.metric-lbl { font-size: .75rem; color: #6b7280; margin-top: 3px; }

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
tab_report, tab_clients, tab_history = st.tabs(["📊 Relatório", "👥 Clientes", "📜 Histórico"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RELATÓRIO
# ══════════════════════════════════════════════════════════════════════════════

with tab_report:
    col_sidebar, col_main = st.columns([1, 3], gap="large")

    # ── Painel lateral ────────────────────────────────────────────────────────
    with col_sidebar:
        st.markdown("### ⚙️ Configuração")

        clients = _load_clients()

        if not clients:
            st.warning("Nenhum cliente cadastrado. Vá para a aba **👥 Clientes** para cadastrar.")
            selected_client = None
        else:
            client_names = [c["name"] for c in clients]
            chosen_name  = st.selectbox("Cliente", client_names)
            selected_client = next((c for c in clients if c["name"] == chosen_name), None)

        st.markdown("---")
        st.markdown("**📂 Upload do CSV**")
        st.markdown(
            "<div style='font-size:.78rem;color:#6b7280;margin-bottom:8px;'>"
            "Exporte o relatório pelo Google Ads Manager:<br>"
            "<strong>Relatórios → Pré-definidos → Desempenho → Campanha</strong><br>"
            "Selecione o período e clique em Download (CSV)"
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

    # ── Área principal ────────────────────────────────────────────────────────
    with col_main:
        if not selected_client:
            st.markdown(
                '<div class="info-box">👈 Selecione um cliente e faça upload do CSV para gerar o relatório.</div>',
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
                st.markdown(
                    f'<div style="text-align:center;background:#fff;border:2px solid {score_color};'
                    f'border-radius:12px;padding:20px;">'
                    f'<div style="font-size:.7rem;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;">Score de Saúde</div>'
                    f'<div style="font-size:3rem;font-weight:800;color:{score_color};line-height:1.2;">'
                    f'{health["score"]}<span style="font-size:1rem;color:#9ca3af;">/100</span></div>'
                    f'<div style="font-weight:700;color:{score_color};">{health["grade"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with grade_col:
                bd = health.get("breakdown", {})
                breakdown_labels = {
                    "ctr":         ("CTR", 25),
                    "conv_rate":   ("Taxa de conversão", 25),
                    "roas":        ("ROAS", 20),
                    "eficiencia":  ("Eficiência / CPA", 15),
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

            # Análise IA — tenta sempre que a ANTHROPIC_API_KEY estiver nos secrets
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
                        st.markdown('<div class="success-box">✅ Salvo no histórico do Supabase!</div>', unsafe_allow_html=True)
                    else:
                        st.error("❌ Falha ao salvar. Verifique as credenciais do Supabase.")

            # Preview do relatório
            with st.expander("👁️ Pré-visualizar relatório", expanded=False):
                components.html(html_report, height=800, scrolling=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CLIENTES
# ══════════════════════════════════════════════════════════════════════════════

with tab_clients:
    st.markdown("### 👥 Gerenciar Clientes Google Ads")

    if not supabase_db.is_configured():
        st.warning("⚠️ Supabase não configurado. Configure `supabase_url` e `supabase_service_key` nos secrets.")
    else:
        # Lista clientes existentes
        clients = _load_clients()
        if clients:
            st.markdown(f"**{len(clients)} cliente(s) cadastrado(s):**")
            for c in clients:
                with st.expander(f"📋 {c['name']}"):
                    col_info, col_action = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"**Key:** `{c['key']}`")
                        if c.get("industry"):
                            st.markdown(f"**Setor:** {c['industry']}")
                        if c.get("notes"):
                            st.markdown(f"**Observações:** {c['notes']}")
                        goals = c.get("goals") or {}
                        if goals:
                            goal_parts = []
                            if goals.get("target_ctr"):  goal_parts.append(f"CTR alvo: {goals['target_ctr']}%")
                            if goals.get("target_cpa"):  goal_parts.append(f"CPA alvo: R${goals['target_cpa']}")
                            if goals.get("target_roas"): goal_parts.append(f"ROAS alvo: {goals['target_roas']}x")
                            if goals.get("max_cpc"):     goal_parts.append(f"CPC máx: R${goals['max_cpc']}")
                            if goal_parts:
                                st.markdown("**Metas:** " + " · ".join(goal_parts))
                    with col_action:
                        if st.button("🗑️ Desativar", key=f"del_{c['key']}"):
                            ok, msg = supabase_db.deactivate_client(c["key"])
                            if ok:
                                _load_clients.clear()
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("Nenhum cliente cadastrado ainda.")

        st.markdown("---")
        st.markdown("### ➕ Cadastrar Novo Cliente")

        with st.form("form_new_client", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_name     = st.text_input("Nome do cliente *", placeholder="Ex: Loja ABC")
                new_key      = st.text_input("Key (identificador único) *", placeholder="loja-abc")
                new_industry = st.text_input("Setor / Indústria", placeholder="E-commerce, Educação, Saúde...")
            with col2:
                new_notes      = st.text_area("Observações", placeholder="Informações relevantes sobre o cliente...")
                st.markdown("**Metas (opcional)**")
                g_col1, g_col2 = st.columns(2)
                with g_col1:
                    goal_ctr  = st.number_input("CTR alvo (%)", min_value=0.0, step=0.1, value=0.0)
                    goal_cpa  = st.number_input("CPA alvo (R$)", min_value=0.0, step=1.0, value=0.0)
                with g_col2:
                    goal_roas = st.number_input("ROAS alvo (x)", min_value=0.0, step=0.1, value=0.0)
                    goal_cpc  = st.number_input("CPC máx. (R$)", min_value=0.0, step=0.1, value=0.0)

            submitted = st.form_submit_button("💾 Cadastrar Cliente")
            if submitted:
                if not new_name or not new_key:
                    st.error("Nome e Key são obrigatórios.")
                else:
                    goals = {}
                    if goal_ctr > 0:  goals["target_ctr"]  = goal_ctr
                    if goal_cpa > 0:  goals["target_cpa"]  = goal_cpa
                    if goal_roas > 0: goals["target_roas"] = goal_roas
                    if goal_cpc > 0:  goals["max_cpc"]     = goal_cpc

                    ok, msg = supabase_db.save_client({
                        "key":      new_key.strip().lower().replace(" ", "-"),
                        "name":     new_name.strip(),
                        "industry": new_industry.strip(),
                        "goals":    goals,
                        "notes":    new_notes.strip(),
                        "active":   True,
                    })
                    if ok:
                        _load_clients.clear()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HISTÓRICO
# ══════════════════════════════════════════════════════════════════════════════

with tab_history:
    st.markdown("### 📜 Histórico de Relatórios")

    if not supabase_db.is_configured():
        st.warning("⚠️ Supabase não configurado.")
    else:
        clients = _load_clients()
        if not clients:
            st.info("Nenhum cliente cadastrado.")
        else:
            chosen_hist = st.selectbox(
                "Cliente",
                [c["name"] for c in clients],
                key="hist_client",
            )
            sel_hist = next((c for c in clients if c["name"] == chosen_hist), None)

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
                        score     = m.get("health_score", 0)
                        score_color = "#16a34a" if score >= 70 else "#d97706" if score >= 55 else "#dc2626"

                        with st.expander(f"📅 {wf} → {wt}  |  Score: {score}/100  |  Gerado: {gen}"):
                            c1, c2, c3, c4, c5 = st.columns(5)
                            preview_metrics = [
                                (c1, "Impressões",  _br(m.get("total_impressions", 0))),
                                (c2, "Cliques",     _br(m.get("total_clicks", 0))),
                                (c3, "CTR",         f"{_br(m.get('avg_ctr', 0), 2)}%"),
                                (c4, "Investimento",f"R${_br(m.get('total_cost', 0), 2)}"),
                                (c5, "Score",       f"{score}/100"),
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
                                for c in camps[:3]:
                                    st.markdown(
                                        f"- **{c.get('name','')}** — "
                                        f"CTR {c.get('ctr',0):.2f}% | "
                                        f"Custo R${c.get('cost',0):.2f} | "
                                        f"Conv. {c.get('conversions',0):.1f}"
                                    )
