#!/usr/bin/env python3
"""
Google Maps Isletme Tarayici & Pazarlama Sistemi

Kullanim:
    python main.py --sektor "oto yikama" --sehir "Istanbul"
    python main.py --sektor "kafe" --sehir "Ankara" --min 30
    python main.py --sektor "mobilya" --sehir "Izmir" --mail-gonder
"""

import argparse
import logging
import sys
import warnings

from scraper.maps_scraper import BusinessScraper
from scraper.email_extractor import EmailExtractor
from sheets.sheets_manager import SheetsManager
from mailer.sender import EmailSender
from utils.filters import is_valid_corporate_email, extract_domain_from_url
from utils.domain_parser import domain_to_business_name
from config import MIN_RESULTS

# SSL uyarilarini gizle (kotu sertifikali siteler icin)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Loglama ayarlari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Google Maps Isletme Tarayici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--sektor", "-s",
        required=True,
        help="Aranacak sektor (ornek: 'oto yikama', 'kafe', 'mobilya')",
    )
    parser.add_argument(
        "--sehir", "-c",
        required=True,
        help="Aranacak sehir (ornek: 'Istanbul', 'Ankara')",
    )
    parser.add_argument(
        "--min", "-m",
        type=int,
        default=MIN_RESULTS,
        help=f"Minimum sonuc sayisi (varsayilan: {MIN_RESULTS})",
    )
    parser.add_argument(
        "--mail-gonder",
        action="store_true",
        help="Tarama sonrasi e-posta gonderim asamasina gec",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Tarayiciyi arka planda calistir (varsayilan: acik)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Tarayiciyi gorunur modda calistir (debug icin)",
    )
    return parser.parse_args()


def run_scraper(sector: str, city: str, min_results: int, send_mail: bool, headless: bool):
    """Ana tarama islemini calistir."""

    # 1. Google Sheets'e baglan
    logger.info("Google Sheets'e baglaniyor...")
    try:
        sheets = SheetsManager()
    except Exception as e:
        logger.error(f"Google Sheets baglanti hatasi: {e}")
        logger.error(
            "\nCozum:\n"
            "1. Google Cloud Console'da bir proje olusturun\n"
            "2. Google Sheets API ve Google Drive API'yi etkinlestirin\n"
            "3. Service account olusturun ve JSON anahtarini indirin\n"
            "4. Anahtari credentials/service_account.json olarak kaydedin\n"
            "5. Tabloyu service account e-postasina editor olarak paylasin"
        )
        sys.exit(1)

    # 2. Google Maps tarayicisini baslat
    logger.info("Google Maps tarayicisi baslatiliyor...")
    scraper = BusinessScraper()

    if not headless:
        from config import HEADLESS
        import config
        config.HEADLESS = False

    try:
        scraper.start_browser()

        # 3. Isletmeleri ara
        raw_businesses = scraper.search_businesses(sector, city, min_results)

        if not raw_businesses:
            logger.warning("Hicbir isletme bulunamadi!")
            return

        logger.info(f"\n{len(raw_businesses)} isletme bulundu, e-postalar cikariliyor...\n")

    finally:
        scraper.close_browser()

    # 4. Her isletmenin web sitesinden e-posta cikar
    extractor = EmailExtractor()
    valid_businesses = []
    skipped_duplicate = 0
    skipped_no_email = 0

    for i, biz in enumerate(raw_businesses, 1):
        website = biz.get("website", "")
        if not website:
            continue

        # Domain cikar
        domain = extract_domain_from_url(website)

        # Mukerrer kontrol
        if sheets.is_duplicate(domain):
            logger.info(f"  [{i}] MUKERRER - {domain} (atlanıyor)")
            skipped_duplicate += 1
            continue

        logger.info(f"  [{i}] E-posta aranıyor: {domain}...")

        # E-postalari cikar
        emails = extractor.extract_emails_from_url(website)

        if not emails:
            logger.info(f"       Kurumsal e-posta bulunamadi.")
            skipped_no_email += 1
            continue

        # Firma adini belirle: Google'dan gelen ad varsa onu kullan, yoksa domainden cikar
        maps_name = biz.get("maps_name", "").strip()
        business_name = maps_name if maps_name else domain_to_business_name(website)

        # Ilk gecerli e-postayi kullan
        email = emails[0]

        valid_businesses.append({
            "name": business_name,
            "email": email,
            "phone": biz.get("phone", ""),
            "domain": domain,
        })

        logger.info(f"       BULUNDU: {business_name} - {email}")

    # 5. Ozet
    logger.info(f"\n{'='*60}")
    logger.info(f"TARAMA SONUCU:")
    logger.info(f"  Toplam taranan: {len(raw_businesses)}")
    logger.info(f"  Gecerli isletme: {len(valid_businesses)}")
    logger.info(f"  Mukerrer atlanan: {skipped_duplicate}")
    logger.info(f"  E-posta bulunamayan: {skipped_no_email}")
    logger.info(f"{'='*60}\n")

    if not valid_businesses:
        logger.warning("Eklenecek yeni isletme bulunamadi.")
        return

    # 6. Google Sheets'e kaydet
    logger.info("Google Sheets'e kaydediliyor...")
    added = sheets.append_businesses(valid_businesses)
    logger.info(f"{added} isletme Google Sheets'e eklendi.")

    # 7. E-posta gonderimi (istege bagli)
    if send_mail:
        sender = EmailSender()
        if sender.ask_approval(valid_businesses):
            logger.info("E-postalar gonderiliyor...")
            result = sender.send_emails(valid_businesses)
            logger.info(
                f"E-posta sonucu: {result['sent']} gonderildi, "
                f"{result['failed']} basarisiz"
            )
            if result["errors"]:
                for err in result["errors"]:
                    logger.warning(f"  Hata: {err}")
        else:
            logger.info("E-posta gonderimi iptal edildi.")
    else:
        # E-posta gonderimi istenmemisse ozet goster
        EmailSender.display_summary(valid_businesses)
        print("\nE-posta gondermek icin --mail-gonder parametresini kullanin.")


def main():
    args = parse_args()

    headless = True
    if args.no_headless:
        headless = False

    print(f"\n{'='*60}")
    print(f"  GOOGLE MAPS ISLETME TARAYICI")
    print(f"  Sektor: {args.sektor}")
    print(f"  Sehir:  {args.sehir}")
    print(f"  Min:    {args.min} isletme")
    print(f"{'='*60}\n")

    run_scraper(
        sector=args.sektor,
        city=args.sehir,
        min_results=args.min,
        send_mail=args.mail_gonder,
        headless=headless,
    )


if __name__ == "__main__":
    main()
