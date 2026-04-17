"""Supabase REST API istemcisi — email marketing tabloları için."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

_URL  = None
_KEY  = None


def _cfg():
    global _URL, _KEY
    if _URL is None:
        _URL = os.getenv("SUPABASE_URL", "").rstrip("/")
        # service_role key önce denenir, yoksa anon key
        _KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
    return _URL, _KEY


def _headers(prefer="return=representation"):
    _, key = _cfg()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def sb_select(table: str, params: dict | None = None) -> list:
    url, _ = _cfg()
    if not url:
        return []
    r = requests.get(
        f"{url}/rest/v1/{table}",
        headers=_headers(),
        params=params or {},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def sb_insert(table: str, data: dict, upsert: bool = False) -> list:
    url, _ = _cfg()
    if not url:
        return []
    prefer = "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
    r = requests.post(
        f"{url}/rest/v1/{table}",
        headers=_headers(prefer),
        json=data,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def sb_update(table: str, match: dict, data: dict) -> list:
    url, _ = _cfg()
    if not url:
        return []
    r = requests.patch(
        f"{url}/rest/v1/{table}",
        headers=_headers(),
        params=match,
        json=data,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def sb_rpc(fn: str, params: dict) -> dict:
    url, _ = _cfg()
    if not url:
        return {}
    r = requests.post(
        f"{url}/rest/v1/rpc/{fn}",
        headers=_headers(),
        json=params,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def is_suppressed(email: str) -> bool:
    """email_suppressions tablosunda var mı kontrol et."""
    try:
        rows = sb_select("email_suppressions", {"email": f"eq.{email.lower().strip()}", "select": "email"})
        return len(rows) > 0
    except Exception as e:
        logger.warning(f"Suppression check failed for {email}: {e}")
        return False


def add_suppression(email: str, reason: str = "unsubscribed", source: str = "user"):
    """email_suppressions tablosuna ekle (upsert)."""
    try:
        sb_insert("email_suppressions", {
            "email": email.lower().strip(),
            "reason": reason,
            "source": source,
        }, upsert=True)
    except Exception as e:
        logger.warning(f"add_suppression failed for {email}: {e}")


def remove_suppression(email: str):
    """email_suppressions tablosundan sil."""
    url, _ = _cfg()
    if not url:
        return
    try:
        requests.delete(
            f"{url}/rest/v1/email_suppressions",
            headers=_headers(),
            params={"email": f"eq.{email.lower().strip()}"},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"remove_suppression failed for {email}: {e}")
