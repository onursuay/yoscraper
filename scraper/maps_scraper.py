import os
import logging
import time
import requests

from config import MIN_RESULTS

logger = logging.getLogger(__name__)

# Google Places API ayarlari
PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")


class BusinessScraper:
    """Google Places API uzerinden isletmeleri bulan sinif.

    Playwright/browser kullanmaz - dogrudan API uzerinden calisir.
    Bot algilamasi, CAPTCHA gibi sorunlar olmaz.
    """

    def __init__(self):
        self.api_key = PLACES_API_KEY
        self.session = requests.Session()

    def start_browser(self):
        """Uyumluluk icin - API kullandigimiz icin tarayici gerekmiyor."""
        if not self.api_key:
            raise ValueError(
                "GOOGLE_PLACES_API_KEY ayarlanmamis!\n"
                ".env dosyasina GOOGLE_PLACES_API_KEY=your-key ekleyin.\n"
                "Google Cloud Console > APIs & Services > Credentials > Create API Key"
            )
        logger.info("Google Places API hazir.")

    def close_browser(self):
        """Uyumluluk icin."""
        pass

    def search_businesses(self, sector: str, city: str, min_results: int = None) -> list:
        """Google Places API ile isletmeleri ara.

        Text Search API kullanarak sektor + sehir bazli arama yapar.
        Her isletme icin Place Details API ile web sitesi ve telefon bilgisi alir.

        Returns:
            [{"maps_name": str, "website": str, "phone": str}, ...]
        """
        if min_results is None:
            min_results = MIN_RESULTS

        # Birden fazla arama sorgusu ile yeterli sonuc topla
        queries = [
            f"{sector} {city}",
            f"{sector} firmaları {city}",
            f"{sector} {city} iletişim",
        ]

        all_businesses = []
        seen_place_ids = set()

        for q_idx, query in enumerate(queries):
            logger.info(f"Arama {q_idx+1}/{len(queries)}: '{query}'")
            next_page_token = None

            # Her sorgu icin tum sayfalari gez
            for page in range(3):  # Max 3 sayfa (60 sonuc) per query
                businesses, next_page_token = self._text_search(query, next_page_token)

                if not businesses:
                    break

                for biz in businesses:
                    if biz["place_id"] not in seen_place_ids:
                        seen_place_ids.add(biz["place_id"])
                        all_businesses.append(biz)

                logger.info(f"  Sayfa {page+1}: toplam {len(all_businesses)} benzersiz isletme")

                if not next_page_token:
                    break

                time.sleep(2)  # Google next_page_token icin bekleme

        logger.info(f"Toplam {len(all_businesses)} benzersiz isletme bulundu, detaylar alınıyor...")

        # Her isletme icin detay bilgisi al (web sitesi, telefon)
        # min_results'a ulasana kadar devam et
        results = []
        for i, biz in enumerate(all_businesses):
            if len(results) >= min_results:
                break

            logger.info(f"  [{i+1}/{len(all_businesses)}] {biz['name']} detaylari aliniyor...")

            details = self._get_place_details(biz["place_id"])
            if details and details.get("website"):
                results.append({
                    "maps_name": biz["name"],
                    "website": details["website"],
                    "phone": details.get("phone", ""),
                })
                logger.info(f"    -> Web sitesi bulundu ({len(results)}/{min_results})")

            time.sleep(0.2)

        logger.info(f"Web sitesi olan {len(results)} isletme bulundu.")
        return results

    def _text_search(self, query: str, page_token: str = None) -> tuple:
        """Google Places Text Search API.

        Returns:
            (businesses_list, next_page_token)
        """
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key,
            "language": "tr",
            "region": "tr",
        }

        if page_token:
            params["pagetoken"] = page_token

        try:
            response = self.session.get(url, params=params, timeout=15)
            data = response.json()

            if data.get("status") == "REQUEST_DENIED":
                error_msg = data.get("error_message", "Bilinmeyen hata")
                logger.error(f"API Hatasi: {error_msg}")
                raise ValueError(f"Google Places API hatasi: {error_msg}")

            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                logger.warning(f"API durumu: {data.get('status')}")
                return [], None

            businesses = []
            for result in data.get("results", []):
                businesses.append({
                    "place_id": result["place_id"],
                    "name": result.get("name", ""),
                    "address": result.get("formatted_address", ""),
                })

            next_token = data.get("next_page_token")
            return businesses, next_token

        except requests.RequestException as e:
            logger.error(f"Text Search API hatasi: {e}")
            return [], None

    def _get_place_details(self, place_id: str) -> dict:
        """Google Places Details API - web sitesi ve telefon bilgisi al."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "website,formatted_phone_number,name",
            "key": self.api_key,
            "language": "tr",
        }

        try:
            response = self.session.get(url, params=params, timeout=15)
            data = response.json()

            if data.get("status") != "OK":
                return {}

            result = data.get("result", {})
            return {
                "website": result.get("website", ""),
                "phone": result.get("formatted_phone_number", ""),
                "name": result.get("name", ""),
            }

        except requests.RequestException as e:
            logger.error(f"Place Details API hatasi: {e}")
            return {}
