import os
import json
import logging
import tempfile

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_URL, SHEET_NAME, SERVICE_ACCOUNT_FILE, SHEET_COLUMNS

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsManager:
    """Google Sheets entegrasyonu - veri yazma ve mukerrer kontrol."""

    def __init__(self):
        self.worksheet = None
        self.existing_domains = set()
        self._connect()

    def _connect(self):
        """Google Sheets'e baglan."""
        try:
            from config import get_google_credentials
            creds = get_google_credentials(SCOPES)
            client = gspread.authorize(creds)

            spreadsheet = client.open_by_url(GOOGLE_SHEET_URL)
            self.worksheet = spreadsheet.worksheet(SHEET_NAME)

            logger.info(f"Google Sheets'e baglanildi: {SHEET_NAME}")

            # Basliklari kontrol et / olustur
            self._ensure_headers()

            # Mevcut domainleri yukle (mukerrer kontrol icin)
            self._load_existing_domains()

        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(
                "Tablo bulunamadi! Service account e-postasini tabloya editor olarak ekleyin."
            )
            raise
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"'{SHEET_NAME}' sayfasi bulunamadi! Lutfen olusturun.")
            raise
        except FileNotFoundError:
            msg = (
                "Google credentials bulunamadı!\n"
                "Railway Variables'a şu değişkeni ekleyin:\n"
                "  GOOGLE_SERVICE_ACCOUNT_JSON = <service_account.json içeriği>\n"
                f"(Dosya yolu: {SERVICE_ACCOUNT_FILE})"
            )
            logger.error(msg)
            raise FileNotFoundError(msg)

    def _ensure_headers(self):
        """Ilk satirdaki basliklari kontrol et, yoksa/eksikse ekle.

        Mevcut sayfalarda yeni eklenen sutunlar (or. 'Tip') icin de basligi
        gunceller (first_row sutun sayisi SHEET_COLUMNS'tan azsa).
        """
        try:
            first_row = self.worksheet.row_values(1)
            need_update = (
                not first_row
                or first_row[0] != SHEET_COLUMNS[0]
                or len(first_row) < len(SHEET_COLUMNS)
            )
            if need_update:
                last_col = self._col_letter(len(SHEET_COLUMNS))
                self.worksheet.update(f"A1:{last_col}1", [SHEET_COLUMNS])
                logger.info("Basliklar eklendi/guncellendi.")
        except Exception as e:
            logger.warning(f"Baslik kontrolunde hata: {e}")

    @staticmethod
    def _col_letter(n: int) -> str:
        """1-tabanli sutun numarasini harfe cevir (1->A, 11->K, 27->AA)."""
        result = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    def _load_existing_domains(self):
        """Mevcut domainleri yukle (F sutunu - Domain)."""
        try:
            domain_col = self.worksheet.col_values(6)  # F sutunu = Domain
            # Basligi atla
            self.existing_domains = {
                d.lower().strip() for d in domain_col[1:] if d.strip()
            }
            logger.info(f"Mevcut {len(self.existing_domains)} domain yuklendi.")
        except Exception as e:
            logger.warning(f"Domain yukleme hatasi: {e}")
            self.existing_domains = set()

    def is_duplicate(self, domain: str) -> bool:
        """Domain daha once taranmis mi kontrol et."""
        return domain.lower().strip() in self.existing_domains

    def append_businesses(self, businesses: list[dict]) -> int:
        """Isletmeleri tabloya ekle.

        Args:
            businesses: [{"name": str, "email": str, "phone": str, "domain": str}, ...]

        Returns:
            Eklenen satir sayisi
        """
        if not businesses:
            return 0

        rows = []
        for biz in businesses:
            domain = biz["domain"].lower().strip()
            if domain in self.existing_domains:
                logger.debug(f"Mukerrer atlanıyor: {domain}")
                continue

            rows.append([
                biz.get("date", ""),
                biz.get("sector", ""),
                biz["name"],
                biz["phone"],
                biz["email"],
                biz["domain"],
                biz.get("website", ""),
                biz.get("instagram", ""),
                biz.get("facebook", ""),
                biz.get("linkedin", ""),
                biz.get("type", ""),
            ])
            self.existing_domains.add(domain)

        if not rows:
            logger.info("Eklenecek yeni isletme yok (hepsi mukerrer).")
            return 0

        try:
            self.worksheet.append_rows(rows, value_input_option="RAW")
            logger.info(f"{len(rows)} isletme tabloya eklendi.")
            return len(rows)
        except Exception as e:
            logger.error(f"Tabloya yazma hatasi: {e}")
            raise

    def get_all_businesses(self) -> list[dict]:
        """Tablodaki tum isletmeleri getir."""
        try:
            records = self.worksheet.get_all_records()
            return records
        except Exception as e:
            logger.error(f"Tablo okuma hatasi: {e}")
            return []
