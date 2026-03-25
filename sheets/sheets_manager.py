import logging

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
            creds = Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
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
            logger.error(
                f"Service account dosyasi bulunamadi: {SERVICE_ACCOUNT_FILE}\n"
                "Google Cloud Console'dan service account olusturup JSON anahtarini indirin."
            )
            raise

    def _ensure_headers(self):
        """Ilk satirdaki basliklari kontrol et, yoksa ekle."""
        try:
            first_row = self.worksheet.row_values(1)
            if not first_row or first_row[0] != SHEET_COLUMNS[0]:
                self.worksheet.update("A1:J1", [SHEET_COLUMNS])
                logger.info("Basliklar eklendi.")
        except Exception as e:
            logger.warning(f"Baslik kontrolunde hata: {e}")

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
