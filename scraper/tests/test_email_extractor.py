"""E-posta cikarma mantigi icin regresyon testleri (ag gerektirmez).

Kapsam: Cloudflare data-cfemail decode, bracket'li obfuscation, gurultu
(sentry/mhtml/takip ID) filtresi, bozuk "@" normalizasyonu, kurumsal/kisisel
tip siniflandirmasi ve aggregator/sosyal site filtresi.
"""
from scraper.email_extractor import EmailExtractor, decode_cfemail
from utils.filters import is_aggregator_website


def _cf_encode(email: str, key: int = 0x7a) -> str:
    out = f"{key:02x}"
    for c in email:
        out += f"{ord(c) ^ key:02x}"
    return out


def test_cfemail_roundtrip():
    enc = _cf_encode("info@firma.com.tr")
    assert decode_cfemail(enc) == "info@firma.com.tr"


def test_cfemail_from_html_attribute():
    ex = EmailExtractor()
    enc = _cf_encode("info@firma.com.tr")
    html = f'<a class="__cf_email__" data-cfemail="{enc}">[email protected]</a>'
    assert "info@firma.com.tr" in ex._extract_emails_from_html(html)


def test_cfemail_from_cdn_cgi_link():
    ex = EmailExtractor()
    enc = _cf_encode("info@firma.com.tr")
    html = f'<a href="/cdn-cgi/l/email-protection#{enc}">mail</a>'
    assert "info@firma.com.tr" in ex._extract_emails_from_html(html)


def test_bracket_obfuscation():
    ex = EmailExtractor()
    assert "info@guzelkuafor.com" in ex._extract_emails_from_html(
        "info [at] guzelkuafor [dot] com"
    )
    assert "satis@firma.com.tr" in ex._extract_emails_from_html(
        "satis (at) firma (dot) com.tr"
    )


def test_mailto_and_plaintext():
    ex = EmailExtractor()
    out = ex._extract_emails_from_html(
        '<a href="mailto:bilgi@xyz.com">m</a> ayrıca destek@xyz.com'
    )
    assert {"bilgi@xyz.com", "destek@xyz.com"} <= out


def test_noise_filter():
    ex = EmailExtractor()
    out = ex._extract_emails_from_html(
        "<p>2062d0a4929b45348643784b5cb39c36@sentry.wixpress.com</p>"
        "<p>frame-0a2d5dc05b8a0b70498426457e6854f5@mhtml.blink</p>"
        "<p>destek@example.com</p>"
        "<p>gercek@firma.com.tr</p>"
    )
    assert not any("sentry" in e for e in out)
    assert not any("mhtml" in e for e in out)
    assert "destek@example.com" not in out
    assert "gercek@firma.com.tr" in out


def test_www_and_at_normalization():
    ex = EmailExtractor()
    out = ex._extract_emails_from_html(
        '<a href="mailto:info@www.gercek.com">x</a>'
        "<p>@info@emlakyap.com</p><p>x@y@z.com</p>"
    )
    assert "info@gercek.com" in out
    assert "info@www.gercek.com" not in out
    assert "info@emlakyap.com" in out
    assert "x@y@z.com" not in out


def test_classify_and_ordering():
    ex = EmailExtractor()
    assert ex._classify("info@firma.com.tr") == "kurumsal"
    assert ex._classify("firma@gmail.com") == "kişisel"
    best = ex._best_emails({"kisi@gmail.com", "info@firma.com", "x@hotmail.com"})
    assert best[0] == "info@firma.com"


def test_aggregator_filter():
    assert is_aggregator_website("https://www.sahibinden.com/ilan/123")
    assert is_aggregator_website("https://instagram.com/firma")
    assert is_aggregator_website("http://facebook.com/firma")
    assert not is_aggregator_website("https://www.gercekfirma.com.tr")
    assert not is_aggregator_website("")
