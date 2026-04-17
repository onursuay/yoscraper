"""Lead yükleme: Scanner (Google Sheets) ve Import (Leads) kaynakları."""
import logging

logger = logging.getLogger(__name__)


def load_leads(filter_dict: dict | None = None) -> list[dict]:
    filter_dict = filter_dict or {}
    source = filter_dict.get("source", "scanner")
    if source == "import":
        return _load_import_leads(filter_dict)
    return _load_scanner_leads(filter_dict)


# ─── Scanner ─────────────────────────────────────────────────────────────────

def _load_scanner_leads(filter_dict: dict) -> list[dict]:
    try:
        from sheets.sheets_manager import SheetsManager
        rows = SheetsManager().worksheet.get_all_values()
    except Exception as e:
        logger.warning(f"_load_scanner_leads error: {e}")
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
            "city":    "",
        })

    return _apply_scanner_filter(leads, filter_dict)


def _apply_scanner_filter(leads: list, f: dict) -> list:
    sector    = (f.get("sector") or "").strip()
    date_from = (f.get("date_from") or "").strip()
    date_to   = (f.get("date_to") or "").strip()

    result = leads
    if sector:
        result = [l for l in result if l["sector"] == sector]
    if date_from:
        result = [l for l in result if l["date"] >= date_from]
    if date_to:
        result = [l for l in result if l["date"] <= date_to]
    return result


# ─── Import / Leads ───────────────────────────────────────────────────────────

def _load_import_leads(filter_dict: dict) -> list[dict]:
    try:
        from sheets.leads_manager import LeadsManager
        rows = LeadsManager().worksheet.get_all_values()
    except Exception as e:
        logger.warning(f"_load_import_leads error: {e}")
        return []

    leads = []
    for i, row in enumerate(rows[1:], 2):
        if not row or not any(row):
            continue
        email = row[4].strip() if len(row) > 4 else ""
        if not email:
            continue
        first = row[1].strip() if len(row) > 1 else ""
        last  = row[2].strip() if len(row) > 2 else ""
        leads.append({
            "row_num":    i,
            "date":       row[0] if len(row) > 0 else "",
            "name":       f"{first} {last}".strip() or email,
            "first_name": first,
            "last_name":  last,
            "phone":      row[3] if len(row) > 3 else "",
            "email":      email,
            "city":       row[5] if len(row) > 5 else "",
            "sector":     "",
            "domain":     "",
            "website":    "",
        })

    return _apply_import_filter(leads, filter_dict)


def _apply_import_filter(leads: list, f: dict) -> list:
    city      = (f.get("city") or "").strip().lower()
    date_from = (f.get("date_from") or "").strip()
    date_to   = (f.get("date_to") or "").strip()

    result = leads
    if city:
        result = [l for l in result if city in l["city"].lower()]
    if date_from:
        result = [l for l in result if l["date"] >= date_from]
    if date_to:
        result = [l for l in result if l["date"] <= date_to]
    return result


# ─── Kaynak sayıları ──────────────────────────────────────────────────────────

def count_source(source: str) -> int:
    """Bir kaynak için e-postası olan toplam lead sayısı."""
    try:
        return len(load_leads({"source": source}))
    except Exception:
        return 0
