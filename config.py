import os
import json
from dotenv import load_dotenv

load_dotenv()

# Google Sheets
GOOGLE_SHEET_URL = os.getenv(
    "GOOGLE_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/11vSrTS4d7Z4x_6z-v5WOFahlkklqPKBvYlB40oeANgM/edit"
)
SHEET_NAME = "Scanner"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "credentials", "service_account.json")


def get_google_credentials(scopes):
    """Google credentials olustur - env variable (base64) veya dosyadan."""
    import base64
    from google.oauth2.service_account import Credentials

    # Base64 formatini dene (Railway icin onerilen yontem - ozel karakter sorunu yok)
    sa_b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_B64", "").strip()
    if sa_b64:
        # Eksik padding'i tamamla
        sa_b64 += "=" * (-len(sa_b64) % 4)
        sa_info = json.loads(base64.b64decode(sa_b64).decode("utf-8"))
        return Credentials.from_service_account_info(sa_info, scopes=scopes)

    # Eski JSON formatini dene
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        sa_info = json.loads(sa_json)
        return Credentials.from_service_account_info(sa_info, scopes=scopes)

    return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)

# Tarama ayarlari
MIN_RESULTS = 20
REQUEST_TIMEOUT = 10
SCROLL_PAUSE = 1.5
CLICK_DELAY_MIN = 1.0
CLICK_DELAY_MAX = 3.0
MAX_SCROLL_RETRIES = 5  # Yeni sonuc gelmezse kac scroll daha denenecek
HEADLESS = True

# Website tarama ayarlari
WEBSITE_TIMEOUT = 10
WEBSITE_DELAY_MIN = 0.5
WEBSITE_DELAY_MAX = 1.5

# Engellenen e-posta domainleri (kisisel, devlet, universite, AVM)
BLOCKED_EMAIL_DOMAINS = {
    # Kisisel
    "gmail.com", "googlemail.com",
    "hotmail.com", "hotmail.com.tr",
    "outlook.com", "outlook.com.tr",
    "live.com", "live.com.tr",
    "yahoo.com", "yahoo.com.tr",
    "yandex.com", "yandex.com.tr",
    "icloud.com", "me.com", "mac.com",
    "msn.com", "aol.com",
    "mail.com", "protonmail.com", "proton.me",
    "zoho.com",
}

# Engellenen domain desenleri (suffix kontrolu)
BLOCKED_DOMAIN_SUFFIXES = [
    ".gov.tr", ".edu.tr", ".mil.tr",
    ".gov", ".edu", ".mil",
    ".k12.tr",
]

# Engellenen domain anahtar kelimeleri
BLOCKED_DOMAIN_KEYWORDS = [
    "avm", "mall", "shoppingcenter",
]

# Atlanacak e-posta onekleri
BLOCKED_EMAIL_PREFIXES = [
    "noreply", "no-reply", "no_reply",
    "mailer-daemon", "postmaster",
    "abuse", "spam",
]

# Website'de kontrol edilecek sayfalar (e-posta bulmak icin)
CONTACT_PAGES = [
    "/iletisim",
    "/contact",
    "/contact-us",
    "/bize-ulasin",
    "/hakkimizda",
    "/about",
    "/about-us",
]

# E-posta ayarlari (Resend API)
FROM_NAME = os.getenv("FROM_NAME", "YO Dijital")
FROM_EMAIL = os.getenv("FROM_EMAIL", "info@yodijital.com")
EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", "Is Birligi Teklifi")
EMAIL_TEMPLATE_FILE = os.getenv("EMAIL_TEMPLATE_FILE", "email_template.html")
EMAIL_SEND_DELAY = 2  # saniye

# User Agent listesi
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Sütun basliklari
SHEET_COLUMNS = ["Tarih", "Sektör", "Firma Adı", "Telefon", "E-posta", "Domain", "Web Sitesi", "Instagram", "Facebook", "LinkedIn"]
