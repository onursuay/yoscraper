"""
Google Ads Click Bot Engine
===========================
Playwright tabanli, anti-ban onlemli reklam tiklama botu.
"""

import os
import json
import time
import random
import logging
import threading
from typing import Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth

load_dotenv()

# Stealth instance - tüm evasion'lar açık, Türkçe ayarlar
_stealth = Stealth(
    navigator_languages_override=("tr-TR", "tr"),
    navigator_platform_override="MacIntel",
)

log = logging.getLogger("bot")


# --- Email Report Helper ---
class EmailReporter:
    """Tarama sonrasi ozet rapor e-postasi gonderir."""

    def __init__(self):
        self.smtp_server = ""
        self.smtp_port = 587
        self.email = ""
        self.password = ""
        self.recipient = ""
        self._enabled = False

    def configure(self, smtp_server, smtp_port, email, password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port) if smtp_port else 587
        self.email = email
        self.password = password
        self.recipient = recipient or email
        self._enabled = bool(email and password and smtp_server)

    def send_report(self, stats, click_history):
        if not self._enabled:
            return False
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            now = datetime.now().strftime("%d.%m.%Y %H:%M")

            total_clicks = stats.get("total_clicks", 0)
            total_ads = stats.get("total_ads_found", 0)
            total_searches = stats.get("total_searches", 0)

            # Son taramanin sonuclari
            recent = click_history[-50:] if click_history else []

            rows = ""
            for r in recent:
                status = r.get('status', '')
                status_color = '#22c55e' if status == 'success' else '#ef4444'
                rows += f"""<tr>
                    <td style="padding:8px 10px;border-bottom:1px solid #eee;color:#333;">{r.get('il','')}</td>
                    <td style="padding:8px 10px;border-bottom:1px solid #eee;color:#333;">{r.get('ilce','')}</td>
                    <td style="padding:8px 10px;border-bottom:1px solid #eee;color:#333;">{r.get('keyword','')}</td>
                    <td style="padding:8px 10px;border-bottom:1px solid #eee;color:#333;">{r.get('domain','')}</td>
                    <td style="padding:8px 10px;border-bottom:1px solid #eee;color:#555;font-size:11px;">{r.get('zone','')}</td>
                    <td style="padding:8px 10px;border-bottom:1px solid #eee;color:{status_color};font-weight:bold;">{status}</td>
                </tr>"""

            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#ffffff;color:#333333;padding:20px;border-radius:12px;border:1px solid #e0e0e0;">
                <h2 style="color:#1a1a2e;text-align:center;margin-bottom:5px;">Google Ads Click Bot</h2>
                <p style="color:#888;text-align:center;font-size:13px;margin-top:0;">Tarama Raporu — {now}</p>
                <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
                    <tr>
                        <td width="33%" style="text-align:center;background:#f0f0ff;padding:15px 10px;border-radius:10px;">
                            <div style="font-size:28px;font-weight:bold;color:#6366f1;">{total_searches}</div>
                            <div style="font-size:12px;color:#666;">Arama</div>
                        </td>
                        <td width="5%"></td>
                        <td width="33%" style="text-align:center;background:#f0fff0;padding:15px 10px;border-radius:10px;">
                            <div style="font-size:28px;font-weight:bold;color:#22c55e;">{total_ads}</div>
                            <div style="font-size:12px;color:#666;">Reklam</div>
                        </td>
                        <td width="5%"></td>
                        <td width="33%" style="text-align:center;background:#fffbf0;padding:15px 10px;border-radius:10px;">
                            <div style="font-size:28px;font-weight:bold;color:#f59e0b;">{total_clicks}</div>
                            <div style="font-size:12px;color:#666;">Tıklama</div>
                        </td>
                    </tr>
                </table>
                {"<table style='width:100%;border-collapse:collapse;margin-top:15px;font-size:12px;'><tr style=" + '"background:#f5f5f5;"' + "><th style='padding:8px 10px;text-align:left;color:#333;border-bottom:2px solid #ddd;'>İl</th><th style='padding:8px 10px;text-align:left;color:#333;border-bottom:2px solid #ddd;'>İlçe</th><th style='padding:8px 10px;text-align:left;color:#333;border-bottom:2px solid #ddd;'>Anahtar Kelime</th><th style='padding:8px 10px;text-align:left;color:#333;border-bottom:2px solid #ddd;'>Firma/Domain</th><th style='padding:8px 10px;text-align:left;color:#333;border-bottom:2px solid #ddd;'>Zone</th><th style='padding:8px 10px;text-align:left;color:#333;border-bottom:2px solid #ddd;'>Durum</th></tr>" + rows + "</table>" if rows else "<p style='text-align:center;color:#999;'>Tıklama kaydedilmedi.</p>"}
                <p style="text-align:center;color:#bbb;font-size:10px;margin-top:20px;">Google Ads Click Bot</p>
            </div>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Tarama Raporu - {now} | {total_clicks} Tiklama"
            msg["From"] = self.email
            msg["To"] = self.recipient
            msg.attach(MIMEText(html, "html"))

            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.email, self.password)
                    server.sendmail(self.email, self.recipient, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.email, self.password)
                    server.sendmail(self.email, self.recipient, msg.as_string())

            log.info(f"Rapor e-postasi gonderildi: {self.recipient}")
            return True
        except Exception as e:
            log.warning(f"E-posta gonderilemedi: {e}")
            return False

    def test_connection(self):
        if not self._enabled:
            return False, "E-posta ayarlari eksik."
        try:
            import smtplib
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.email, self.password)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.email, self.password)
            return True, "Baglanti basarili!"
        except Exception as e:
            return False, str(e)


# --- Google Sheets Helper ---
class SheetsLogger:
    """Google Sheets'e tiklama sonuclarini kaydeder."""

    def __init__(self, sheet_id=None, credentials_path=None):
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self._client = None
        self._sheet = None
        self._enabled = False

    def configure(self, sheet_id, credentials_path="credentials/service_account.json", worksheet_name=None):
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.worksheet_name = worksheet_name
        self._client = None
        self._sheet = None
        self._enabled = bool(sheet_id)

    def _connect(self):
        if self._sheet:
            return True
        if not self._enabled or not self.sheet_id:
            return False
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            self._client = gspread.authorize(creds)
            spreadsheet = self._client.open_by_key(self.sheet_id)
            if self.worksheet_name:
                self._sheet = spreadsheet.worksheet(self.worksheet_name)
            else:
                self._sheet = spreadsheet.sheet1

            # Baslik satiri yoksa ekle
            existing = self._sheet.row_values(1)
            if not existing or existing[0] != "Tarih":
                self._sheet.update("A1:I1", [["Tarih", "Saat", "İl", "İlçe", "Anahtar Kelime", "Baslik", "URL", "Zone", "Durum"]])

            return True
        except Exception as e:
            log.warning(f"Sheets baglanti hatasi: {e}")
            self._sheet = None
            return False

    def get_worksheets(self, sheet_id, credentials_path="credentials/service_account.json"):
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(sheet_id)
            return [ws.title for ws in spreadsheet.worksheets()]
        except Exception as e:
            log.warning(f"Worksheet listesi alinamadi: {e}")
            return []

    def log_click(self, result_dict):
        if not self._enabled:
            return
        try:
            if not self._connect():
                return
            ts = result_dict.get("timestamp", "")
            date_part = ts.split("T")[0] if "T" in ts else ts[:10]
            time_part = ts.split("T")[1][:8] if "T" in ts else ""

            row = [
                date_part,
                time_part,
                result_dict.get("il", ""),
                result_dict.get("ilce", ""),
                result_dict.get("keyword", ""),
                result_dict.get("ad_title", "")[:100],
                result_dict.get("ad_url", "")[:200],
                result_dict.get("zone", ""),
                result_dict.get("status", ""),
            ]
            self._sheet.append_row(row, value_input_option="USER_ENTERED")
        except Exception as e:
            log.warning(f"Sheets yazma hatasi: {e}")
            self._sheet = None  # Baglanti resetle, sonraki denemede yeniden baglanir

# --- Anti-ban: User Agent havuzu ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

VIEWPORT_SIZES = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

# --- Ad zone definitions: each zone is scanned independently ---
AD_ZONES = [
    {
        "name": "Top Ads",
        "container_selectors": [
            "#tads div[data-text-ad]",
            "#tads .uEierd",
            "#tads .v5yQqb",
            "#tads li.ads-ad",
        ],
    },
    {
        "name": "Bottom Ads",
        "container_selectors": [
            "#tadsb div[data-text-ad]",
            "#tadsb .uEierd",
            "#tadsb .v5yQqb",
            "#tadsb li.ads-ad",
        ],
    },
    {
        "name": "Shopping",
        "container_selectors": [
            "div.pla-unit",
            "div.mnr-c .pla-unit",
            "div.cu-container .pla-unit",
            "div[data-enable-product-traversal] .pla-unit",
        ],
    },
    {
        "name": "Local/Map",
        "container_selectors": [
            "div.VkpGBb",
            "div[data-local-promotions]",
        ],
    },
    {
        "name": "Sponsorlu",
        "container_selectors": [
            "div[data-text-ad]",
            "div.uEierd",
            "div.commercial-unit-desktop-top",
            "div[aria-label='Ads'] div.uEierd",
            "div[aria-label='Reklamlar'] div.uEierd",
        ],
    },
]

AD_LINK_SELECTORS = [
    "a[data-rw]",
    "a.sVXRqc",
    "a[data-pcu]",
    "a[ping]",
    "a[href^='http']",
]

AD_TITLE_SELECTORS = [
    "div[role='heading']",
    "span[role='heading']",
    "h3",
    "span.CCgQ5",
    "div.v0nnCb",
    "span.pymv4e",
]


def domain_to_firm_name(url):
    """URL'den domain parse edip firma adını çıkar.
    cankayaanahtarci.com → Çankaya Anahtarcı
    favorihaliyikama.com → Favori Halı Yıkama
    cilingirservisi.com.tr → Çilingir Servisi
    umutelektronikanahtar.net → Umut Elektronik Anahtar
    """
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        if not domain:
            return url

        # TLD kaldır (.com, .net, .org, .com.tr, .net.tr vb.)
        name = domain
        for tld in [".com.tr", ".net.tr", ".org.tr", ".gen.tr", ".bel.tr",
                     ".com", ".net", ".org", ".info", ".biz", ".co", ".io", ".tr"]:
            if name.endswith(tld):
                name = name[:-len(tld)]
                break

        if not name:
            return domain

        # Türkçe kelime sözlüğü - yaygın iş/sektör/marka kelimeleri
        tr_words = {
            # Çilingir / Anahtar
            "cilingir": "Çilingir", "cilingirci": "Çilingirci", "cilingirim": "Çilingirim",
            "anahtarci": "Anahtarcı", "anahtar": "Anahtar", "kilit": "Kilit", "kilitci": "Kilitçi",
            # Temizlik / Yıkama
            "haliyikama": "Halı Yıkama", "koltukyikama": "Koltuk Yıkama",
            "hali": "Halı", "yikama": "Yıkama", "koltuk": "Koltuk",
            "temizlik": "Temizlik", "temiz": "Temiz", "temizle": "Temizle",
            "hijyen": "Hijyen", "dezenfeksiyon": "Dezenfeksiyon",
            "kuru": "Kuru", "islak": "Islak", "buhar": "Buhar", "vakum": "Vakum",
            # Nakliyat
            "nakliyat": "Nakliyat", "nakliye": "Nakliye", "tasima": "Taşıma",
            "tasimacilik": "Taşımacılık", "evden": "Evden", "eve": "Eve",
            # İnşaat / Tadilat
            "insaat": "İnşaat", "dekorasyon": "Dekorasyon", "tadilat": "Tadilat",
            "yapi": "Yapı", "restorasyon": "Restorasyon", "mantolama": "Mantolama",
            # Teknik
            "elektrik": "Elektrik", "elektronik": "Elektronik", "tesisat": "Tesisat",
            "tesisatci": "Tesisatçı", "klima": "Klima", "kombi": "Kombi",
            "servis": "Servis", "servisi": "Servisi", "tamir": "Tamir",
            "bakim": "Bakım", "montaj": "Montaj", "onarim": "Onarım",
            # Araç
            "oto": "Oto", "araba": "Araba", "arac": "Araç", "rent": "Rent",
            "car": "Car", "garage": "Garage", "garaj": "Garaj",
            # Şehirler
            "ankara": "Ankara", "istanbul": "İstanbul", "izmir": "İzmir",
            "antalya": "Antalya", "bursa": "Bursa", "adana": "Adana",
            "gaziantep": "Gaziantep", "konya": "Konya", "kayseri": "Kayseri",
            # İlçeler
            "cankaya": "Çankaya", "etimesgut": "Etimesgut", "kecioren": "Keçiören",
            "yenimahalle": "Yenimahalle", "mamak": "Mamak", "sincan": "Sincan",
            "eryaman": "Eryaman", "batikent": "Batıkent", "dikmen": "Dikmen",
            "bahcelievler": "Bahçelievler", "besevler": "Beşevler",
            "kadikoy": "Kadıköy", "besiktas": "Beşiktaş", "uskudar": "Üsküdar",
            "bakirkoy": "Bakırköy", "sisli": "Şişli", "beyoglu": "Beyoğlu",
            "atasehir": "Ataşehir", "umraniye": "Ümraniye", "pendik": "Pendik",
            "kartal": "Kartal", "maltepe": "Maltepe", "bostanci": "Bostancı",
            "bornova": "Bornova", "karsiyaka": "Karşıyaka", "konak": "Konak",
            # Sağlık
            "pet": "Pet", "veteriner": "Veteriner", "eczane": "Eczane",
            "avukat": "Avukat", "hukuk": "Hukuk", "noter": "Noter",
            "dis": "Diş", "klinik": "Klinik", "hastane": "Hastane",
            "saglik": "Sağlık", "doktor": "Doktor", "eczaci": "Eczacı",
            # Konaklama / Yeme
            "otel": "Otel", "hotel": "Hotel", "pansiyon": "Pansiyon",
            "restoran": "Restoran", "cafe": "Cafe", "kafe": "Kafe",
            "pizza": "Pizza", "burger": "Burger", "kebap": "Kebap",
            # Ticaret
            "market": "Market", "magaza": "Mağaza", "shop": "Shop",
            "satis": "Satış", "alis": "Alış", "ticaret": "Ticaret",
            "toptan": "Toptan", "perakende": "Perakende",
            # Marka/isim kelimeleri
            "favori": "Favori", "umut": "Umut", "guven": "Güven", "nazar": "Nazar",
            "kale": "Kale", "guvenlik": "Güvenlik", "ari": "Arı",
            "star": "Star", "gold": "Gold", "golden": "Golden", "royal": "Royal",
            "oz": "Öz", "ozel": "Özel", "vip": "VIP", "mega": "Mega",
            "super": "Süper", "ideal": "İdeal", "mavi": "Mavi", "yesil": "Yeşil",
            "beyaz": "Beyaz", "altin": "Altın", "gumus": "Gümüş",
            "kartal": "Kartal", "aslan": "Aslan", "kardes": "Kardeş",
            "birlik": "Birlik", "dost": "Dost", "can": "Can", "nur": "Nur",
            "ay": "Ay", "gunes": "Güneş", "yildiz": "Yıldız",
            "usta": "Usta", "ustasi": "Ustası", "master": "Master",
            "reis": "Reis", "bey": "Bey", "han": "Han", "saray": "Saray",
            "hereke": "Hereke", "soft": "Soft", "yaprak": "Yaprak",
            "ipek": "İpek", "sedir": "Sedir", "zambak": "Zambak",
            "lotus": "Lotus", "lale": "Lale", "gonca": "Gonca",
            # Bağlaçlar / Ekler
            "ve": "ve", "ile": "ile", "den": "den", "da": "da", "de": "de",
            "bu": "Bu", "bir": "Bir", "en": "En", "my": "My", "the": "The",
            # Boya / Dekor
            "boyaci": "Boyacı", "boya": "Boya", "badana": "Badana",
            "mobilya": "Mobilya", "mutfak": "Mutfak", "banyo": "Banyo",
            "cam": "Cam", "pvc": "PVC", "aluminyum": "Alüminyum", "perde": "Perde",
            # Dijital / Medya
            "dijital": "Dijital", "medya": "Medya", "ajans": "Ajans",
            "yazilim": "Yazılım", "bilisim": "Bilişim", "teknoloji": "Teknoloji",
            "web": "Web", "net": "Net", "bilgi": "Bilgi", "data": "Data",
            # Danışmanlık / Eğitim
            "danismanlik": "Danışmanlık", "musavirlik": "Müşavirlik",
            "egitim": "Eğitim", "kurs": "Kurs", "okul": "Okul", "akademi": "Akademi",
            # Finans
            "sigorta": "Sigorta", "finans": "Finans", "kredi": "Kredi", "banka": "Banka",
            # Lojistik
            "kargo": "Kargo", "kurye": "Kurye", "lojistik": "Lojistik",
            # Matbaa / Reklam
            "matbaa": "Matbaa", "baski": "Baskı", "reklam": "Reklam", "tabela": "Tabela",
            # Foto / Video
            "foto": "Foto", "fotograf": "Fotoğraf", "video": "Video", "studio": "Stüdyo",
            # Organizasyon
            "dugun": "Düğün", "organizasyon": "Organizasyon", "davet": "Davet",
            # Bahçe
            "cicek": "Çiçek", "peyzaj": "Peyzaj", "bahce": "Bahçe", "fidancilik": "Fidancılık",
            # Su / Enerji
            "su": "Su", "aritma": "Arıtma", "enerji": "Enerji", "solar": "Solar", "gunes": "Güneş",
            # Genel sıfatlar/ekler
            "hizmet": "Hizmet", "hizmetler": "Hizmetler", "hizmetleri": "Hizmetleri",
            "profesyonel": "Profesyonel", "kaliteli": "Kaliteli",
            "acil": "Acil", "online": "Online", "express": "Express", "hizli": "Hızlı",
            "plus": "Plus", "pro": "Pro", "group": "Group", "grup": "Grup",
            "fiyat": "Fiyat", "fiyatlari": "Fiyatları", "ucuz": "Ucuz",
            "evi": "Evi", "dunyasi": "Dünyası", "merkezi": "Merkezi", "merkez": "Merkez",
        }

        # Domain adını kelimelere ayır
        name = name.replace("-", " ").replace("_", " ")
        parts = name.split()

        result_words = []
        for part in parts:
            remaining = part.lower()
            found_words = []

            while remaining:
                matched = False
                # Uzun eşleşmeden kısa kelimeye (min 2 harf)
                for length in range(len(remaining), 1, -1):
                    candidate = remaining[:length]
                    if candidate in tr_words:
                        found_words.append(tr_words[candidate])
                        remaining = remaining[length:]
                        matched = True
                        break
                if not matched:
                    # Eşleşme yok - kalan kısmın içinde sonraki bilinen kelimeyi ara
                    next_match_pos = len(remaining)
                    for pos in range(1, len(remaining)):
                        found_at = False
                        for length in range(len(remaining) - pos, 1, -1):
                            if remaining[pos:pos+length] in tr_words:
                                next_match_pos = pos
                                found_at = True
                                break
                        if found_at:
                            break
                    # Bilinmeyen kısmı capitalize et
                    unknown = remaining[:next_match_pos]
                    found_words.append(unknown.capitalize())
                    remaining = remaining[next_match_pos:]

            result_words.extend(found_words)

        return " ".join(result_words) if result_words else domain
    except Exception:
        return url


# --- Türkiye İl/İlçe GPS Koordinatları ---
CITY_COORDINATES = {
    "Adana": (37.0000, 35.3213), "Adıyaman": (37.7648, 38.2786), "Afyonkarahisar": (38.7507, 30.5567),
    "Ağrı": (39.7191, 43.0503), "Aksaray": (38.3687, 34.0370), "Amasya": (40.6499, 35.8353),
    "Ankara": (39.9334, 32.8597), "Antalya": (36.8969, 30.7133), "Ardahan": (41.1105, 42.7022),
    "Artvin": (41.1828, 41.8183), "Aydın": (37.8560, 27.8416), "Balıkesir": (39.6484, 27.8826),
    "Bartın": (41.6344, 32.3375), "Batman": (37.8812, 41.1351), "Bayburt": (40.2552, 40.2249),
    "Bilecik": (40.0567, 30.0665), "Bingöl": (38.8854, 40.4966), "Bitlis": (38.3938, 42.1232),
    "Bolu": (40.7350, 31.6061), "Burdur": (37.7203, 30.2908), "Bursa": (40.1826, 29.0665),
    "Çanakkale": (40.1553, 26.4142), "Çankırı": (40.6013, 33.6134), "Çorum": (40.5506, 34.9556),
    "Denizli": (37.7765, 29.0864), "Diyarbakır": (37.9144, 40.2306), "Düzce": (40.8438, 31.1565),
    "Edirne": (41.6818, 26.5623), "Elazığ": (38.6810, 39.2264), "Erzincan": (39.7500, 39.5000),
    "Erzurum": (39.9055, 41.2658), "Eskişehir": (39.7767, 30.5206), "Gaziantep": (37.0662, 37.3833),
    "Giresun": (40.9128, 38.3895), "Gümüşhane": (40.4386, 39.5086), "Hakkâri": (37.5833, 43.7333),
    "Hatay": (36.4018, 36.3498), "Iğdır": (39.9167, 44.0500), "Isparta": (37.7648, 30.5566),
    "İstanbul": (41.0082, 28.9784), "İzmir": (38.4192, 27.1287), "Kahramanmaraş": (37.5858, 36.9371),
    "Karabük": (41.2061, 32.6204), "Karaman": (37.1759, 33.2287), "Kars": (40.6013, 43.0975),
    "Kastamonu": (41.3887, 33.7827), "Kayseri": (38.7312, 35.4787), "Kırıkkale": (39.8468, 33.5153),
    "Kırklareli": (41.7333, 27.2167), "Kırşehir": (39.1425, 34.1709), "Kilis": (36.7184, 37.1212),
    "Kocaeli": (40.8533, 29.8815), "Konya": (37.8667, 32.4833), "Kütahya": (39.4167, 29.9833),
    "Malatya": (38.3552, 38.3095), "Manisa": (38.6191, 27.4289), "Mardin": (37.3212, 40.7245),
    "Mersin": (36.8121, 34.6415), "Muğla": (37.2153, 28.3636), "Muş": (38.9462, 41.7539),
    "Nevşehir": (38.6939, 34.6857), "Niğde": (37.9667, 34.6833), "Ordu": (40.9839, 37.8764),
    "Osmaniye": (37.0742, 36.2464), "Rize": (41.0201, 40.5234), "Sakarya": (40.6940, 30.4358),
    "Samsun": (41.2928, 36.3313), "Şanlıurfa": (37.1591, 38.7969), "Siirt": (37.9333, 41.9500),
    "Sinop": (42.0231, 35.1531), "Sivas": (39.7477, 37.0179), "Şırnak": (37.4187, 42.4918),
    "Tekirdağ": (40.9833, 27.5167), "Tokat": (40.3167, 36.5500), "Trabzon": (41.0015, 39.7178),
    "Tunceli": (39.1079, 39.5401), "Uşak": (38.6823, 29.4082), "Van": (38.4891, 43.4089),
    "Yalova": (40.6500, 29.2667), "Yozgat": (39.8181, 34.8147), "Zonguldak": (41.4564, 31.7987),
}

# Popüler ilçe koordinatları (büyükşehirler ve yoğun ilçeler)
DISTRICT_COORDINATES = {
    # Ankara - Tüm ilçeler
    "Ankara Altındağ": (39.9550, 32.8690), "Ankara Çankaya": (39.9179, 32.8627),
    "Ankara Etimesgut": (39.9500, 32.6667), "Ankara Keçiören": (39.9833, 32.8500),
    "Ankara Mamak": (39.9333, 32.9167), "Ankara Pursaklar": (40.0333, 32.8833),
    "Ankara Sincan": (39.9667, 32.5833), "Ankara Yenimahalle": (39.9667, 32.8000),
    "Ankara Gölbaşı": (39.7833, 32.8000),
    # İstanbul
    "İstanbul Kadıköy": (40.9927, 29.0290), "İstanbul Beşiktaş": (41.0422, 29.0083),
    "İstanbul Bakırköy": (40.9819, 28.8772), "İstanbul Fatih": (41.0186, 28.9395),
    "İstanbul Beyoğlu": (41.0370, 28.9770), "İstanbul Şişli": (41.0602, 28.9877),
    "İstanbul Üsküdar": (41.0235, 29.0153), "İstanbul Ataşehir": (40.9923, 29.1244),
    "İstanbul Maltepe": (40.9358, 29.1266), "İstanbul Kartal": (40.8903, 29.1858),
    "İstanbul Pendik": (40.8755, 29.2333), "İstanbul Bağcılar": (41.0367, 28.8567),
    "İstanbul Bahçelievler": (41.0000, 28.8619), "İstanbul Başakşehir": (41.0940, 28.7930),
    "İstanbul Esenyurt": (41.0338, 28.6729), "İstanbul Küçükçekmece": (41.0028, 28.7810),
    "İstanbul Büyükçekmece": (41.0205, 28.5855), "İstanbul Sarıyer": (41.1667, 29.0500),
    "İstanbul Eyüpsultan": (41.0481, 28.9340), "İstanbul Sultangazi": (41.1078, 28.8667),
    "İstanbul Bayrampaşa": (41.0500, 28.9167), "İstanbul Zeytinburnu": (41.0042, 28.9020),
    "İstanbul Avcılar": (40.9833, 28.7167), "İstanbul Beykoz": (41.1333, 29.1000),
    "İstanbul Çatalca": (41.1439, 28.4597), "İstanbul Silivri": (41.0739, 28.2469),
    "İstanbul Arnavutköy": (41.1833, 28.7333), "İstanbul Güngören": (41.0167, 28.8833),
    "İstanbul Esenler": (41.0500, 28.8833), "İstanbul Gaziosmanpaşa": (41.0667, 28.9167),
    "İstanbul Sancaktepe": (41.0028, 29.2319), "İstanbul Sultanbeyli": (40.9667, 29.2667),
    "İstanbul Tuzla": (40.8167, 29.3000), "İstanbul Ümraniye": (41.0167, 29.1167),
    "İstanbul Beylikdüzü": (41.0000, 28.6333), "İstanbul Çekmeköy": (41.0333, 29.1833),
    "İstanbul Kağıthane": (41.0833, 28.9667), "İstanbul Şile": (41.1761, 29.6128),
    # İzmir - Tüm ilçeler
    "İzmir Konak": (38.4189, 27.1287), "İzmir Buca": (38.3833, 27.1667),
    "İzmir Karşıyaka": (38.4559, 27.1094), "İzmir Bornova": (38.4667, 27.2167),
    "İzmir Bayraklı": (38.4597, 27.1597), "İzmir Çiğli": (38.5000, 27.0667),
    "İzmir Karabağlar": (38.3833, 27.1167), "İzmir Gaziemir": (38.3167, 27.1333),
    "İzmir Narlıdere": (38.3958, 27.0167), "İzmir Balçova": (38.3894, 27.0456),
    "İzmir Güzelbahçe": (38.3667, 26.8833), "İzmir Aliağa": (38.8000, 26.9667),
    "İzmir Bayındır": (38.2167, 27.6500), "İzmir Bergama": (39.1167, 27.1833),
    "İzmir Beydağ": (38.0833, 28.2167), "İzmir Çeşme": (38.3167, 26.3000),
    "İzmir Dikili": (39.0667, 26.8833), "İzmir Foça": (38.6667, 26.7500),
    "İzmir Karaburun": (38.6333, 26.5167), "İzmir Kemalpaşa": (38.4333, 27.4167),
    "İzmir Kınık": (39.0833, 27.3833), "İzmir Kiraz": (38.2333, 28.2000),
    "İzmir Menderes": (38.2500, 27.1333), "İzmir Menemen": (38.6000, 27.0667),
    "İzmir Ödemiş": (38.2333, 27.9667), "İzmir Seferihisar": (38.1833, 26.8333),
    "İzmir Selçuk": (37.9500, 27.3667), "İzmir Tire": (38.0833, 27.7333),
    "İzmir Torbalı": (38.1500, 27.3667), "İzmir Urla": (38.3167, 26.7667),
    # Bursa - Tüm ilçeler
    "Bursa Osmangazi": (40.1833, 29.0667), "Bursa Yıldırım": (40.1833, 29.1000),
    "Bursa Nilüfer": (40.2167, 28.9833), "Bursa Gürsu": (40.2333, 29.1667),
    "Bursa Kestel": (40.2000, 29.2167), "Bursa Büyükorhan": (39.7333, 28.8833),
    "Bursa Gemlik": (40.4333, 29.1500), "Bursa Harmancık": (39.6667, 29.1333),
    "Bursa İnegöl": (40.0833, 29.5167), "Bursa İznik": (40.4333, 29.7167),
    "Bursa Karacabey": (40.2167, 28.3667), "Bursa Keles": (39.9167, 29.2333),
    "Bursa Mudanya": (40.3667, 28.8833), "Bursa Mustafakemalpaşa": (39.9833, 28.4000),
    "Bursa Orhaneli": (39.8000, 28.9833), "Bursa Orhangazi": (40.4833, 29.3167),
    "Bursa Yenişehir": (40.2500, 29.6500),
    # Antalya - Tüm ilçeler
    "Antalya Muratpaşa": (36.8869, 30.7062), "Antalya Konyaaltı": (36.8694, 30.6350),
    "Antalya Kepez": (36.9333, 30.7167), "Antalya Döşemealtı": (37.0500, 30.5833),
    "Antalya Aksu": (36.9500, 30.8333), "Antalya Akseki": (37.0500, 31.7833),
    "Antalya Alanya": (36.5500, 32.0000), "Antalya Demre": (36.2500, 29.9833),
    "Antalya Elmalı": (36.7333, 29.9167), "Antalya Finike": (36.3000, 30.1500),
    "Antalya Gazipaşa": (36.2667, 32.3167), "Antalya Gündoğmuş": (36.8167, 31.9833),
    "Antalya İbradı": (37.1000, 31.5833), "Antalya Kaş": (36.1833, 29.6333),
    "Antalya Kemer": (36.5833, 30.5500), "Antalya Korkuteli": (37.0667, 30.2000),
    "Antalya Kumluca": (36.3667, 30.2833), "Antalya Manavgat": (36.7833, 31.4333),
    "Antalya Serik": (36.9167, 31.1000),
    # Gaziantep
    "Gaziantep Şahinbey": (37.0500, 37.3667), "Gaziantep Şehitkâmil": (37.0833, 37.3833),
    "Gaziantep Nizip": (37.0167, 37.8000),
    # Konya
    "Konya Selçuklu": (37.8833, 32.4500), "Konya Meram": (37.8333, 32.4333),
    "Konya Karatay": (37.8833, 32.5167), "Konya Ereğli": (37.5167, 34.0500),
    # Adana - Tüm ilçeler
    "Adana Seyhan": (36.9914, 35.3308), "Adana Çukurova": (37.0500, 35.3167),
    "Adana Yüreğir": (37.0000, 35.3833), "Adana Sarıçam": (37.0667, 35.4333),
    "Adana Aladağ": (37.5500, 35.4000), "Adana Ceyhan": (37.0167, 35.8167),
    "Adana Feke": (37.8167, 35.9167), "Adana İmamoğlu": (37.2667, 35.6667),
    "Adana Karaisalı": (37.2500, 35.0667), "Adana Karataş": (36.5667, 35.3833),
    "Adana Kozan": (37.4500, 35.8167), "Adana Pozantı": (37.4167, 34.8667),
    "Adana Saimbeyli": (37.9833, 36.1000), "Adana Tufanbeyli": (38.2667, 36.2167),
    "Adana Yumurtalık": (36.7667, 35.7833),
    # Mersin
    "Mersin Akdeniz": (36.8000, 34.6333), "Mersin Mezitli": (36.7667, 34.5500),
    "Mersin Toroslar": (36.8333, 34.6167), "Mersin Yenişehir": (36.8167, 34.6000),
    "Mersin Tarsus": (36.9167, 34.8833),
    # Kayseri
    "Kayseri Kocasinan": (38.7500, 35.4667), "Kayseri Melikgazi": (38.7167, 35.4833),
    "Kayseri Talas": (38.6833, 35.5500),
    # Diyarbakır
    "Diyarbakır Bağlar": (37.9000, 40.2000), "Diyarbakır Kayapınar": (37.9333, 40.1833),
    "Diyarbakır Sur": (37.9167, 40.2333), "Diyarbakır Yenişehir": (37.9167, 40.2167),
    # Kocaeli
    "Kocaeli İzmit": (40.7667, 29.9167), "Kocaeli Gebze": (40.8000, 29.4333),
    "Kocaeli Darıca": (40.7667, 29.3833), "Kocaeli Körfez": (40.7500, 29.7500),
    # Eskişehir
    "Eskişehir Odunpazarı": (39.7667, 30.5167), "Eskişehir Tepebaşı": (39.7833, 30.5000),
    # Samsun - Tüm ilçeler
    "Samsun Atakum": (41.3333, 36.2667), "Samsun Canik": (41.2500, 36.3667),
    "Samsun İlkadım": (41.2833, 36.3333), "Samsun Tekkeköy": (41.2167, 36.4667),
    "Samsun Alaçam": (41.6000, 35.9833), "Samsun Asarcık": (41.0333, 36.2333),
    "Samsun Ayvacık": (40.9667, 36.1833), "Samsun Bafra": (41.5667, 35.9000),
    "Samsun Çarşamba": (41.2000, 36.7167), "Samsun Havza": (40.9667, 35.6833),
    "Samsun Kavak": (41.0833, 36.0333), "Samsun Ladik": (40.9167, 35.9000),
    "Samsun Salıpazarı": (41.0833, 36.3500), "Samsun Terme": (41.2000, 36.9667),
    "Samsun Vezirköprü": (41.1333, 35.4500), "Samsun Yakakent": (41.6333, 35.5167),
    # Balıkesir - Tüm ilçeler
    "Balıkesir Altıeylül": (39.6500, 27.8833), "Balıkesir Karesi": (39.6500, 27.8667),
    "Balıkesir Ayvalık": (39.3167, 26.6833), "Balıkesir Balya": (39.7500, 27.5833),
    "Balıkesir Bandırma": (40.3500, 27.9667), "Balıkesir Bigadiç": (39.3833, 28.1333),
    "Balıkesir Burhaniye": (39.5000, 26.9667), "Balıkesir Dursunbey": (39.5833, 28.6333),
    "Balıkesir Edremit": (39.5833, 27.0167), "Balıkesir Altınoluk": (39.5667, 26.7333),
    "Balıkesir Erdek": (40.3833, 27.7833),
    "Balıkesir Gömeç": (39.3667, 26.8333), "Balıkesir Gönen": (40.1000, 27.6500),
    "Balıkesir Havran": (39.5500, 27.1000), "Balıkesir İvrindi": (39.5833, 27.4833),
    "Balıkesir Kepsut": (39.6833, 28.1333), "Balıkesir Manyas": (40.0500, 27.9667),
    "Balıkesir Marmara": (40.6167, 27.6000), "Balıkesir Savaştepe": (39.3833, 27.6500),
    "Balıkesir Sındırgı": (39.2333, 28.1667), "Balıkesir Susurluk": (39.9167, 28.1500),
    # Trabzon
    "Trabzon Ortahisar": (41.0027, 39.7168),
    # Şanlıurfa
    "Şanlıurfa Eyyübiye": (37.1500, 38.7833), "Şanlıurfa Haliliye": (37.1667, 38.8000),
    # Tekirdağ
    "Tekirdağ Süleymanpaşa": (40.9833, 27.5167), "Tekirdağ Çorlu": (41.1500, 27.8000),
    "Tekirdağ Çerkezköy": (41.2833, 27.9833),
    # Sakarya
    "Sakarya Adapazarı": (40.6667, 30.4000),
    # Manisa
    "Manisa Yunusemre": (38.6167, 27.4167), "Manisa Akhisar": (38.9167, 27.8333),
    # Denizli
    "Denizli Merkezefendi": (37.7833, 29.0833), "Denizli Pamukkale": (37.7667, 29.1000),
    # Muğla - Tüm ilçeler
    "Muğla Menteşe": (37.2153, 28.3636), "Muğla Bodrum": (37.0344, 27.4305),
    "Muğla Dalaman": (36.7667, 28.7833), "Muğla Datça": (36.7333, 27.6833),
    "Muğla Fethiye": (36.6500, 29.1167), "Muğla Kavaklıdere": (37.4333, 28.3667),
    "Muğla Köyceğiz": (36.9667, 28.6833), "Muğla Marmaris": (36.8500, 28.2667),
    "Muğla Milas": (37.3167, 27.7833), "Muğla Ortaca": (36.8333, 28.7667),
    "Muğla Seydikemer": (36.6167, 29.3500), "Muğla Ula": (37.1000, 28.4167),
    "Muğla Yatağan": (37.3333, 28.1333),
    # Malatya
    "Malatya Battalgazi": (38.3667, 38.3333), "Malatya Yeşilyurt": (38.3333, 38.2667),
}

def get_coordinates(city_label):
    """Şehir/ilçe etiketinden GPS koordinatlarını döndürür."""
    # Önce tam eşleşme (il + ilçe) ara
    if city_label in DISTRICT_COORDINATES:
        lat, lng = DISTRICT_COORDINATES[city_label]
        return {"latitude": lat, "longitude": lng, "accuracy": 100}
    # İl adıyla ara
    for city_name, coords in CITY_COORDINATES.items():
        if city_label.startswith(city_name):
            lat, lng = coords
            # İlçe varsa ama koordinat yoksa, il merkezine küçük sapma ekle
            if " " in city_label and city_label != city_name:
                lat += random.uniform(-0.03, 0.03)
                lng += random.uniform(-0.03, 0.03)
            return {"latitude": lat, "longitude": lng, "accuracy": 100}
    return None


class ClickResult:
    def __init__(self, keyword, city, ad_title, ad_url, status, error=None):
        self.keyword = keyword
        self.city = city
        self.ad_title = ad_title
        self.ad_url = ad_url
        self.status = status  # "success" | "failed" | "captcha"
        self.error = error
        self.timestamp = datetime.now().isoformat()

    def _parse_city(self):
        """Şehir etiketinden il ve ilçe ayır."""
        parts = self.city.split(" ", 1) if self.city else ["", ""]
        il = parts[0] if len(parts) >= 1 else ""
        ilce = parts[1] if len(parts) >= 2 else ""
        return il, ilce

    def to_dict(self):
        from urllib.parse import urlparse
        domain = ""
        try:
            domain = urlparse(self.ad_url).netloc.replace("www.", "")
        except Exception:
            pass
        il, ilce = self._parse_city()
        return {
            "keyword": self.keyword,
            "city": self.city,
            "il": il,
            "ilce": ilce,
            "title": self.ad_title or "",
            "ad_title": self.ad_title or "",
            "url": self.ad_url or "",
            "ad_url": self.ad_url or "",
            "domain": domain,
            "status": self.status,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class AdClickBot:
    def __init__(self, emit_log=None, emit_stats=None, emit_click=None):
        self.running = False
        self.paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread = None
        self._captcha_backoff = 30  # CAPTCHA bekleme suresi (artar)
        self._consecutive_captchas = 0  # Ardisik CAPTCHA sayaci
        self._daily_search_count = 0  # Gunluk arama sayaci
        self._daily_reset_date = None  # Son reset tarihi
        self.sheets_logger = SheetsLogger()
        self.email_reporter = EmailReporter()

        # Callbacks for real-time updates
        self._emit_log = emit_log or (lambda msg, level: None)
        self._emit_stats = emit_stats or (lambda stats: None)
        self._emit_click = emit_click or (lambda entry: None)

        # Stats
        self.stats = {
            "total_searches": 0,
            "total_ads_found": 0,
            "total_clicks": 0,
            "successful_clicks": 0,
            "failed_clicks": 0,
            "captcha_count": 0,
            "current_keyword": "",
            "current_city": "",
            "status": "idle",
        }
        self.click_history = []
        self._original_keywords = set()

        # Settings (safe defaults - ban onleme icin optimize)
        self.settings = {
            "delay_min": 30,
            "delay_max": 60,
            "click_delay_min": 10,
            "click_delay_max": 25,
            "page_stay_min": 20,
            "page_stay_max": 45,
            "pages_to_scan": 2,
            "headless": True,
            "proxy": "",
            "scan_mode": "power",  # "ads", "organic", "power"
            "daily_limit": 100,  # Gunluk max arama sayisi (0 = limitsiz)
            "captcha_pause_threshold": 3,  # Ardisik X CAPTCHA sonrasi otomatik duraklat
        }

    # --- Google Suggest ile dinamik türev üretici ---
    def _get_google_suggestions(self, keyword):
        """Google Suggest API'den popüler arama türevlerini çek."""
        import urllib.request
        import urllib.parse

        suggestions = []
        try:
            encoded = urllib.parse.quote(keyword)
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=tr&gl=tr&q={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode("utf-8"))
            if len(data) > 1 and isinstance(data[1], list):
                suggestions = data[1]
        except Exception as e:
            self.log(f"Google Suggest hatası: {e}", "warning")
        return suggestions

    def _expand_keywords_dynamic(self, keywords, cities=None):
        """Her anahtar kelime için Google Suggest'ten popüler türevleri çek.
        Lokasyon içeren önerileri filtrele (GPS zaten lokasyonu belirliyor)."""
        originals = []
        variants = []
        seen = set()

        # Lokasyon filtresi: seçilen şehirlerden il/ilçe adlarını çıkar
        location_words = set()
        # 81 il adı
        il_adlari = [
            "adana","adıyaman","afyon","afyonkarahisar","ağrı","amasya","ankara","antalya","artvin","aydın",
            "balıkesir","bilecik","bingöl","bitlis","bolu","burdur","bursa","çanakkale","çankırı","çorum",
            "denizli","diyarbakır","edirne","elazığ","erzincan","erzurum","eskişehir","gaziantep","giresun",
            "gümüşhane","hakkari","hatay","ısparta","mersin","istanbul","izmir","kars","kastamonu","kayseri",
            "kırklareli","kırşehir","kocaeli","konya","kütahya","malatya","manisa","kahramanmaraş","mardin",
            "muğla","muş","nevşehir","niğde","ordu","rize","sakarya","samsun","siirt","sinop","sivas",
            "tekirdağ","tokat","trabzon","tunceli","şanlıurfa","uşak","van","yozgat","zonguldak","aksaray",
            "bayburt","karaman","kırıkkale","batman","şırnak","bartın","ardahan","iğdır","yalova","karabük",
            "kilis","osmaniye","düzce"
        ]
        for il in il_adlari:
            location_words.add(il)

        # Seçilen şehirlerin ilçe adlarını da ekle
        if cities:
            for city_str in cities:
                parts = city_str.strip().split()
                for p in parts:
                    if len(p) > 2:
                        location_words.add(p.lower())

        # Yaygın semt/mahalle adları
        common_locations = [
            "eryaman","batıkent","çayyolu","ümitköy","bahçelievler","beşevler","kızılay","tunalı",
            "kadıköy","beşiktaş","taksim","üsküdar","bakırköy","ataşehir","maltepe","pendik",
            "bornova","karşıyaka","alsancak","konak","bayraklı","buca","çiğli",
            "lara","konyaaltı","kepez","muratpaşa","alanya","manavgat","serik",
            "nilüfer","osmangazi","yıldırım","mudanya","gemlik","inegöl",
        ]
        for loc in common_locations:
            location_words.add(loc)

        for kw in keywords:
            kw_clean = kw.strip()
            if not kw_clean:
                continue

            # Orijinal kelimeyi ekle
            if kw_clean.lower() not in seen:
                seen.add(kw_clean.lower())
                originals.append(kw_clean)

            # Google Suggest'ten türevleri çek
            suggestions = self._get_google_suggestions(kw_clean)
            added = 0
            for sug in suggestions:
                sug_clean = sug.strip()
                if not sug_clean or sug_clean.lower() in seen:
                    continue

                # Lokasyon kelimesi içeren önerileri atla
                sug_lower = sug_clean.lower()
                sug_words = sug_lower.split()
                skip = False
                for word in sug_words:
                    if word in location_words and word not in kw_clean.lower():
                        skip = True
                        break
                if skip:
                    continue

                seen.add(sug_clean.lower())
                variants.append(sug_clean)
                added += 1
                if added >= 5:
                    break

            if added > 0:
                self.log(f"  '{kw_clean}' → +{added} türev (Google Suggest)")

        # Önce orijinal kelimeler, sonra türevler
        # Hangi kelimenin orijinal/türev olduğunu takip et
        self._original_keywords = set(k.lower() for k in originals)
        return originals + variants

    def log(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{ts}] {msg}"
        getattr(log, level, log.info)(msg)
        self._emit_log(full_msg, level)

    def update_stats(self):
        self._emit_stats(self.stats.copy())

    def start(self, cities, keywords, settings=None):
        if self.running:
            self.log("Bot zaten çalışıyor!", "warning")
            return
        if settings:
            self.settings.update(settings)
        self._stop_event.clear()
        self._pause_event.clear()
        self.running = True
        self.paused = False
        self.stats["status"] = "running"
        self.update_stats()
        self._thread = threading.Thread(
            target=self._run, args=(cities, keywords), daemon=True
        )
        self._thread.start()
        self.log("Bot başlatıldı.")

    def stop(self):
        if not self.running:
            return
        self._stop_event.set()
        self.running = False
        self.paused = False
        self.stats["status"] = "stopped"
        self.update_stats()
        self.log("Bot durduruluyor...")

    def pause(self):
        if not self.running:
            return
        self.paused = True
        self._pause_event.set()
        self.stats["status"] = "paused"
        self.update_stats()
        self.log("Bot duraklatildi.")

    def resume(self):
        if not self.running:
            return
        self.paused = False
        self._pause_event.clear()
        self.stats["status"] = "running"
        self.update_stats()
        self.log("Bot devam ediyor.")

    def _check_stop(self):
        return self._stop_event.is_set()

    def _wait_pause(self):
        while self._pause_event.is_set() and not self._stop_event.is_set():
            time.sleep(0.5)

    def _check_daily_limit(self):
        """Tarama basina arama limitini kontrol et. True = limit asildi."""
        limit = self.settings.get("daily_limit", 100)
        if limit <= 0:
            return False
        if self._daily_search_count >= limit:
            self.log(f"Tarama limiti ({limit}) tamamlandı. Bot duruyor.", "info")
            return True
        return False

    def _handle_captcha_streak(self):
        """Ardisik CAPTCHA kontrolu. True = bot duraklatilmali."""
        self._consecutive_captchas += 1
        threshold = self.settings.get("captcha_pause_threshold", 3)
        if self._consecutive_captchas >= threshold:
            wait = min(self._consecutive_captchas * 60, 300)  # max 5 dakika
            self.log(f"Ardışık {self._consecutive_captchas} CAPTCHA! {wait//60} dk mola veriliyor...", "error")
            end_time = time.time() + wait
            while time.time() < end_time:
                if self._check_stop():
                    return True
                time.sleep(1)
            return False
        return False

    def _smart_delay(self):
        """Arama sayisina gore artan gecikme. Cok arama = daha uzun bekleme."""
        base_min = self.settings["delay_min"]
        base_max = self.settings["delay_max"]
        searches = self._daily_search_count
        if searches > 75:
            multiplier = 2.5
        elif searches > 50:
            multiplier = 2.0
        elif searches > 25:
            multiplier = 1.5
        else:
            multiplier = 1.0
        self._human_delay(base_min * multiplier, base_max * multiplier)

    def _human_delay(self, min_s=None, max_s=None):
        mn = min_s or self.settings["delay_min"]
        mx = max_s or self.settings["delay_max"]
        delay = random.uniform(mn, mx)
        self.log(f"Bekleniyor: {delay:.1f}s")
        # Sleep in small chunks so we can respond to stop
        end_time = time.time() + delay
        while time.time() < end_time:
            if self._check_stop():
                return
            time.sleep(0.3)

    def _human_mouse_move(self, page: Page):
        """Simulate random mouse movements for anti-detection."""
        try:
            vw = page.viewport_size["width"]
            vh = page.viewport_size["height"]
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, vw - 100)
                y = random.randint(100, vh - 100)
                page.mouse.move(x, y, steps=random.randint(5, 15))
                time.sleep(random.uniform(0.1, 0.4))
        except Exception:
            pass

    def _human_scroll(self, page: Page):
        """Simulate human-like scrolling."""
        try:
            for _ in range(random.randint(2, 4)):
                delta = random.randint(150, 500)
                page.mouse.wheel(0, delta)
                time.sleep(random.uniform(0.5, 1.5))
        except Exception:
            pass

    def _close_cookie_banner(self, page: Page):
        for btn_text in ["Tumunu kabul et", "Accept all", "Kabul et", "Agree", "Tamam"]:
            try:
                btn = page.locator(f"button:has-text('{btn_text}')").first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    time.sleep(1)
                    self.log("Cookie banner kapatildi.")
                    return
            except Exception:
                continue

    def _check_captcha(self, page: Page) -> bool:
        url = page.url
        if "sorry/index" in url or "/sorry/" in url or "google.com/sorry" in url:
            return True
        try:
            if page.locator("form#captcha-form").count() > 0:
                return True
            if page.locator("iframe[src*='recaptcha']").count() > 0:
                return True
            body_text = page.locator("body").inner_text(timeout=2000)
            if "unusual traffic" in body_text.lower() or "olagan disi trafik" in body_text.lower():
                return True
        except Exception:
            pass
        return False

    def _solve_captcha(self, page: Page) -> bool:
        """OpenAI Vision (GPT-4o) ile CAPTCHA otomatik çöz."""
        api_key = os.getenv("OPENAI_API_KEY") or self.settings.get("openai_api_key", "")
        if not api_key:
            self.log("CAPTCHA çözücü: OpenAI API key yok, atlanıyor.", "warning")
            return False

        import requests as _requests
        import base64 as _b64

        self.log("CAPTCHA tespit edildi, OpenAI Vision çözüyor...", "info")

        try:
            img_b64 = None
            captcha_type = None  # "image" veya "screenshot"

            # 1) Google sorry sayfası image CAPTCHA
            img = page.locator("img[src*='sorry']")
            if img.count() == 0:
                img = page.locator("#captcha-form img")
            if img.count() > 0:
                img_src = img.first.get_attribute("src") or ""
                if img_src:
                    if not img_src.startswith("http"):
                        img_src = f"https://www.google.com{img_src}"
                    img_resp = _requests.get(img_src, timeout=10)
                    img_b64 = _b64.b64encode(img_resp.content).decode()
                    captcha_type = "image"
                    self.log("Image CAPTCHA bulundu, OpenAI'ya gönderiliyor...")

            # 2) Diğer CAPTCHA tipleri - ekran görüntüsü al
            if not img_b64:
                screenshot_bytes = page.screenshot(type="png")
                img_b64 = _b64.b64encode(screenshot_bytes).decode()
                captcha_type = "screenshot"
                self.log("Ekran görüntüsü alındı, OpenAI analiz ediyor...")

            # --- OpenAI Vision API çağrısı ---
            if captcha_type == "image":
                prompt = (
                    "Bu bir CAPTCHA görüntüsüdür. Görüntüdeki metni tam olarak oku ve yaz. "
                    "Sadece CAPTCHA metnini yaz, başka hiçbir şey yazma. "
                    "Büyük/küçük harf ayrımına dikkat et."
                )
            else:
                prompt = (
                    "Bu bir web sayfasının ekran görüntüsüdür ve bir CAPTCHA/güvenlik doğrulaması içeriyor. "
                    "Eğer metin tabanlı bir CAPTCHA varsa, metni tam olarak yaz. "
                    "Eğer bir checkbox (ben robot değilim) varsa 'CHECKBOX' yaz. "
                    "Eğer resim seçme CAPTCHA'sı varsa (trafik ışığı, araba vb. seç) 'IMAGE_SELECT' yaz. "
                    "Sadece sonucu yaz, açıklama yapma."
                )

            resp = _requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_b64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 100,
                },
                timeout=30,
            ).json()

            if "error" in resp:
                self.log(f"OpenAI hata: {resp['error'].get('message', resp['error'])}", "error")
                return False

            answer = resp["choices"][0]["message"]["content"].strip()
            self.log(f"OpenAI yanıt: '{answer}'")

            # --- Yanıta göre işlem ---
            if answer == "IMAGE_SELECT":
                self.log("CAPTCHA tipi 'IMAGE_SELECT' — otomatik çözülemiyor.", "warning")
                return False

            if answer == "CHECKBOX":
                self.log("reCAPTCHA checkbox tespit edildi, tıklanıyor...", "info")
                try:
                    # reCAPTCHA iframe içinde çalışır
                    recaptcha_frame = None
                    for frame in page.frames:
                        if "recaptcha" in (frame.url or ""):
                            recaptcha_frame = frame
                            break

                    if recaptcha_frame:
                        # İnsan gibi: iframe'deki checkbox'a tıkla
                        checkbox = recaptcha_frame.locator("#recaptcha-anchor")
                        if checkbox.count() > 0:
                            time.sleep(random.uniform(0.5, 1.5))
                            checkbox.click()
                            time.sleep(random.uniform(2.0, 4.0))

                            # Tıklamadan sonra kontrol et
                            if not self._check_captcha(page):
                                self.log("CAPTCHA checkbox ile aşıldı!", "success")
                                return True

                            # Checkbox tıklandı ama image challenge çıkmış olabilir
                            self.log("Checkbox tıklandı ama ek doğrulama istendi.", "warning")
                            return False
                    else:
                        # iframe bulunamadı — doğrudan checkbox dene
                        cb = page.locator(".recaptcha-checkbox-border, .recaptcha-checkbox")
                        if cb.count() > 0:
                            time.sleep(random.uniform(0.5, 1.5))
                            cb.first.click()
                            time.sleep(random.uniform(2.0, 4.0))
                            if not self._check_captcha(page):
                                self.log("CAPTCHA checkbox ile aşıldı!", "success")
                                return True

                    # Google sorry sayfasındaki "Ben robot değilim" butonu
                    sorry_btn = page.locator("input[type='submit']")
                    if sorry_btn.count() > 0:
                        time.sleep(random.uniform(0.5, 1.0))
                        sorry_btn.first.click()
                        time.sleep(random.uniform(2.0, 4.0))
                        if not self._check_captcha(page):
                            self.log("CAPTCHA sorry butonu ile aşıldı!", "success")
                            return True

                    self.log("CHECKBOX tıklanamadı.", "warning")
                    return False
                except Exception as e:
                    self.log(f"CHECKBOX tıklama hatası: {e}", "warning")
                    return False

            # Metin CAPTCHA çözümü — input alanına yaz
            captcha_input = None
            for selector in [
                "input[name='captcha']",
                "input#captcha-input",
                "#captcha-form input[type='text']",
                "form input[type='text']",
            ]:
                loc = page.locator(selector)
                if loc.count() > 0:
                    captcha_input = loc.first
                    break

            if not captcha_input:
                self.log("CAPTCHA input alanı bulunamadı.", "warning")
                return False

            captcha_input.fill(answer)
            self.log(f"CAPTCHA metni girildi: '{answer}', form gönderiliyor...")

            try:
                page.locator("input[type='submit'], button[type='submit']").first.click()
            except Exception:
                try:
                    page.evaluate("document.querySelector('form').submit()")
                except Exception:
                    pass

            time.sleep(3)

            if not self._check_captcha(page):
                self.log("CAPTCHA aşıldı! (OpenAI Vision)", "success")
                return True
            else:
                self.log("Metin girildi ama CAPTCHA hala aktif.", "warning")
                return False

        except Exception as e:
            self.log(f"CAPTCHA çözücü hatası: {e}", "error")
            return False

    def _scroll_full_page(self, page: Page):
        """Sayfanin tamamini scroll et, alt reklamlar yuklensin."""
        try:
            for _ in range(6):
                page.mouse.wheel(0, random.randint(400, 800))
                time.sleep(random.uniform(0.4, 0.8))
            # Sayfanin en altina in
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)
            # Tekrar yukari cik (insan gibi)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)
        except Exception:
            pass

    def _find_ads(self, page: Page) -> list:
        """Sayfadaki TUM reklam bolgelerini tara - JavaScript ile dogrudan DOM'dan cek."""
        all_ads = []
        seen_urls = set()

        # Yontem 1: Zone-bazli CSS selektorler ile tara
        for zone in AD_ZONES:
            zone_name = zone["name"]
            zone_found = 0

            for sel in zone["container_selectors"]:
                try:
                    count = page.locator(sel).count()
                    if count == 0:
                        continue

                    for i in range(count):
                        block = page.locator(sel).nth(i)
                        ad_info = self._extract_ad_info(block)
                        if ad_info and ad_info["url"] not in seen_urls:
                            seen_urls.add(ad_info["url"])
                            ad_info["zone"] = zone_name
                            all_ads.append(ad_info)
                            zone_found += 1

                    if zone_found > 0:
                        break
                except Exception:
                    continue

            if zone_found > 0:
                self.log(f"  [{zone_name}] {zone_found} reklam bulundu")

        # Yontem 2: JavaScript ile reklam container'lari icindeki linkleri bul
        # Sadece bilinen reklam alanlari (#tads, #tadsb, [data-text-ad]) icinde arama yapar
        try:
            js_ads = page.evaluate("""() => {
                const results = [];
                const seen = new Set();

                // Bilinen reklam container'lari - SADECE bunlarin icinde ara
                const adContainers = [
                    ...document.querySelectorAll('#tads [data-text-ad]'),
                    ...document.querySelectorAll('#tadsb [data-text-ad]'),
                    ...document.querySelectorAll('#tads .uEierd'),
                    ...document.querySelectorAll('#tadsb .uEierd'),
                    ...document.querySelectorAll('[data-text-ad]'),
                    ...document.querySelectorAll('div[aria-label="Ads"] .uEierd'),
                    ...document.querySelectorAll('div[aria-label="Reklamlar"] .uEierd'),
                ];

                adContainers.forEach(container => {
                    const links = container.querySelectorAll('a[href^="http"]');
                    for (const a of links) {
                        const href = a.href;
                        if (!href || href.includes('google.com/') || seen.has(href)) continue;

                        // h3 veya heading role olan baslik bul
                        const h3 = a.querySelector('h3') || a.querySelector('[role="heading"]');
                        if (!h3) continue;

                        seen.add(href);

                        // Zone belirle - #tads = Top, #tadsb = Bottom
                        let zone = 'Sponsorlu';
                        const tads = a.closest('#tads');
                        const tadsb = a.closest('#tadsb');
                        if (tads) zone = 'Top Ads';
                        else if (tadsb) zone = 'Bottom Ads';

                        results.push({
                            url: href,
                            title: h3.textContent?.trim() || '',
                            zone: zone
                        });
                    }
                });

                return results;
            }""")

            for ad in js_ads:
                if ad["url"] not in seen_urls:
                    seen_urls.add(ad["url"])
                    # Zone belirle
                    zone_label = "Sponsorlu"

                    # Playwright element'i bul (tıklamak için)
                    try:
                        link_el = page.locator(f'a[href="{ad["url"]}"]').first
                        if link_el.count() > 0 or True:
                            firm = domain_to_firm_name(ad["url"])
                            all_ads.append({
                                "title": firm,
                                "url": ad["url"],
                                "element": link_el,
                                "zone": zone_label,
                            })
                            self.log(f"  [JS:{zone_label}] {firm}")
                    except Exception:
                        continue
        except Exception as e:
            self.log(f"JS reklam tarama hatası: {e}", "warning")

        if not all_ads:
            self._dump_debug_html(page)

        self.log(f"  TOPLAM: {len(all_ads)} reklam bulundu")
        return all_ads

    def _find_organic_results(self, page: Page) -> list:
        """Sayfadaki organik (reklam olmayan) arama sonuclarini bul."""
        results = []
        seen_urls = set()

        # Organik sonuclar genelde #search icerisinde, #rso altinda
        organic_selectors = [
            "#rso div.g:not([data-text-ad]) > div > div > div > a[href^='http']",
            "#rso div.g > div > a[href^='http']",
            "#rso .tF2Cxc a[href^='http']",
            "#search div.g a[href^='http']:not([data-rw])",
        ]

        for sel in organic_selectors:
            try:
                links = page.locator(sel)
                count = links.count()
                for i in range(count):
                    try:
                        el = links.nth(i)
                        href = el.get_attribute("href", timeout=1000)
                        if not href or "google.com" in href:
                            continue
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        # Baslik bul
                        title = ""
                        try:
                            title = el.locator("h3").first.inner_text(timeout=1000)
                        except Exception:
                            try:
                                title = el.inner_text(timeout=1000)[:80]
                            except Exception:
                                title = "(başlık yok)"

                        results.append({
                            "title": title.strip() or "(başlık yok)",
                            "url": href,
                            "element": el,
                            "zone": "Organik",
                        })
                    except Exception:
                        continue

                if results:
                    break  # Bir selector yeterliyse devam etme
            except Exception:
                continue

        return results

    def _extract_ad_info(self, block) -> Optional[dict]:
        """Reklam blogundan firma adı (domain) ve link cikart."""
        link_el = None
        url = ""

        # Tiklanabilir link bul
        for sel in AD_LINK_SELECTORS:
            try:
                el = block.locator(sel).first
                href = el.get_attribute("href", timeout=1000)
                if href and href.startswith("http") and "google.com" not in href:
                    link_el = el
                    url = href
                    break
            except Exception:
                continue

        if link_el and url:
            # Firma adı = domain
            title = domain_to_firm_name(url)
            return {"title": title, "url": url, "element": link_el}
        return None

    def _dump_debug_html(self, page: Page):
        """Reklam bulunamadiginda debug icin HTML kaydet."""
        try:
            html = page.content()
            debug_path = Path("debug_last_page.html")
            debug_path.write_text(html, encoding="utf-8")
            self.log(f"DEBUG: Sayfa HTML'i kaydedildi -> {debug_path}", "warning")

            # Sayfada 'Sponsorlu' veya 'Sponsored' var mi kontrol et
            has_sponsored = "Sponsorlu" in html or "Sponsored" in html
            has_tads = 'id="tads"' in html
            has_tadsb = 'id="tadsb"' in html
            self.log(f"DEBUG: Sponsorlu={has_sponsored}, #tads={has_tads}, #tadsb={has_tadsb}", "warning")
        except Exception:
            pass

    def _is_excluded_domain(self, url):
        """Muaf domainleri kontrol et."""
        excluded = self.settings.get("excluded_domains", [])
        if not excluded:
            return False
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace("www.", "").lower()
            for ex in excluded:
                ex = ex.strip().lower().replace("www.", "")
                if ex and (domain == ex or domain.endswith("." + ex)):
                    return True
        except Exception:
            pass
        return False

    def _is_target_domain(self, url):
        """Hedef domain kontrolü (SEO modu)."""
        targets = self.settings.get("target_domains", [])
        if not targets:
            return False
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace("www.", "").lower()
            for t in targets:
                t = t.strip().lower().replace("www.", "")
                if t and (domain == t or domain.endswith("." + t)):
                    return True
        except Exception:
            pass
        return False

    def _seo_browse_site(self, page: Page, context: BrowserContext, keyword: str, city: str, url: str, title: str):
        """SEO katkı: Hedef sitede insan gibi gezin."""
        from urllib.parse import urlparse
        base_domain = urlparse(url).netloc
        stay_min = self.settings.get("seo_stay_min", 2) * 60  # dakika -> saniye
        stay_max = self.settings.get("seo_stay_max", 4) * 60
        click_min = self.settings.get("seo_click_min", 2)
        click_max = self.settings.get("seo_click_max", 4)
        total_stay = random.uniform(stay_min, stay_max)
        internal_clicks = random.randint(click_min, click_max)

        self.log(f"🔍 SEO: {base_domain} sitesinde {total_stay/60:.1f}dk gezilecek, {internal_clicks} iç sayfa tıklanacak")

        try:
            new_page = context.new_page()
            _stealth.apply_stealth_sync(new_page)
            new_page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # 1. İlk sayfada doğal okuma
            time_per_section = total_stay / (internal_clicks + 1)

            # İlk sayfada oku - yavaş scroll + mouse
            self._seo_read_page(new_page, time_per_section)
            self.log(f"📖 SEO: Ana sayfa okundu ({time_per_section/60:.1f}dk)")

            # 2. Site içi linklere tıkla (sayfa derinliği artır)
            clicked_urls = set()
            for click_idx in range(internal_clicks):
                if self._check_stop():
                    break
                try:
                    # Site içi linkleri bul (aynı domain, reklam olmayan)
                    links = new_page.evaluate(f"""() => {{
                        const allLinks = Array.from(document.querySelectorAll('a[href]'));
                        return allLinks
                            .filter(a => {{
                                const href = a.href;
                                if (!href || href.startsWith('javascript:') || href.startsWith('#') || href.startsWith('mailto:')) return false;
                                if (href.includes('google') || href.includes('doubleclick') || href.includes('googlesyndication') || href.includes('googleads')) return false;
                                try {{ return new URL(href).hostname.includes('{base_domain.replace("www.", "")}'); }} catch {{ return false; }}
                            }})
                            .map(a => ({{ url: a.href, text: (a.textContent || '').trim().substring(0, 80) }}))
                            .filter(a => a.text.length > 2 && a.url.length < 300);
                    }}""")

                    # Ziyaret edilmemiş linkleri filtrele
                    available = [l for l in links if l["url"] not in clicked_urls and l["url"] != url]
                    if not available:
                        self.log(f"📖 SEO: Yeni iç link bulunamadı, sayfada okumaya devam")
                        self._seo_read_page(new_page, time_per_section)
                        continue

                    # Rastgele bir iç link seç
                    target_link = random.choice(available)
                    clicked_urls.add(target_link["url"])
                    self.log(f"🔗 SEO: İç sayfa tıklanıyor ({click_idx+1}/{internal_clicks}): {target_link['text'][:40]}")

                    new_page.goto(target_link["url"], wait_until="domcontentloaded", timeout=20000)

                    # Sayfada oku
                    self._seo_read_page(new_page, time_per_section)
                    self.log(f"📖 SEO: İç sayfa okundu ({time_per_section/60:.1f}dk)")

                except Exception as e:
                    self.log(f"SEO iç link hatası: {e}", "warning")
                    self._seo_read_page(new_page, time_per_section * 0.5)

            new_page.close()

            result = ClickResult(keyword, city, title, url, "success")
            self.stats["successful_clicks"] += 1
            self.log(f"✅ SEO: {base_domain} - {total_stay/60:.1f}dk, {len(clicked_urls)} iç sayfa gezildi")

        except Exception as e:
            result = ClickResult(keyword, city, title, url, "failed", str(e))
            self.stats["failed_clicks"] += 1
            self.log(f"SEO hata: {e}", "error")
            try:
                if 'new_page' in dir() and new_page and not new_page.is_closed():
                    new_page.close()
            except Exception:
                pass

        self.stats["total_clicks"] += 1
        result_dict = result.to_dict()
        result_dict["zone"] = "Organik (SEO)"
        result_dict["kw_type"] = "ORİJİNAL" if keyword.lower() in getattr(self, '_original_keywords', set()) else "TÜREV"
        self.click_history.append(result_dict)
        self.update_stats()
        self._emit_click(result_dict)

    def _seo_read_page(self, page, duration):
        """Bir sayfada insan gibi okuma simülasyonu."""
        if duration <= 0:
            return
        segments = random.randint(3, 6)
        segment_time = duration / segments

        for i in range(segments):
            if self._check_stop():
                break
            try:
                # Doğal mouse hareketi
                self._human_mouse_move(page)
                time.sleep(segment_time * 0.2)

                # Yavaş scroll (az miktarda)
                scroll_amount = random.randint(100, 400)
                page.evaluate(f"""() => {{
                    let scrolled = 0;
                    const target = {scroll_amount};
                    const step = () => {{
                        const chunk = Math.min(target - scrolled, {random.randint(20, 60)});
                        window.scrollBy(0, chunk);
                        scrolled += chunk;
                        if (scrolled < target) requestAnimationFrame(step);
                    }};
                    step();
                }}""")
                time.sleep(segment_time * 0.3)

                # Bazen yukarı scroll (geri dönme efekti)
                if random.random() < 0.25:
                    page.evaluate(f"window.scrollBy(0, -{random.randint(50, 150)})")

                # Okuma süresi
                time.sleep(segment_time * 0.5)

                # Bazen fare ile metin üzerinde gezinme
                if random.random() < 0.3:
                    self._human_mouse_move(page)

            except Exception:
                time.sleep(segment_time)

    def _seo_search_and_click(self, page: Page, context: BrowserContext, keyword: str, city: str, search_query: str):
        """SEO modu: Google'da ara, sayfalar arası hedef domain'i bul ve tıkla."""
        target_domains = self.settings.get("target_domains", [])
        if not target_domains:
            self.log("SEO: Hedef domain belirtilmedi, atlıyorum.", "warning")
            return

        max_pages = self.settings.get("seo_max_pages", 5)

        for page_num in range(1, max_pages + 1):
            if self._check_stop():
                break

            if page_num > 1:
                # Sonraki sayfaya git
                try:
                    next_btn = page.locator('a#pnnext, a[aria-label="Next"]').first
                    if next_btn.is_visible(timeout=3000):
                        next_btn.click()
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                        time.sleep(random.uniform(1.5, 3.0))
                    else:
                        self.log(f"SEO: Sayfa {page_num} bulunamadı, aramayı bitiriyorum.")
                        break
                except Exception:
                    self.log(f"SEO: Sonraki sayfaya geçilemedi.")
                    break

            # Yavaş scroll ile sayfayı oku (insan gibi)
            self._human_scroll(page)
            time.sleep(random.uniform(1.0, 2.0))

            # Sayfadaki TÜM linkleri al ve hedef domain'i ara
            from urllib.parse import urlparse
            target_found = False

            for td in target_domains:
                if target_found:
                    break
                td_clean = td.strip().lower().replace("www.", "").replace("https://", "").replace("http://", "")
                if not td_clean:
                    continue

                # Playwright ile sayfadaki tüm linkleri tara
                all_links = page.locator(f'a[href*="{td_clean}"]')
                count = all_links.count()
                self.log(f"SEO: Sayfa {page_num} - '{td_clean}' içeren {count} link bulundu")

                for i in range(count):
                    try:
                        link = all_links.nth(i)
                        href = link.get_attribute("href", timeout=2000)
                        if not href:
                            continue

                        r_domain = urlparse(href).netloc.replace("www.", "").lower()
                        if r_domain == td_clean or r_domain.endswith("." + td_clean):
                            # Reklam mı kontrol et
                            is_ad = link.evaluate("""el => {
                                return !!el.closest('[data-text-ad], [data-rw], .ads-ad, #tads, #tadsb');
                            }""")
                            if is_ad:
                                self.log(f"SEO: {td_clean} reklam olarak bulundu, atlıyorum.")
                                continue

                            title = ""
                            try:
                                title = link.locator("h3").first.inner_text(timeout=1000)
                            except Exception:
                                try:
                                    title = link.inner_text(timeout=1000)[:80]
                                except Exception:
                                    title = td_clean

                            self.log(f"🎯 SEO: Hedef domain bulundu! Sayfa {page_num}: {title[:50]}")
                            self._seo_browse_site(page, context, keyword, city, href, title)
                            target_found = True
                            break
                    except Exception:
                        continue

            if target_found:
                return

            # Bu sayfada bulunamadı, doğal bekleme ile sonraki sayfaya geç
            self.log(f"SEO: Sayfa {page_num}'de hedef domain bulunamadı, devam ediliyor...")
            time.sleep(random.uniform(2.0, 4.0))
            self._human_scroll(page)

        self.log(f"SEO: {max_pages} sayfada hedef domain bulunamadı.", "warning")

    def _click_ad(self, page: Page, context: BrowserContext, ad_info: dict, keyword: str, city: str):
        """Click on an ad and stay on the page for a while."""
        title = ad_info["title"]
        url = ad_info["url"]

        # Muaf domain kontrolü
        if self._is_excluded_domain(url):
            self.log(f"⏭️ Muaf domain, atlanıyor: {url[:60]}", "info")
            return

        self.log(f"Reklama tıklanıyor: {title[:60]}...")

        try:
            # Open in new tab to simulate real behavior
            new_page = context.new_page()
            _stealth.apply_stealth_sync(new_page)
            new_page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Stay on the ad page - simulate reading
            stay_time = random.uniform(
                self.settings["page_stay_min"],
                self.settings["page_stay_max"]
            )
            self.log(f"Reklam sayfasında {stay_time:.0f}s kalınıyor...")

            # Human-like behavior on ad page
            self._human_mouse_move(new_page)
            time.sleep(stay_time * 0.3)
            self._human_scroll(new_page)
            time.sleep(stay_time * 0.4)
            self._human_mouse_move(new_page)
            time.sleep(stay_time * 0.3)

            new_page.close()

            result = ClickResult(keyword, city, title, url, "success")
            self.stats["successful_clicks"] += 1
            self.log(f"Başarılı tıklama: {title[:60]}")

        except Exception as e:
            result = ClickResult(keyword, city, title, url, "failed", str(e))
            self.stats["failed_clicks"] += 1
            self.log(f"Tıklama hatası: {e}", "error")
            try:
                # Close the tab if it's still open
                if 'new_page' in dir() and new_page and not new_page.is_closed():
                    new_page.close()
            except Exception:
                pass

        self.stats["total_clicks"] += 1
        result_dict = result.to_dict()
        result_dict["zone"] = ad_info.get("zone", "")
        result_dict["kw_type"] = "ORİJİNAL" if keyword.lower() in getattr(self, '_original_keywords', set()) else "TÜREV"
        self.click_history.append(result_dict)
        self.update_stats()
        self._emit_click(result_dict)

        # Google Sheets'e kaydet
        self.sheets_logger.log_click(result_dict)

        return result

    def _run(self, cities, keywords):
        """Main bot loop."""
        mode_names = {"ads": "Google Ads", "organic": "Organik", "power": "Power"}
        mode_name = mode_names.get(self.settings.get("scan_mode", "power"), "Power")

        # Google Suggest ile dinamik türevler üret (lokasyon kelimeleri filtrelenir)
        original_count = len(keywords)
        keywords = self._expand_keywords_dynamic(keywords, cities=cities)
        variant_count = len(keywords) - original_count
        self.log(f"📋 {original_count} ORİJİNAL + {variant_count} TÜREV = {len(keywords)} anahtar kelime")
        self.log(f"🔵 Sıralama: Önce ORİJİNAL kelimeler, sonra TÜREV kelimeler aranacak")
        self.log(f"Gorev: {len(cities)} sehir x {len(keywords)} anahtar kelime | Mod: {mode_name}")

        try:
            with sync_playwright() as p:
                # Launch browser - anti-detection optimized
                launch_args = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-infobars",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-extensions",
                    "--disable-sync",
                    "--disable-translate",
                    "--metrics-recording-only",
                    "--no-first-run",
                    "--safebrowsing-disable-auto-update",
                    "--password-store=basic",
                    "--use-mock-keychain",
                ]
                # Headless=new (yeni Chromium headless - eski headless'tan çok daha iyi)
                browser = p.chromium.launch(
                    headless=self.settings["headless"],
                    args=launch_args,
                    channel="chromium",
                )

                self._captcha_backoff = 30  # Reset backoff
                self._consecutive_captchas = 0  # Reset CAPTCHA streak
                self._daily_search_count = 0  # Her tarama basinda sayac sifirla

                # Warm-up: Önce normal bir Google ziyareti yap (cookie al, güven oluştur)
                self.log("Warm-up: Google'a bağlanılıyor...")
                try:
                    warmup_ctx = browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport=random.choice(VIEWPORT_SIZES),
                        locale="tr-TR",
                        timezone_id="Europe/Istanbul",
                    )
                    warmup_page = warmup_ctx.new_page()
                    _stealth.apply_stealth_sync(warmup_page)
                    warmup_page.goto("https://www.google.com/?hl=tr", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(1.5, 3))
                    # Cookie banner'ı kabul et
                    self._close_cookie_banner(warmup_page)
                    time.sleep(random.uniform(1, 2))
                    # Google'ın storage state'ini kaydet (cookie'ler dahil)
                    self._google_storage = warmup_ctx.storage_state()
                    warmup_page.close()
                    warmup_ctx.close()
                    self.log("Warm-up tamamlandı, cookie'ler kaydedildi.")
                except Exception as e:
                    self._google_storage = None
                    self.log(f"Warm-up başarısız: {e}", "warning")

                for city in cities:
                    if self._check_stop():
                        break
                    if self._check_daily_limit():
                        self._stop_event.set()
                        break

                    for keyword in keywords:
                        if self._check_stop():
                            break
                        if self._check_daily_limit():
                            self._stop_event.set()
                            break
                        self._wait_pause()
                        if self._check_stop():
                            break

                        self._daily_search_count += 1

                        # Tüm modlarda sadece anahtar kelime aratılır
                        # İl/ilçe GPS lokasyonu ile belirlenir, Google konuma göre sonuç gösterir
                        search_query = keyword
                        display_city = city
                        self.stats["current_city"] = display_city
                        self.stats["current_keyword"] = keyword
                        self.stats["total_searches"] += 1
                        self.update_stats()

                        kw_type = "ORİJİNAL" if keyword.lower() in self._original_keywords else "TÜREV"
                        self.log(f"=== [{kw_type}] Aranıyor: '{search_query}' ===")

                        # New context per search for fingerprint rotation
                        ua = random.choice(USER_AGENTS)
                        vp = random.choice(VIEWPORT_SIZES)

                        context_opts = {
                            "user_agent": ua,
                            "viewport": vp,
                            "locale": "tr-TR",
                            "timezone_id": "Europe/Istanbul",
                            "permissions": ["geolocation"],
                        }
                        proxy_url = os.getenv("PROXY_URL") or self.settings.get("proxy")
                        if proxy_url:
                            from urllib.parse import urlparse
                            parsed = urlparse(proxy_url)
                            if parsed.username:
                                context_opts["proxy"] = {
                                    "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                                    "username": parsed.username,
                                    "password": parsed.password or "",
                                }
                            else:
                                context_opts["proxy"] = {"server": proxy_url}
                            self.log(f"🌐 Proxy aktif: {parsed.hostname}:{parsed.port}")

                        # GPS konum ayarla - ilçe/il GPS
                        geo = get_coordinates(city)
                        if geo:
                            context_opts["geolocation"] = geo
                            self.log(f"📍 Konum: {display_city} ({geo['latitude']:.4f}, {geo['longitude']:.4f})")

                        # Google cookie'lerini yeni context'e aktar
                        if hasattr(self, '_google_storage') and self._google_storage:
                            context_opts["storage_state"] = self._google_storage
                        context = browser.new_context(**context_opts)

                        # Anti-detection scripts (kapsamlı)
                        context.add_init_script("""
                            // webdriver flag'ini kaldır
                            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                            delete navigator.__proto__.webdriver;

                            // Gerçekçi plugin listesi
                            Object.defineProperty(navigator, 'plugins', {
                                get: () => {
                                    const plugins = [
                                        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
                                        {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
                                        {name: 'Native Client', filename: 'internal-nacl-plugin', description: ''},
                                    ];
                                    plugins.length = 3;
                                    return plugins;
                                }
                            });

                            // Gerçekçi languages
                            Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR', 'tr', 'en-US', 'en']});

                            // Chrome runtime
                            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};

                            // permissions query override
                            const origQuery = window.navigator.permissions.query;
                            window.navigator.permissions.query = (params) =>
                                params.name === 'notifications'
                                    ? Promise.resolve({state: Notification.permission})
                                    : origQuery(params);

                            // WebGL vendor/renderer
                            const getParameter = WebGLRenderingContext.prototype.getParameter;
                            WebGLRenderingContext.prototype.getParameter = function(param) {
                                if (param === 37445) return 'Intel Inc.';
                                if (param === 37446) return 'Intel Iris OpenGL Engine';
                                return getParameter.call(this, param);
                            };

                            // Platform
                            Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});

                            // hardwareConcurrency
                            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});

                            // deviceMemory
                            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});

                            // connection
                            Object.defineProperty(navigator, 'connection', {get: () => ({
                                effectiveType: '4g', rtt: 50, downlink: 10, saveData: false
                            })});
                        """)

                        page = context.new_page()
                        _stealth.apply_stealth_sync(page)  # Bot algılamayı atlatma

                        try:
                            all_ads_for_keyword = []
                            seen_urls = set()
                            captcha_hit = False
                            pages_to_scan = self.settings.get("pages_to_scan", 2)
                            scan_mode = self.settings.get("scan_mode", "power")

                            for page_num in range(1, pages_to_scan + 1):
                                if self._check_stop():
                                    break

                                start = (page_num - 1) * 10

                                self.log(f"--- Sayfa {page_num} yükleniyor ---")

                                if page_num == 1:
                                    # Insan gibi: google.com'a git, arama kutusuna yaz
                                    page.goto("https://www.google.com/?hl=tr&gl=tr", wait_until="domcontentloaded", timeout=60000)
                                    time.sleep(random.uniform(1.5, 3.0))
                                    # Arama kutusunu bul ve yaz
                                    search_box = page.locator('textarea[name="q"], input[name="q"]').first
                                    search_box.click()
                                    time.sleep(random.uniform(0.3, 0.8))
                                    # Harfleri tek tek yaz (insan gibi)
                                    for char in search_query:
                                        search_box.type(char, delay=random.randint(50, 150))
                                    time.sleep(random.uniform(0.5, 1.2))
                                    search_box.press("Enter")
                                    page.wait_for_load_state("domcontentloaded", timeout=60000)
                                    time.sleep(random.uniform(1.5, 3.0))
                                else:
                                    # Sonraki sayfalar icin URL ile git
                                    search_url = (
                                        f"https://www.google.com/search"
                                        f"?q={search_query.replace(' ', '+')}"
                                        f"&hl=tr&gl=tr&start={start}"
                                    )
                                    page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                                    time.sleep(random.uniform(1.5, 3.0))

                                if page_num == 1:
                                    self._close_cookie_banner(page)

                                # CAPTCHA check
                                if self._check_captcha(page):
                                    # Önce AI ile çözmeyi dene
                                    if (os.getenv("OPENAI_API_KEY") or self.settings.get("openai_api_key")) and self._solve_captcha(page):
                                        self._consecutive_captchas = 0
                                        self.log("CAPTCHA aşıldı, taramaya devam ediliyor.", "success")
                                        continue  # Aynı sayfayı tekrar tara

                                    # Çözülemediyse bekleme moduna geç
                                    self.stats["captcha_count"] += 1
                                    wait = self._captcha_backoff
                                    self.log(f"CAPTCHA tespit edildi! {wait}s bekleniyor (artan bekleme)...", "error")
                                    self._captcha_backoff = min(self._captcha_backoff * 1.5, 300)
                                    self.update_stats()
                                    captcha_hit = True
                                    if self._handle_captcha_streak():
                                        break
                                    break

                                # CAPTCHA yok = streak sifirla
                                self._consecutive_captchas = 0

                                # Sayfanin tamamini scroll et
                                self._human_mouse_move(page)
                                time.sleep(random.uniform(1, 2))
                                self._scroll_full_page(page)

                                # SEO modu: hedef domain varsa özel akış
                                if scan_mode == "organic" and self.settings.get("target_domains") and page_num == 1:
                                    self._seo_search_and_click(page, context, keyword, display_city, search_query)
                                    break  # Bu anahtar kelime için tamamlandı

                                # Tarama moduna gore sonuclari topla
                                page_results = []

                                if scan_mode in ("ads", "power"):
                                    ads = self._find_ads(page)
                                    page_results.extend(ads)

                                if scan_mode in ("organic", "power"):
                                    organic = self._find_organic_results(page)
                                    page_results.extend(organic)

                                # Tekrar URL filtrele
                                new_results = []
                                for item in page_results:
                                    if item["url"] not in seen_urls:
                                        seen_urls.add(item["url"])
                                        new_results.append(item)

                                if new_results:
                                    ad_count = sum(1 for r in new_results if r.get("zone") != "Organik")
                                    org_count = sum(1 for r in new_results if r.get("zone") == "Organik")
                                    parts = []
                                    if ad_count: parts.append(f"{ad_count} reklam")
                                    if org_count: parts.append(f"{org_count} organik")
                                    self.log(f"Sayfa {page_num}: {' + '.join(parts)} bulundu")
                                    all_ads_for_keyword.extend(new_results)
                                else:
                                    self.log(f"Sayfa {page_num}: Sonuç bulunamadı")

                                # Sayfalar arasi bekleme
                                if page_num < pages_to_scan:
                                    self._human_delay(3, 7)

                            if captcha_hit:
                                context.close()
                                wait = self._captcha_backoff // 2
                                self._human_delay(wait, wait + 30)
                                continue

                            # CAPTCHA backoff reset
                            self._captcha_backoff = 30

                            # Istatistik guncelle
                            self.stats["total_ads_found"] += len(all_ads_for_keyword)
                            self.update_stats()

                            if not all_ads_for_keyword:
                                self.log("Hiç sonuç bulunamadı (tüm sayfalarda).")
                                context.close()
                                self._human_delay()
                                continue

                            mode_label = {"ads": "Reklam", "organic": "Organik", "power": "Power"}.get(scan_mode, "Power")
                            self.log(f"TOPLAM {len(all_ads_for_keyword)} sonuç ({mode_label} mod, {pages_to_scan} sayfa) - hepsine tıklanacak.")

                            # Tum reklamlara tikla
                            for idx, ad in enumerate(all_ads_for_keyword):
                                if self._check_stop():
                                    break
                                self._wait_pause()
                                if self._check_stop():
                                    break

                                zone = ad.get("zone", "")
                                self.log(f"[{idx+1}/{len(all_ads_for_keyword)}] [{zone}] Tıklanıyor...")
                                self._click_ad(page, context, ad, keyword, display_city)

                                # Tiklamalar arasi bekleme
                                if idx < len(all_ads_for_keyword) - 1:
                                    self._human_delay(
                                        self.settings["click_delay_min"],
                                        self.settings["click_delay_max"],
                                    )

                        except Exception as e:
                            self.log(f"Arama hatası: {e}", "error")
                        finally:
                            context.close()

                        # Aramalar arasi bekleme (akilli gecikme - arama sayisi arttikca bekleme artar)
                        if not self._check_stop():
                            self._smart_delay()

                browser.close()

        except Exception as e:
            self.log(f"Kritik hata: {e}", "error")
        finally:
            self.running = False
            self.stats["status"] = "idle"
            self.stats["current_keyword"] = ""
            self.stats["current_city"] = ""
            self.update_stats()
            self.log("Bot tamamlandı.")
            if self.email_reporter._enabled:
                if self.email_reporter.send_report(self.stats, self.click_history):
                    self.log("Özet rapor e-posta ile gönderildi.", "success")
                else:
                    self.log("E-posta raporu gönderilemedi.", "error")
