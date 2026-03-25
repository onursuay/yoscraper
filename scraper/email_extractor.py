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
    CONTACT_PAGES, USER_AGENTS,
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

    def extract_emails_from_url(self, url: str) -> list:
        """Verilen URL'den kurumsal e-posta adreslerini cikar.

        3 asamali strateji:
        1. Web sitesinden cikar (requests - hizli)
        2. Web sitesinden cikar (Playwright - JS render)
        3. Domain'den tahmin et (MX kaydi kontrolu ile)
        """
        if not url:
            return []

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # 1. Requests ile dene (hizli yol)
        emails = self._extract_with_requests(url)
        if emails:
            return emails

        # 2. Domain'den standart e-posta tahmin et (MX kontrolu ile)
        emails = self._guess_email_from_domain(url)
        return emails

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

    def _extract_with_requests(self, url: str) -> list:
        """Requests + BeautifulSoup ile e-posta cikar (statik HTML)."""
        found_emails = set()

        # Ana sayfa
        emails = self._scrape_page_requests(url)
        found_emails.update(emails)

        corporate = [e for e in found_emails if is_valid_corporate_email(e)]
        if corporate:
            return corporate

        # Iletisim sayfalari
        for page_path in CONTACT_PAGES[:4]:  # Ilk 4 sayfayi dene
            try:
                page_url = urljoin(url.rstrip("/") + "/", page_path.lstrip("/"))
                emails = self._scrape_page_requests(page_url)
                found_emails.update(emails)
                corporate = [e for e in found_emails if is_valid_corporate_email(e)]
                if corporate:
                    return corporate
            except Exception:
                continue

        return [e for e in found_emails if is_valid_corporate_email(e)]

    def _scrape_page_requests(self, url: str) -> set:
        """Requests ile tek bir sayfadan e-posta cikar."""
        emails = set()
        try:
            response = self.session.get(url, timeout=WEBSITE_TIMEOUT, verify=False)
            if response.status_code != 200:
                return emails
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return emails
            return self._extract_emails_from_html(response.text)
        except Exception:
            return emails

    def _extract_emails_from_html(self, html: str) -> set:
        """HTML iceriginden e-posta adreslerini cikar."""
        emails = set()

        # Regex ile bul
        raw_emails = EMAIL_REGEX.findall(html)

        # mailto: linklerinden de cikar
        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if email:
                    raw_emails.append(email)

        # Filtrele
        for email in raw_emails:
            email = email.lower().strip().rstrip(".")
            if any(email.endswith(ext) for ext in INVALID_EXTENSIONS):
                continue
            if self._is_plausible_email(email):
                emails.add(email)

        return emails

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
        if not email or "@" not in email:
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
