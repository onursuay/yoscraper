import os
import time
import logging

from config import (
    FROM_NAME, FROM_EMAIL, EMAIL_SUBJECT, EMAIL_TEMPLATE_FILE,
    EMAIL_SEND_DELAY,
)

logger = logging.getLogger(__name__)


class EmailSender:
    """Resend API ile pazarlama e-postasi gonderici."""

    def __init__(self):
        self.template = self._load_template()
        self.api_key = os.getenv("RESEND_API_KEY", "")

    def _load_template(self) -> str:
        """E-posta sablonunu yukle."""
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), EMAIL_TEMPLATE_FILE)
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            logger.warning(
                f"E-posta sablonu bulunamadi: {template_path}\n"
                "Varsayilan sablon kullanilacak."
            )
            return self._default_template()

    @staticmethod
    def _default_template() -> str:
        return """
<html>
<body>
<p>Sayın Yetkili,</p>

<p>Firmanızla iş birliği yapmak istiyoruz. Sizinle detayları görüşmek için
uygun bir zamanda iletişime geçebilir misiniz?</p>

<p>Saygılarımızla,<br>
{from_name}</p>
</body>
</html>
""".strip()

    def send_emails(self, businesses: list[dict]) -> dict:
        """Isletmelere Resend API ile pazarlama e-postasi gonder.

        Args:
            businesses: [{"name": str, "email": str, "domain": str}, ...]

        Returns:
            {"sent": int, "failed": int, "errors": list}
        """
        if not self.api_key:
            logger.error("RESEND_API_KEY ayarlanmamis! .env dosyasini kontrol edin.")
            return {"sent": 0, "failed": len(businesses), "errors": ["RESEND_API_KEY ayarlanmamis"]}

        import requests
        import json as _json
        from urllib.parse import quote

        from_name = FROM_NAME or "YO Dijital"
        from_email = FROM_EMAIL or "info@yodijital.com"

        # Abonelikten cikanlar listesi (Supabase)
        unsubscribed = set()
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_ANON_KEY", "")

        if supabase_url and supabase_key:
            try:
                r = requests.get(
                    f"{supabase_url}/rest/v1/unsubscribed?select=email",
                    headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                    timeout=5,
                )
                if r.status_code == 200:
                    unsubscribed = {item["email"] for item in r.json()}
                    logger.info(f"  Supabase: {len(unsubscribed)} abonelikten cikmis email yuklendi")
            except Exception as e:
                logger.warning(f"  Supabase baglanti hatasi: {e}")

        # Base URL
        base_url = os.getenv("APP_BASE_URL", "https://yodijital.com")

        result = {"sent": 0, "failed": 0, "skipped": 0, "errors": []}

        for biz in businesses:
            try:
                email = biz["email"]

                # Abonelikten cikanları atla
                if email.lower().strip() in unsubscribed:
                    result["skipped"] += 1
                    logger.info(f"  Atlandi (abonelikten cikmis): {email}")
                    continue

                name = biz.get("name", "Yetkili")

                # Unsubscribe URL olustur
                unsub_url = f"{base_url}/unsubscribe?email={quote(email)}"

                # Sablonda degiskenleri degistir
                body = self.template.replace("{firma_adi}", name)
                body = body.replace("{from_name}", from_name)
                body = body.replace("{email}", email)
                body = body.replace("{sektor}", biz.get("sector", ""))
                body = body.replace("{sehir}", biz.get("city", ""))
                body = body.replace("{unsubscribe_url}", unsub_url)

                resp = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": f"{from_name} <{from_email}>",
                        "to": [email],
                        "reply_to": [from_email],
                        "subject": EMAIL_SUBJECT,
                        "html": body,
                        "headers": {
                            "List-Unsubscribe": f"<{unsub_url}>",
                            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                        },
                    },
                    timeout=15,
                )

                if resp.status_code == 200:
                    result["sent"] += 1
                    logger.info(f"  Gonderildi: {email}")
                else:
                    error_msg = resp.json().get("message", resp.text)
                    result["failed"] += 1
                    result["errors"].append(f"{email}: {error_msg}")
                    logger.warning(f"  Gonderilemedi {email}: {error_msg}")

                time.sleep(EMAIL_SEND_DELAY)

            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"{biz.get('email', '?')}: {e}")
                logger.warning(f"  Gonderilemedi {biz.get('email', '?')}: {e}")

        return result

    @staticmethod
    def display_summary(businesses: list[dict]):
        """Bulunan isletmelerin ozetini goster."""
        if not businesses:
            print("\nHicbir isletme bulunamadi.")
            return

        print(f"\n{'='*80}")
        print(f"{'BULUNAN ISLETMELER':^80}")
        print(f"{'='*80}")
        print(f"{'#':<4} {'Firma Adı':<25} {'E-posta':<30} {'Domain':<20}")
        print(f"{'-'*80}")

        for i, biz in enumerate(businesses, 1):
            print(
                f"{i:<4} {biz['name'][:24]:<25} {biz['email'][:29]:<30} {biz['domain'][:19]:<20}"
            )

        print(f"{'-'*80}")
        print(f"Toplam: {len(businesses)} isletme")
        print(f"{'='*80}")

    @staticmethod
    def ask_approval(businesses: list[dict]) -> bool:
        """Kullanicidan e-posta gonderim onayi al."""
        EmailSender.display_summary(businesses)
        print(f"\nBu {len(businesses)} isletmeye pazarlama e-postasi gonderilsin mi?")
        answer = input("(evet/hayir): ").strip().lower()
        return answer in ("evet", "e", "yes", "y")
