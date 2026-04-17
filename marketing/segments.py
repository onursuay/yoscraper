"""Google Sheets'ten lead yükleme + segment filtresi."""
import logging

logger = logging.getLogger(__name__)


def load_leads(filter_dict: dict | None = None) -> list[dict]:
    """SheetsManager'dan e-postası olan leadleri çek ve filtrele."""
    filter_dict = filter_dict or {}
    try:
        from sheets.sheets_manager import SheetsManager
        sheets = SheetsManager()
        rows = sheets.worksheet.get_all_values()
    except Exception as e:
        logger.warning(f"load_leads SheetsManager error: {e}")
        return []

    leads = []
    for i, row in enumerate(rows[1:], 2):
        if not row or not any(row):
            continue
        email = row[4].strip() if len(row) > 4 else ""
        if not email:
            continue
        leads.append({
            "row_num": i,
            "date":    row[0] if len(row) > 0 else "",
            "sector":  row[1] if len(row) > 1 else "",
            "name":    row[2] if len(row) > 2 else "",
            "phone":   row[3] if len(row) > 3 else "",
            "email":   email,
            "domain":  row[5] if len(row) > 5 else "",
            "website": row[6] if len(row) > 6 else "",
        })

    return _apply_filter(leads, filter_dict)


def _apply_filter(leads: list, f: dict) -> list:
    sector       = (f.get("sector") or "").strip()
    name_contains = (f.get("name_contains") or "").strip().lower()
    date_from    = (f.get("date_from") or "").strip()
    date_to      = (f.get("date_to") or "").strip()

    result = leads
    if sector:
        result = [l for l in result if l["sector"] == sector]
    if name_contains:
        result = [l for l in result if name_contains in l["name"].lower()]
    if date_from:
        result = [l for l in result if l["date"] >= date_from]
    if date_to:
        result = [l for l in result if l["date"] <= date_to]
    return result
