"""Email kuyruğu: enqueue + queue processor."""
import os
import logging
from datetime import datetime, timezone

import requests as _req

from .db import sb_select, sb_insert, sb_update, is_suppressed, add_suppression
from .unsub import generate_token

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def enqueue(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    campaign_id: str | None = None,
    enrollment_id: str | None = None,
    step_id: str | None = None,
    scheduled_at: datetime | None = None,
) -> dict | None:
    """email_queue tablosuna yeni satır ekle."""
    data = {
        "to_email": to_email,
        "to_name": to_name,
        "subject": subject,
        "body_html": body_html,
        "status": "pending",
        "scheduled_at": (scheduled_at or datetime.now(timezone.utc)).isoformat(),
    }
    if campaign_id:    data["campaign_id"]   = campaign_id
    if enrollment_id:  data["enrollment_id"] = enrollment_id
    if step_id:        data["step_id"]       = step_id
    try:
        rows = sb_insert("email_queue", data)
        return rows[0] if rows else None
    except Exception as e:
        logger.warning(f"enqueue failed ({to_email}): {e}")
        return None


def process_queue():
    """Bekleyen queue öğelerini Resend'e gönder. APScheduler tarafından dakikada çağrılır."""
    api_key   = os.getenv("RESEND_API_KEY", "")
    from_name = os.getenv("FROM_NAME", "YO Dijital")
    from_email = os.getenv("FROM_EMAIL", "info@yodijital.com")
    base_url  = os.getenv("APP_BASE_URL", "https://scraper.yodijital.com")

    if not api_key:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        items = sb_select("email_queue", {
            "status": "eq.pending",
            "scheduled_at": f"lte.{now_iso}",
            "select": "*",
            "order": "scheduled_at.asc",
            "limit": "50",
        })
    except Exception as e:
        logger.warning(f"Queue fetch error: {e}")
        return

    sent_count = failed_count = 0

    for item in items:
        qid   = item["id"]
        email = item["to_email"]
        name  = item.get("to_name") or "Yetkili"

        # Suppression kontrolü
        if is_suppressed(email):
            sb_update("email_queue", {"id": f"eq.{qid}"}, {"status": "failed", "last_error": "suppressed"})
            failed_count += 1
            continue

        # Gönderiliyor olarak işaretle
        try:
            sb_update("email_queue", {"id": f"eq.{qid}"}, {
                "status": "sending",
                "attempts": (item.get("attempts") or 0) + 1,
            })
        except Exception as e:
            logger.warning(f"Queue mark-sending failed ({qid}): {e}")
            continue

        # Footer inject
        unsub_url = f"{base_url}/unsubscribe?token={generate_token(email)}"
        body      = item["body_html"] + _email_footer(unsub_url)

        try:
            resp = _req.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{from_name} <{from_email}>",
                    "to":   [email],
                    "subject": item["subject"],
                    "html": body,
                    "headers": {
                        "List-Unsubscribe": f"<{unsub_url}>",
                        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    },
                },
                timeout=15,
            )
            if resp.status_code == 200:
                msg_id = resp.json().get("id", "")
                sb_update("email_queue", {"id": f"eq.{qid}"}, {
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "provider_message_id": msg_id,
                })
                _log_event(item.get("campaign_id"), qid, email, "sent")
                sent_count += 1
            else:
                err = resp.json().get("message", resp.text)[:200]
                sb_update("email_queue", {"id": f"eq.{qid}"}, {"status": "failed", "last_error": err})
                _log_event(item.get("campaign_id"), qid, email, "failed", {"error": err})
                failed_count += 1
        except Exception as e:
            err = str(e)[:200]
            try:
                sb_update("email_queue", {"id": f"eq.{qid}"}, {"status": "failed", "last_error": err})
            except Exception:
                pass
            failed_count += 1

    if sent_count or failed_count:
        logger.info(f"Queue processor: {sent_count} sent, {failed_count} failed")


def build_footer(base_url: str, email: str) -> str:
    unsub_url = f"{base_url}/unsubscribe?token={generate_token(email)}"
    return _email_footer(unsub_url), unsub_url


def _email_footer(unsub_url: str) -> str:
    return (
        '<div style="margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;'
        'font-family:Arial,sans-serif;font-size:12px;color:#94a3b8;text-align:center;">'
        f'<p>Bu e-postayı almak istemiyorsanız '
        f'<a href="{unsub_url}" style="color:#3b82f6;">abonelikten çıkabilirsiniz</a>'
        f' / <a href="{unsub_url}" style="color:#3b82f6;">unsubscribe</a>.</p>'
        '<p style="margin-top:8px;">YO Dijital &bull; yodijital.com</p>'
        '</div>'
    )


def _log_event(campaign_id, queue_id, to_email, event_type, metadata=None):
    try:
        sb_insert("email_events", {
            "queue_id":    queue_id,
            "campaign_id": campaign_id,
            "to_email":    to_email,
            "event_type":  event_type,
            "metadata":    metadata or {},
        })
    except Exception as e:
        logger.debug(f"_log_event failed: {e}")
