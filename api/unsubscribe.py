"""Vercel Serverless: Abonelikten cikma endpoint'i (Supabase)."""
import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def _supabase_insert(email: str):
    url = f"{SUPABASE_URL}/rest/v1/unsubscribed"
    data = json.dumps({"email": email.lower().strip()}).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return True
    except urllib.error.HTTPError as e:
        # Duplicate email - sorun degil
        if e.code == 409:
            return True
        return False
    except Exception:
        return False


HTML_OK = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Abonelikten \u00c7\u0131k\u0131ld\u0131</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f4f4f7;font-family:'Helvetica Neue',Arial,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh}}
.card{{background:#fff;border-radius:16px;padding:48px 40px;max-width:480px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,0.08)}}
.icon{{font-size:48px;margin-bottom:16px}}
h1{{color:#1e293b;font-size:22px;margin-bottom:12px}}
p{{color:#64748b;font-size:15px;line-height:1.7;margin-bottom:8px}}
.email{{color:#1e293b;font-weight:700}}
.note{{color:#94a3b8;font-size:13px;margin-top:20px}}
</style>
</head>
<body>
<div class="card">
<div class="icon">&#9989;</div>
<h1>Abonelikten \u00c7\u0131k\u0131ld\u0131</h1>
<p><span class="email">{email}</span> adresi e-posta listemizden \u00e7\u0131kar\u0131ld\u0131.</p>
<p>Art\u0131k size pazarlama e-postas\u0131 g\u00f6ndermeyece\u011fiz.</p>
<p class="note">Bu i\u015flem yanl\u0131\u015fl\u0131kla yap\u0131ld\u0131ysa info@yodijital.com adresine yaz\u0131n.</p>
</div>
</body>
</html>"""

HTML_ERR = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hata</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f4f4f7;font-family:'Helvetica Neue',Arial,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh}}
.card{{background:#fff;border-radius:16px;padding:48px 40px;max-width:480px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,0.08)}}
.icon{{font-size:48px;margin-bottom:16px}}
h1{{color:#1e293b;font-size:22px;margin-bottom:12px}}
p{{color:#64748b;font-size:15px;line-height:1.7}}
</style>
</head>
<body>
<div class="card">
<div class="icon">&#10060;</div>
<h1>Ge\u00e7ersiz \u0130stek</h1>
<p>E-posta adresi belirtilmedi.</p>
</div>
</body>
</html>"""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        email = params.get("email", [""])[0].strip()

        if not email:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_ERR.encode())
            return

        _supabase_insert(email)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_OK.format(email=email).encode())
