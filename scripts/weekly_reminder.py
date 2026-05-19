"""
weekly_reminder.py — Lembrete semanal para upload dos dados do Google Ads.

Roda via GitHub Actions toda segunda-feira às 09:00 BRT.
Para cada cliente ativo no Supabase:
  - Verifica quando foi o último upload de dados
  - Se faz mais de 6 dias (sem upload desta semana), inclui no lembrete
  - Envia um único e-mail com a lista de clientes que precisam de dados

Variáveis de ambiente necessárias (GitHub Secrets):
  SUPABASE_URL         — URL do projeto Supabase
  SUPABASE_SERVICE_KEY — chave service_role do Supabase
  GMAIL_USER           — e-mail Gmail remetente
  GMAIL_APP_PASSWORD   — senha de app do Gmail
  EMAIL_TO             — destinatário(s), separados por vírgula
"""
import os
import sys
import logging
import smtplib
from datetime import date, timedelta, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import supabase_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Verificação de ambiente ────────────────────────────────────────────────────

def _check_env() -> bool:
    required = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD", "EMAIL_TO")
    missing  = [k for k in required if not os.environ.get(k)]
    if missing:
        log.error("Variáveis de ambiente ausentes: %s", ", ".join(missing))
        return False
    return True


# ── E-mail ─────────────────────────────────────────────────────────────────────

def _build_reminder_html(clients_needing_upload: list[dict], today: date) -> str:
    """Monta o e-mail HTML de lembrete."""
    generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")
    week_label   = today.strftime("%d/%m/%Y")

    rows_html = ""
    for c in clients_needing_upload:
        last_upload = c.get("last_upload")
        if last_upload:
            try:
                last_dt     = date.fromisoformat(last_upload)
                days_ago    = (today - last_dt).days
                last_label  = f"{last_dt.strftime('%d/%m/%Y')} ({days_ago} dias atrás)"
                badge_color = "#fef3c7"
                badge_text  = "#92400e"
            except Exception:
                last_label  = last_upload
                badge_color = "#f3f4f6"
                badge_text  = "#374151"
        else:
            last_label  = "Nunca"
            badge_color = "#fee2e2"
            badge_text  = "#7f1d1d"

        rows_html += f"""
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6;">
            <div style="font-weight:600;font-size:.9rem;color:#111827;">{c['name']}</div>
            {f'<div style="font-size:.75rem;color:#9ca3af;">{c.get("industry","")}</div>' if c.get("industry") else ''}
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6;">
            <span style="background:{badge_color};color:{badge_text};font-size:.78rem;
                  font-weight:600;padding:4px 10px;border-radius:8px;">{last_label}</span>
          </td>
        </tr>"""

    steps_html = """
      <ol style="margin:8px 0 0;padding-left:20px;font-size:.85rem;color:#374151;line-height:2.2;">
        <li>Acesse o <a href="https://ads.google.com" style="color:#92400e;font-weight:600;">Google Ads Manager</a></li>
        <li>Vá em <strong>Relatórios → Pré-definidos → Desempenho → Campanha</strong></li>
        <li>Selecione o período da semana (segunda a domingo)</li>
        <li>Clique em <strong>Download → CSV</strong></li>
        <li>Abra o <a href="https://seu-app.streamlit.app" style="color:#92400e;font-weight:600;">Dash Google Ads</a>
            e faça o upload</li>
      </ol>"""

    n = len(clients_needing_upload)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f3f8;font-family:'Segoe UI',system-ui,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#92400e,#f59e0b);border-radius:16px;
       padding:32px;color:#fff;margin-bottom:20px;text-align:center;">
    <div style="font-size:2.5rem;margin-bottom:8px;">🟡</div>
    <h1 style="margin:0 0 6px;font-size:1.4rem;font-weight:700;">
      &#x1F4CA; Hora de subir os dados do Google Ads!
    </h1>
    <div style="opacity:.85;font-size:.9rem;">Dash Digital · Semana de {week_label}</div>
  </div>

  <!-- Intro -->
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;
       padding:18px 22px;margin-bottom:16px;font-size:.88rem;color:#374151;">
    <p style="margin:0 0 8px;">
      &#128338; <strong>{n} cliente{'s precisam' if n != 1 else ' precisa'} de dados atualizados</strong>
      esta semana. Faça o upload do CSV do Google Ads para manter o histórico
      e receber a análise estratégica de IA.
    </p>
  </div>

  <!-- Tabela de clientes -->
  <div style="background:#fff;border-radius:12px;overflow:hidden;
       border:1px solid #e5e7eb;margin-bottom:20px;">
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#fffbeb;">
          <th style="padding:10px 16px;text-align:left;font-size:.75rem;
               color:#92400e;font-weight:700;letter-spacing:.04em;">CLIENTE</th>
          <th style="padding:10px 16px;text-align:left;font-size:.75rem;
               color:#92400e;font-weight:700;letter-spacing:.04em;">ÚLTIMO UPLOAD</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <!-- Passo a passo -->
  <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:12px;
       padding:16px 20px;margin-bottom:20px;">
    <div style="font-size:.8rem;font-weight:700;color:#92400e;
         text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">
      &#128221; Como fazer o upload:
    </div>
    {steps_html}
  </div>

  <!-- Footer -->
  <div style="text-align:center;font-size:.72rem;color:#9ca3af;margin-top:16px;">
    Lembrete automático semanal · Gerado em {generated_at} · Dash Digital · @dashdgt
  </div>

</div>
</body>
</html>"""


def send_reminder(clients_needing_upload: list[dict], today: date) -> bool:
    """Envia o e-mail de lembrete via Gmail SMTP."""
    gmail_user  = os.environ.get("GMAIL_USER", "")
    gmail_pass  = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipients  = [r.strip() for r in os.environ.get("EMAIL_TO", "").split(",") if r.strip()]

    if not (gmail_user and gmail_pass and recipients):
        log.warning("Configuração de e-mail incompleta — lembrete não enviado.")
        return False

    n       = len(clients_needing_upload)
    subject = f"🟡 [Google Ads] {n} cliente{'s' if n != 1 else ''} aguardando upload · {today.strftime('%d/%m/%Y')}"
    body    = _build_reminder_html(clients_needing_upload, today)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Dash Digital Reports <{gmail_user}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, recipients, msg.as_bytes())
        log.info("✉ Lembrete enviado para: %s", ", ".join(recipients))
        return True
    except Exception as exc:
        log.error("Falha ao enviar e-mail: %s", exc)
        return False


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    log.info("═══ Verificação semanal Google Ads ═══")

    if not _check_env():
        sys.exit(1)

    today = date.today()
    log.info("Data: %s", today.isoformat())

    # Carrega clientes ativos
    clients = supabase_db.get_clients()
    if not clients:
        log.info("Nenhum cliente ativo no Supabase — nada a fazer.")
        return

    log.info("Clientes ativos: %d", len(clients))

    # Verifica último upload de cada cliente
    client_keys  = [c["key"] for c in clients]
    last_uploads = supabase_db.get_all_clients_last_upload(client_keys)

    threshold = today - timedelta(days=6)  # considera "atualizado" se upload nos últimos 6 dias

    needs_upload = []
    for c in clients:
        key        = c["key"]
        last_str   = last_uploads.get(key)
        needs      = True
        if last_str:
            try:
                last_dt = date.fromisoformat(last_str)
                needs   = last_dt < threshold
            except Exception:
                needs = True

        log.info(
            "  %s — último upload: %s → %s",
            c["name"],
            last_str or "nunca",
            "PRECISA ATUALIZAR" if needs else "OK",
        )
        if needs:
            needs_upload.append({**c, "last_upload": last_str})

    if not needs_upload:
        log.info("Todos os clientes têm dados atualizados — nenhum lembrete enviado.")
        return

    log.info("%d cliente(s) precisam de atualização — enviando lembrete...", len(needs_upload))
    ok = send_reminder(needs_upload, today)

    if not ok:
        sys.exit(1)

    log.info("═══ Concluído ═══")


if __name__ == "__main__":
    main()
