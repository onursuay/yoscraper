import re
import random
import logging
import time
from urllib.parse import urljoin

import requests
import dns.resolver
from bs4 import BeautifulSoup

from config import (
    WEBSITE_TIMEOUT, WEBSITE_DELAY_MIN, WEBSITE_DELAY_MAX,
    CONTACT_PAGES, USER_AGENTS, FIRECRAWL_API_KEY,
)
from utils.filters import is_valid_corporate_email, extract_domain_from_url

logger = logging.getLogger(__name__)

# E-posta regex deseni
EMAIL_REGEX = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

# Gecersiz uzantilar
INVALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".zip", ".css", ".js"}

# Gurultu e-posta domainleri (analitik/takip/placeholder - gercek mail degil)
NOISE_EMAIL_DOMAINS = {
    "sentry.wixpress.com", "sentry-next.wixpress.com", "sentry.io",
    "mhtml.blink", "wix.com", "wixpress.com",
    "example.com", "example.org", "example.net", "domain.com",
    "yourdomain.com", "yourcompany.com", "email.com", "test.com",
    "sentry.local", "godaddy.com", "wordpress.com", "wp.com",
}
# Gurultu domain son ekleri
NOISE_TLD_SUFFIXES = (".blink", ".local", ".invalid", ".test", ".example")
# Takip ID'si gibi gorunen local part (uzun hex dizisi)
_HEX_RUN_RE = re.compile(r"[0-9a-f]{20,}", re.IGNORECASE)

# Iletisim sayfasi linklerini tespit icin anahtar kelimeler
CONTACT_LINK_KEYWORDS = [
    "iletisim", "iletişim", "contact", "bize-ulas", "bizeulas",
    "ulasin", "ulaşın", "hakkimizda", "hakkımızda", "about", "kurumsal",
]

# Bracket'li obfuscation: "info [at] firma [dot] com" -> "info@firma.com"
_OBF_AT = re.compile(r"\s*[\[\(]\s*at\s*[\]\)]\s*", re.IGNORECASE)
_OBF_DOT = re.compile(r"\s*[\[\(]\s*(?:dot|nokta)\s*[\]\)]\s*", re.IGNORECASE)


def decode_cfemail(hex_str: str) -> str:
    """Cloudflare email-protection hex stringini coz (XOR ilk byte = anahtar)."""
    try:
        data = bytes.fromhex(hex_str.strip())
        if len(data) < 2:
            return ""
        key = data[0]
        return "".join(chr(b ^ key) for b in data[1:])
    except (ValueError, IndexError):
        return ""


class EmailExtractor:
    """Web sitelerinden kurumsal e-posta adresi cikaran sinif.

    Requests + BeautifulSoup ile statik HTML'den e-posta cikarir.
    Bulamazsa domain MX kaydi ile tahmin eder.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        })
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def close(self):
        """Oturumu kapat."""
        self.session.close()

    # Standart kurumsal e-posta onekleri
    COMMON_PREFIXES = ["info", "iletisim", "bilgi", "contact", "admin", "destek", "satis", "hizmet"]

    @staticmethod
    def _classify(email: str) -> str:
        """E-posta tipini belirle: kurumsal mi kisisel mi."""
        return "kurumsal" if is_valid_corporate_email(email) else "kişisel"

    @staticmethod
    def _best_emails(emails: set) -> list:
        """E-postalari oncelige gore sirala: once kurumsal, sonra kisisel."""
        corporate = sorted(e for e in emails if is_valid_corporate_email(e))
        personal = sorted(e for e in emails if not is_valid_corporate_email(e))
        return corporate + personal

    def extract_contact_email(self, url: str) -> dict:
        """Verilen URL'den en iyi iletisim e-postasini ve TIPINI cikar.

        Strateji (kurumsal > kisisel > tahmin):
        1. Requests ile sitedeki TUM gercek e-postalari topla (kurumsal+kisisel)
        2. Bulamazsa Firecrawl (JS render, CAPTCHA/Cloudflare bypass)
        3. Hala yoksa domain MX kaydindan info@domain tahmin et

        Returns:
            {"email": str, "type": "kurumsal"|"kişisel"|"tahmin"|"", "all": list}
        """
        empty = {"email": "", "type": "", "all": []}
        if not url:
            return empty
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # 1. Requests (hizli yol) - tum gercek e-postalari topla
        found = self._collect_emails_requests(url)

        # 2. Requests'te KURUMSAL yoksa Firecrawl dene (JS/Cloudflare siteleri)
        if FIRECRAWL_API_KEY and not any(is_valid_corporate_email(e) for e in found):
            fc = self._collect_emails_firecrawl(url)
            if fc:
                found |= fc

        if found:
            ordered = self._best_emails(found)
            best = ordered[0]
            return {"email": best, "type": self._classify(best), "all": ordered}

        # 3. Son care: domain MX kaydindan tahmin (dusuk kalite)
        guessed = self._guess_email_from_domain(url)
        if guessed:
            return {"email": guessed[0], "type": "tahmin", "all": guessed}

        return empty

    def extract_emails_from_url(self, url: str) -> list:
        """Geriye donuk uyumluluk: e-posta listesini dondur (en iyi ilk sirada)."""
        return self.extract_contact_email(url)["all"]

    def _collect_emails_firecrawl(self, url: str) -> set:
        """Firecrawl API (v4) ile sitedeki tum e-postalari topla.

        Ana sayfayi tarar, oradaki iletisim linklerini takip eder.
        Kurumsal e-posta bulununca erken durur.
        """
        try:
            from firecrawl import Firecrawl
            app = Firecrawl(api_key=FIRECRAWL_API_KEY)
        except ImportError:
            logger.warning("firecrawl-py yuklu degil: pip install firecrawl-py")
            return set()

        def _scrape(u: str):
            try:
                doc = app.scrape(u, formats=["html"], timeout=30000)
                return getattr(doc, "html", None) or (doc.get("html") if isinstance(doc, dict) else None)
            except Exception as e:
                logger.debug(f"  Firecrawl hata ({u}): {e}")
                return None

        found = set()
        home_html = _scrape(url)
        if home_html:
            found |= self._extract_emails_from_html(home_html)
            if any(is_valid_corporate_email(e) for e in found):
                logger.info(f"  Firecrawl ile kurumsal e-posta bulundu: {url}")
                return found

        for page_url in self._discover_contact_pages(url, home_html)[:3]:
            html = _scrape(page_url)
            if html:
                found |= self._extract_emails_from_html(html)
                if any(is_valid_corporate_email(e) for e in found):
                    logger.info(f"  Firecrawl ile kurumsal e-posta bulundu: {page_url}")
                    return found

        return found

    def _guess_email_from_domain(self, url: str) -> list:
        """Domain'in MX kaydi varsa standart e-posta adresleri olustur.

        ornek: dilasayan.com -> MX kaydi var -> info@dilasayan.com
        """
        domain = extract_domain_from_url(url)
        if not domain:
            return []

        # MX kaydi kontrol et
        if not self._has_mx_record(domain):
            logger.debug(f"{domain}: MX kaydi yok, e-posta tahmini atlanıyor.")
            return []

        # Standart oneklerle e-posta olustur
        for prefix in self.COMMON_PREFIXES:
            email = f"{prefix}@{domain}"
            if is_valid_corporate_email(email):
                logger.info(f"  MX dogrulandi, tahmin edilen e-posta: {email}")
                return [email]

        return []

    @staticmethod
    def _has_mx_record(domain: str) -> bool:
        """Domain'in MX (mail exchange) kaydi var mi kontrol et."""
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=5)
            return len(answers) > 0
        except Exception:
            return False

    def _collect_emails_requests(self, url: str) -> set:
        """Requests + BeautifulSoup ile sitedeki TUM gercek e-postalari topla.

        Ana sayfayi cektikten sonra oradaki gercek "Iletisim" linklerini
        takip eder (sabit liste sadece yedek). Kurumsal bulununca erken durur.
        """
        found = set()

        # Ana sayfa
        home_html = self._get_html(url)
        if home_html:
            found |= self._extract_emails_from_html(home_html)
            if any(is_valid_corporate_email(e) for e in found):
                return found

        # Iletisim/hakkimizda sayfalari (once sayfadaki gercek linkler)
        for page_url in self._discover_contact_pages(url, home_html):
            html = self._get_html(page_url)
            if html:
                found |= self._extract_emails_from_html(html)
                if any(is_valid_corporate_email(e) for e in found):
                    return found

        return found

    def _discover_contact_pages(self, base_url: str, home_html: str) -> list:
        """Iletisim sayfasi URL'lerini bul: once ana sayfadaki gercek linkler,
        sonra sabit yedek listesi (config.CONTACT_PAGES)."""
        urls = []
        seen = set()
        base = base_url.rstrip("/") + "/"

        # 1. Ana sayfadaki gercek iletisim linklerini takip et
        if home_html:
            try:
                soup = BeautifulSoup(home_html, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    text = (a_tag.get_text() or "").lower()
                    hl = href.lower()
                    if any(k in hl or k in text for k in CONTACT_LINK_KEYWORDS):
                        full = urljoin(base, href)
                        if full.startswith(("http://", "https://")) and full not in seen:
                            seen.add(full)
                            urls.append(full)
            except Exception:
                pass

        # 2. Sabit yedek liste
        for page_path in CONTACT_PAGES:
            full = urljoin(base, page_path.lstrip("/"))
            if full not in seen:
                seen.add(full)
                urls.append(full)

        return urls[:8]  # Asiri sayfa cekmeyi sinirlandir

    def _get_html(self, url: str) -> str:
        """Requests ile tek bir sayfanin HTML'ini getir (yoksa bos string)."""
        try:
            response = self.session.get(url, timeout=WEBSITE_TIMEOUT, verify=False)
            if response.status_code != 200:
                return ""
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ""
            return response.text or ""
        except Exception:
            return ""

    def _extract_emails_from_html(self, html: str) -> set:
        """HTML iceriginden e-posta adreslerini cikar.

        Kaynaklar: duz metin regex, mailto: linkleri, Cloudflare
        email-protection (data-cfemail) decode ve bracket'li obfuscation
        ("info [at] firma [dot] com").
        """
        emails = set()
        if not html:
            return emails

        # 1. Bracket'li obfuscation'i once cozup duz metin regex calistir
        deobf = _OBF_DOT.sub(".", _OBF_AT.sub("@", html))
        raw_emails = EMAIL_REGEX.findall(deobf)

        soup = BeautifulSoup(html, "html.parser")

        # 2. mailto: linklerinden cikar
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if email:
                    raw_emails.append(email)

        # 3. Cloudflare email-protection decode
        #    a) data-cfemail attribute'lu elementler
        for el in soup.select("[data-cfemail]"):
            decoded = decode_cfemail(el.get("data-cfemail", ""))
            if decoded:
                raw_emails.append(decoded)
        #    b) /cdn-cgi/l/email-protection#<hex> linkleri
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/cdn-cgi/l/email-protection#" in href:
                decoded = decode_cfemail(href.split("#", 1)[1])
                if decoded:
                    raw_emails.append(decoded)

        # Filtrele
        for email in raw_emails:
            email = email.lower().strip().rstrip(".")
            # Bozuk lider/artik "@" temizle (or. "@info@x.com" -> "info@x.com")
            email = email.strip("@")
            # E-posta domaininde gereksiz "www." onekini temizle (info@www.x.com -> info@x.com)
            if "@www." in email:
                email = email.replace("@www.", "@", 1)
            # Tam olarak tek "@" olmali (cift @ = bozuk)
            if email.count("@") != 1:
                continue
            if any(email.endswith(ext) for ext in INVALID_EXTENSIONS):
                continue
            if self._is_noise_email(email):
                continue
            if self._is_plausible_email(email):
                emails.add(email)

        return emails

    @staticmethod
    def _is_noise_email(email: str) -> bool:
        """Analitik/takip/placeholder e-postalarini ele (sentry, mhtml, example vb.)."""
        if "@" not in email:
            return True
        local, domain = email.rsplit("@", 1)
        if domain in NOISE_EMAIL_DOMAINS:
            return True
        if domain.endswith(NOISE_TLD_SUFFIXES):
            return True
        # Takip ID'si gibi uzun hex local part (or. 2062d0a4...@..., frame-0a2d...@...)
        if _HEX_RUN_RE.search(local):
            return True
        return False

    def extract_site_title(self, url: str) -> str:
        """Web sitesinin <title> etiketinden firma adini cikar."""
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            response = self.session.get(url, timeout=WEBSITE_TIMEOUT, verify=False)
            if response.status_code != 200:
                return ""

            soup = BeautifulSoup(response.text, "html.parser")
            title_tag = soup.find("title")
            if not title_tag or not title_tag.string:
                return ""

            title = title_tag.string.strip()
            for sep in ["|", " - ", " – ", " — ", " :: ", " // ", " » "]:
                if sep in title:
                    title = title.split(sep)[0].strip()
                    break

            if len(title) < 2 or len(title) > 80:
                return ""

            skip_words = ["ana sayfa", "anasayfa", "home", "hoşgeldiniz", "hosgeldiniz", "welcome"]
            if title.lower() in skip_words:
                return ""

            return title

        except Exception:
            return ""

    def extract_social_links(self, url: str) -> dict:
        """Web sitesinden Instagram, Facebook ve LinkedIn linklerini cikar."""
        result = {"instagram": "", "facebook": "", "linkedin": ""}
        if not url:
            return result
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            response = self.session.get(url, timeout=WEBSITE_TIMEOUT, verify=False)
            if response.status_code != 200:
                return result

            soup = BeautifulSoup(response.text, "html.parser")

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                href_lower = href.lower()

                # Instagram
                if not result["instagram"] and "instagram.com/" in href_lower:
                    if "/p/" not in href_lower and "/reel/" not in href_lower:
                        result["instagram"] = href.rstrip("/")

                # Facebook
                if not result["facebook"] and ("facebook.com/" in href_lower or "fb.com/" in href_lower):
                    if "/sharer" not in href_lower and "/share" not in href_lower:
                        result["facebook"] = href.rstrip("/")

                # LinkedIn
                if not result["linkedin"] and "linkedin.com/" in href_lower:
                    if "/share" not in href_lower:
                        result["linkedin"] = href.rstrip("/")

                if result["instagram"] and result["facebook"] and result["linkedin"]:
                    break

        except Exception:
            pass

        return result

    @staticmethod
    def _is_plausible_email(email: str) -> bool:
        """E-posta adresinin makul olup olmadigini kontrol et."""
        if not email or email.count("@") != 1:
            return False
        local, domain = email.rsplit("@", 1)
        if not local or not domain:
            return False
        if "." not in domain:
            return False
        if len(local) > 64 or len(domain) > 253:
            return False
        parts = domain.split(".")
        if any(len(p) < 2 for p in parts):
            return False
        return True
