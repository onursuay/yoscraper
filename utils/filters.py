import tldextract
from config import (
    BLOCKED_EMAIL_DOMAINS,
    BLOCKED_DOMAIN_SUFFIXES,
    BLOCKED_DOMAIN_KEYWORDS,
    BLOCKED_EMAIL_PREFIXES,
    BLOCKED_WEBSITE_DOMAINS,
)


def is_valid_corporate_email(email: str) -> bool:
    """Kurumsal e-posta mi kontrol et. Gmail, Hotmail, devlet, universite, AVM vb. filtrele."""
    if not email or "@" not in email:
        return False

    email = email.lower().strip()
    local_part, domain = email.split("@", 1)

    # Engellenen onekler (noreply, spam vb.)
    for prefix in BLOCKED_EMAIL_PREFIXES:
        if local_part.startswith(prefix):
            return False

    # Engellenen domainler (gmail, hotmail vb.)
    if domain in BLOCKED_EMAIL_DOMAINS:
        return False

    # Engellenen domain son ekleri (.gov.tr, .edu.tr vb.)
    for suffix in BLOCKED_DOMAIN_SUFFIXES:
        if domain.endswith(suffix):
            return False

    # Engellenen anahtar kelimeler (avm vb.)
    extracted = tldextract.extract(domain)
    domain_name = extracted.domain.lower()
    for keyword in BLOCKED_DOMAIN_KEYWORDS:
        if keyword in domain_name:
            return False

    return True


def extract_domain_from_url(url: str) -> str:
    """URL'den ana domaini cikar (ornek: www.firma.com.tr -> firma.com.tr)."""
    extracted = tldextract.extract(url)
    if extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return extracted.domain


def is_aggregator_website(url: str) -> bool:
    """URL bir aggregator / pazaryeri / sosyal medya sitesi mi?

    Google Places "website" alaninda isletmenin kendi sitesi yerine
    sahibinden.com, instagram.com gibi adresler donebiliyor. Bunlar gercek
    isletme sitesi degildir - e-posta cikarmaya calismak copyem lead uretir.
    """
    if not url:
        return False
    domain = extract_domain_from_url(url).lower().strip()
    if not domain:
        return False
    return domain in BLOCKED_WEBSITE_DOMAINS
