"""Vercel Serverless: Kara liste API (Supabase)."""
import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = f"{SUPABASE_URL}/rest/v1/unsubscribed?select=email"
        req = urllib.request.Request(
            url, method="GET",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                emails = [r["email"] for r in data]
        except Exception:
            emails = []

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"emails": sorted(emails)}).encode())
