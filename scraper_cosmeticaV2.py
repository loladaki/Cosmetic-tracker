import requests
from bs4 import BeautifulSoup
import re
import psycopg2
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, timedelta
import time


# PRODUTOS DE COSMETICA
# formato: "ID": ("Nome do produto", "URL")

produtos = {
    "P01": ("Serum de Rosto Fluido UV Diario FPS 50+ Nivea",                "https://www.continente.pt/produto/serum-de-rosto-fluido-uv-diario-fps-50-nivea-nivea-8215194.html"),
    "P02": ("Creme de Rosto Dia Q10 Energy Antirrugas FPS15 Nivea",         "https://www.continente.pt/produto/creme-de-rosto-dia-q10-energy-antirrugas-fps15-nivea-nivea-5028703.html"),
    "P03": ("Serum Facial Glow Beauty of Joseon",                           "https://www.continente.pt/produto/serum-facial-glow-beauty-of-joseon-beauty-of-joseon-7983861.html"),
    "P04": ("Creme de Rosto Dynasty Beauty of Joseon",                      "https://www.continente.pt/produto/creme-de-rosto-dynasty-beauty-of-joseon-beauty-of-joseon-7983865.html"),
    "P05": ("Serum Facial Preenchedor Aloe Hialuronico Garnier",            "https://www.continente.pt/produto/serum-facial-preenchedor-aloe-hialuronico-garnier-skin-active-garnier-skin-active-7713344.html"),
    "P06": ("Serum Facial Revitalift Filler Antirrugas Loreal",             "https://www.continente.pt/produto/serum-facial-revitalift-filler-antirrugas-loreal-paris-loreal-paris-7094090.html"),
    "P07": ("Serum Facial Revitalift Clinical Vitamina C Loreal",           "https://www.continente.pt/produto/serum-facial-revitalift-clinical-vitamina-c-loreal-paris-loreal-paris-7713327.html"),
    "P08": ("Creme Dia Cellular Luminous 630 Antimanchas FPS50 Nivea",      "https://www.continente.pt/produto/creme-de-rosto-dia-cellular-luminous-630-antimanchas-fps50-30-nivea-nivea-7341889.html"),
    "P09": ("Serum Facial Noite Revitalift Laser Loreal",                   "https://www.continente.pt/produto/serum-facial-noite-revitalift-laser-loreal-paris-loreal-paris-7346510.html"),
    "P10": ("Serum de Rosto Rejuvenescedor Cellular Epigenetics Nivea",     "https://www.continente.pt/produto/serum-de-rosto-rejuvenescedor-cellular-epigenetics-nivea-nivea-8457679.html"),
    "P11": ("Serum Facial Antimanchas Vitamina C Garnier",                  "https://www.continente.pt/produto/serum-facial-antimanchas-vitamina-c-garnier-skin-active-garnier-skin-active-7514731.html"),
    "P12": ("Serum de Rosto Q10 Dupla Acao Nivea",                         "https://www.continente.pt/produto/serum-de-rosto-q10-dupla-acao-nivea-nivea-7985612.html"),
    "P13": ("Serum de Rosto Cellular Luminous 630 Antimanchas Nivea",       "https://www.continente.pt/produto/serum-de-rosto-cellular-luminous-630-antimanchas-nivea-nivea-7341888.html"),
    "P14": ("Serum Facial Age Perfect LE Duo Rejuvenescedor Loreal",        "https://www.continente.pt/produto/serum-facial-age-perfect-le-duo-rejuvenescedor-loreal-paris-loreal-paris-8110588.html"),
    "P15": ("Creme de Rosto Dia Revitalift Filler FPS 50 Loreal",           "https://www.continente.pt/produto/creme-de-rosto-dia-revitalift-filler-fps-50-loreal-paris-loreal-paris-7382344.html"),
    "P16": ("Creme de Rosto Dia Revitalift Filler Micro Gel Loreal",        "https://www.continente.pt/produto/creme-de-rosto-dia-revitalift-filler-micro-gel-loreal-paris-loreal-paris-7713331.html"),
    "P17": ("Serum Facial Vitamina C FPS 25 Garnier",                       "https://www.continente.pt/produto/serum-facial-vitamina-c-fps-25-garnier-skin-active-garnier-skin-active-7514729.html"),
    "P18": ("BB Cream Bege Brilhante N.13 Missha",                          "https://www.continente.pt/produto/bb-cream-bege-brilhante-n.13-missha-missha-7983880.html"),
    "P19": ("Serum de Rosto Antirugas Q10 Collagen Expert Nivea",           "https://www.continente.pt/produto/serum-de-rosto-antirugas-q10-collagen-expert-nivea-nivea-8716894.html"),
    "P20": ("Serum Facial Revitalift Antirrugas e Reparacao Loreal",        "https://www.continente.pt/produto/serum-facial-revitalift-antirrugas-e-reparacao-loreal-paris-loreal-paris-7801609.html"),
}

MIN_SEMANAS = 2


# EXTRAÇÃO DE PREÇOS

def get_price_info(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
    except:
        return None, None, None, None

    preco = None
    pvpr  = None

    price_elem = soup.select_one(".pwc-tile--price-primary")
    if price_elem:
        match = re.search(r"(\d+,\d+)", price_elem.get_text(strip=True))
        if match:
            preco = float(match.group(1).replace(",", "."))

    old_elem = soup.select_one(".strike-through .pwc-tile--price-value")
    if old_elem:
        match = re.search(r"(\d+,\d+)", old_elem.get_text(strip=True))
        if match:
            pvpr = float(match.group(1).replace(",", "."))

    if pvpr is None:
        match = re.search(r"PVPR\s*(\d+,\d+)", soup.get_text())
        if match:
            pvpr = float(match.group(1).replace(",", "."))

    desconto_percent = None
    desconto_euros   = None

    if preco and pvpr and pvpr > preco:
        desconto_euros   = round(pvpr - preco, 2)
        desconto_percent = round((desconto_euros / pvpr) * 100, 2)

    return preco, pvpr, desconto_percent, desconto_euros


# FALLBACK: ultimo preco conhecido

def get_fallback(cursor, produto_id):
    cursor.execute("""
        SELECT preco, pvpr, desconto_percent, desconto_euros
        FROM cosmetica_precos
        WHERE produto_id = %s
        ORDER BY data DESC
        LIMIT 1
    """, (produto_id,))
    row = cursor.fetchone()
    return (row[0], row[1], row[2], row[3]) if row else (None, None, None, None)


# ANÁLISE DE ALERTAS

def analisar_alertas(cursor, hoje, dados):
    dias_desde_terca = (hoje.weekday() - 1) % 7
    inicio_semana_atual = hoje - timedelta(days=dias_desde_terca)

    alertas_media  = []
    alertas_minimo = []

    for item in dados:
        produto_id   = item["produto_id"]
        nome         = item["produto"]
        preco        = item["preco"]
        pvpr         = item["pvpr"]
        desc_hoje    = item["desconto_percent"]
        euros_hoje   = item["desconto_euros"]

        if desc_hoje is None:
            continue

        cursor.execute("""
            SELECT
                DATE_TRUNC('week', data + INTERVAL '6 days')::date AS semana,
                AVG(desconto_percent) AS desc_semana,
                MIN(preco)            AS preco_min_semana
            FROM cosmetica_precos
            WHERE produto_id = %s
              AND data < %s
              AND desconto_percent IS NOT NULL
            GROUP BY DATE_TRUNC('week', data + INTERVAL '6 days')
            ORDER BY semana DESC
        """, (produto_id, inicio_semana_atual))
        semanas_hist = cursor.fetchall()

        n_semanas = len(semanas_hist)
        if n_semanas < MIN_SEMANAS:
            print(f"  [{produto_id}] {n_semanas}/{MIN_SEMANAS} semanas -- a acumular historico")
            continue

        descontos_hist    = [r[1] for r in semanas_hist if r[1] is not None]
        precos_min_hist   = [r[2] for r in semanas_hist if r[2] is not None]
        media_desc_hist   = sum(descontos_hist) / len(descontos_hist) if descontos_hist else None
        preco_minimo_hist = min(precos_min_hist) if precos_min_hist else None

        if media_desc_hist and desc_hoje > media_desc_hist:
            alertas_media.append({
                "produto_id": produto_id,
                "produto":    nome,
                "preco":      preco,
                "pvpr":       pvpr,
                "desc_hoje":  round(desc_hoje, 1),
                "media_desc": round(media_desc_hist, 1),
                "diferenca":  round(desc_hoje - media_desc_hist, 1),
                "euros_hoje": euros_hoje,
                "n_semanas":  n_semanas,
            })

        if preco_minimo_hist and preco <= preco_minimo_hist:
            alertas_minimo.append({
                "produto_id":   produto_id,
                "produto":      nome,
                "preco":        preco,
                "pvpr":         pvpr,
                "desc_hoje":    desc_hoje,
                "euros_hoje":   euros_hoje,
                "preco_minimo": preco_minimo_hist,
                "n_semanas":    n_semanas,
            })

    return alertas_media, alertas_minimo


# ENVIAR EMAIL

def enviar_email(hoje, alertas_media, alertas_minimo):
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_PASS = os.getenv("GMAIL_PASS")
    EMAIL_DEST = os.getenv("EMAIL_DEST")

    if not GMAIL_USER or not GMAIL_PASS or not EMAIL_DEST:
        print("Credenciais Gmail nao configuradas -- email nao enviado.")
        return

    def fmt(val, suffix=""):
        return f"{val:.2f}{suffix}" if val is not None else "-"

    linhas_media = ""
    for a in sorted(alertas_media, key=lambda x: x["diferenca"], reverse=True):
        linhas_media += f"""
        <tr>
            <td style="color:#888">{a['produto_id']}</td>
            <td><b>{a['produto']}</b></td>
            <td>{fmt(a['preco'])} €</td>
            <td>{fmt(a['pvpr'])} €</td>
            <td style="color:#e65c00"><b>{a['desc_hoje']}%</b></td>
            <td>{a['media_desc']}%</td>
            <td style="color:green"><b>+{a['diferenca']}%</b></td>
            <td>{fmt(a['euros_hoje'])} €</td>
            <td style="color:#888">{a['n_semanas']} sem.</td>
        </tr>"""

    linhas_minimo = ""
    for a in sorted(alertas_minimo, key=lambda x: x["preco"]):
        linhas_minimo += f"""
        <tr>
            <td style="color:#888">{a['produto_id']}</td>
            <td><b>{a['produto']}</b></td>
            <td style="color:green"><b>{fmt(a['preco'])} €</b></td>
            <td>{fmt(a['pvpr'])} €</td>
            <td>{fmt(a['desc_hoje'], '%') if a['desc_hoje'] else '-'}</td>
            <td>{fmt(a['euros_hoje'])} €</td>
            <td style="color:#888">{a['n_semanas']} sem.</td>
        </tr>"""

    tabela_media = ""
    if alertas_media:
        tabela_media = f"""
        <h2 style="color:#e65c00">Desconto acima da media semanal</h2>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px">
            <tr style="background:#f2f2f2">
                <th>ID</th><th>Produto</th><th>Preco hoje</th><th>PVPR</th>
                <th>Desconto hoje</th><th>Media semanal</th>
                <th>Diferenca</th><th>Poupanca</th><th>Historico</th>
            </tr>
            {linhas_media}
        </table><br>"""

    tabela_minimo = ""
    if alertas_minimo:
        tabela_minimo = f"""
        <h2 style="color:#1a7f37">Preco minimo historico!</h2>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px">
            <tr style="background:#f2f2f2">
                <th>ID</th><th>Produto</th><th>Preco hoje</th><th>PVPR</th>
                <th>Desconto</th><th>Poupanca</th><th>Historico</th>
            </tr>
            {linhas_minimo}
        </table><br>"""

    dias_desde_terca = (hoje.weekday() - 1) % 7
    semana_str = (hoje - timedelta(days=dias_desde_terca)).strftime("%d/%m/%Y")

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;padding:20px;max-width:950px">
        <h1>Alertas de Cosmetica -- semana de {semana_str}</h1>
        <p>
            <b>{len(alertas_media)}</b> produto(s) com desconto acima da media e
            <b>{len(alertas_minimo)}</b> produto(s) no preco minimo historico.
        </p>
        {tabela_media}
        {tabela_minimo}
        <hr>
        <p style="font-size:11px;color:#aaa">
            Alerta automatico · Cosmetica Continente · comparacao semanal (terca a segunda) ·
            minimo {MIN_SEMANAS} semanas de historico
        </p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"Alertas Cosmetica semana {semana_str} -- "
        f"{len(alertas_media) + len(alertas_minimo)} produto(s) em destaque"
    )
    msg["From"] = GMAIL_USER
    msg["To"]   = EMAIL_DEST
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.sendmail(GMAIL_USER, EMAIL_DEST, msg.as_string())
        print(f"Email enviado: {len(alertas_media)} alertas media + {len(alertas_minimo)} minimos.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        raise


# ── MAIN ─────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")
conn   = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()
hoje   = date.today()

dados = []

for produto_id, (nome, url) in produtos.items():

    preco, pvpr, desconto_percent, desconto_euros = get_price_info(url)

    if preco is None:
        preco, pvpr, desconto_percent, desconto_euros = get_fallback(cursor, produto_id)
        if preco is not None:
            print(f"Fallback [{produto_id}] {nome[:40]} -- {preco:.2f} EUR")
        else:
            print(f"Sem preco e sem fallback para [{produto_id}] {nome[:40]} -- ignorado")
            continue

    dados.append({
        "produto_id":       produto_id,
        "produto":          nome,
        "preco":            preco,
        "pvpr":             pvpr,
        "desconto_percent": desconto_percent,
        "desconto_euros":   desconto_euros,
    })

    time.sleep(1)

# GUARDAR NA BASE DE DADOS

cursor.execute("DELETE FROM cosmetica_precos WHERE data = %s", (hoje,))

for item in dados:
    cursor.execute("""
        INSERT INTO cosmetica_precos
            (data, produto_id, produto, preco, pvpr, desconto_percent, desconto_euros)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (data, produto) DO NOTHING
    """, (
        hoje,
        item["produto_id"],
        item["produto"],
        item["preco"],
        item["pvpr"],
        item["desconto_percent"],
        item["desconto_euros"],
    ))

conn.commit()
print(f"Cosmetica: {len(dados)}/{len(produtos)} produtos guardados ({hoje})")

# ANALISAR E ENVIAR ALERTAS

alertas_media, alertas_minimo = analisar_alertas(cursor, hoje, dados)

if alertas_media or alertas_minimo:
    enviar_email(hoje, alertas_media, alertas_minimo)
else:
    print(f"Sem alertas para hoje ({hoje}).")

conn.close()
