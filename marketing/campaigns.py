"""Kampanya CRUD + broadcast/sequence başlatma + istatistikler."""
import logging
from datetime import datetime, timezone, timedelta

from .db import sb_select, sb_insert, sb_update
from .queue import enqueue as _enqueue
from .segments import load_leads

logger = logging.getLogger(__name__)


# ─── CRUD ────────────────────────────────────────────────────────────────────

def list_campaigns() -> list:
    return sb_select("campaigns", {"select": "*", "order": "created_at.desc"})


def get_campaign(cid: str) -> dict | None:
    rows = sb_select("campaigns", {"id": f"eq.{cid}", "select": "*"})
    return rows[0] if rows else None


def create_campaign(data: dict) -> dict:
    payload = {
        "name":            data["name"],
        "type":            data["type"],
        "status":          "draft",
        "subject":         data.get("subject", ""),
        "body_html":       data.get("body_html", ""),
        "segment_filter":  data.get("segment_filter") or {},
        "trigger_type":    data.get("trigger_type", "manual"),
        "recurrence_cron": data.get("recurrence_cron") or None,
    }
    if data.get("scheduled_at"):
        payload["scheduled_at"] = data["scheduled_at"]

    rows = sb_insert("campaigns", payload)
    campaign = rows[0] if rows else {}

    if data.get("type") == "sequence" and data.get("steps"):
        _save_steps(campaign["id"], data["steps"])

    return campaign


def update_campaign(cid: str, data: dict) -> dict:
    allowed = {"name", "subject", "body_html", "segment_filter",
               "scheduled_at", "recurrence_cron", "trigger_type"}
    payload = {k: v for k, v in data.items() if k in allowed}
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    rows = sb_update("campaigns", {"id": f"eq.{cid}"}, payload)
    return rows[0] if rows else {}


def save_steps(cid: str, steps: list) -> None:
    _save_steps(cid, steps)


def _save_steps(cid: str, steps: list) -> None:
    for i, step in enumerate(steps):
        sb_insert("campaign_steps", {
            "campaign_id": cid,
            "step_order":  i,
            "delay_hours": int(step.get("delay_hours") or 0),
            "subject":     step.get("subject", ""),
            "body_html":   step.get("body_html", ""),
        })


def get_steps(cid: str) -> list:
    return sb_select("campaign_steps", {
        "campaign_id": f"eq.{cid}",
        "select": "*",
        "order": "step_order.asc",
    })


# ─── LAUNCH ──────────────────────────────────────────────────────────────────

def launch_campaign(cid: str) -> dict:
    campaign = get_campaign(cid)
    if not campaign:
        return {"error": "Kampanya bulunamadı"}
    if campaign["status"] == "running":
        return {"error": "Kampanya zaten çalışıyor"}

    if campaign["type"] == "broadcast":
        return _launch_broadcast(campaign)
    elif campaign["type"] == "sequence":
        return _launch_sequence(campaign)
    return {"error": "Bilinmeyen kampanya türü"}


def _launch_broadcast(campaign: dict) -> dict:
    leads = load_leads(campaign.get("segment_filter") or {})
    if not leads:
        return {"error": "Segment filtresine uyan lead bulunamadı"}

    scheduled_at = _parse_dt(campaign.get("scheduled_at"))
    count = 0
    for lead in leads:
        _enqueue(
            to_email=lead["email"],
            to_name=lead["name"],
            subject=_render(campaign.get("subject", ""), lead),
            body_html=_render(campaign.get("body_html", ""), lead),
            campaign_id=campaign["id"],
            scheduled_at=scheduled_at,
        )
        count += 1

    _set_status(campaign["id"], "running")
    return {"ok": True, "enqueued": count}


def _launch_sequence(campaign: dict) -> dict:
    leads = load_leads(campaign.get("segment_filter") or {})
    if not leads:
        return {"error": "Segment filtresine uyan lead bulunamadı"}

    steps = get_steps(campaign["id"])
    if not steps:
        return {"error": "Sekans adımı tanımlanmamış"}

    first_step = steps[0]
    enrolled = 0
    for lead in leads:
        try:
            sb_insert("campaign_enrollments", {
                "campaign_id": campaign["id"],
                "lead_email":  lead["email"],
                "lead_name":   lead.get("name", ""),
                "lead_data":   lead,
                "current_step": 0,
                "status":      "active",
                "next_send_at": _step_time(first_step["delay_hours"]).isoformat(),
            })
            enrolled += 1
        except Exception:
            pass  # duplicate — already enrolled

    _set_status(campaign["id"], "running")
    return {"ok": True, "enrolled": enrolled}


def cancel_campaign(cid: str) -> dict:
    _set_status(cid, "cancelled")
    return {"ok": True}


def _set_status(cid: str, status: str):
    sb_update("campaigns", {"id": f"eq.{cid}"}, {
        "status":     status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


# ─── ADVANCE SEQUENCES (Faz 3) ───────────────────────────────────────────────

def advance_sequences():
    """Due active enrollments'ı ilerlet — APScheduler tarafından çağrılır."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        enrollments = sb_select("campaign_enrollments", {
            "status":      "eq.active",
            "next_send_at": f"lte.{now_iso}",
            "select":      "*",
            "limit":       "100",
        })
    except Exception as e:
        logger.warning(f"advance_sequences fetch error: {e}")
        return

    for enrollment in enrollments:
        _process_enrollment(enrollment)


def _process_enrollment(enrollment: dict):
    cid          = enrollment["campaign_id"]
    eid          = enrollment["id"]
    current_step = enrollment["current_step"]
    lead_email   = enrollment["lead_email"]
    lead_name    = enrollment.get("lead_name", "")
    lead_data    = enrollment.get("lead_data") or {}

    # Suppression check
    from .db import is_suppressed
    if is_suppressed(lead_email):
        sb_update("campaign_enrollments", {"id": f"eq.{eid}"}, {"status": "unsubscribed"})
        return

    try:
        steps = sb_select("campaign_steps", {
            "campaign_id": f"eq.{cid}",
            "step_order":  f"eq.{current_step}",
            "select":      "*",
        })
    except Exception:
        return

    if not steps:
        sb_update("campaign_enrollments", {"id": f"eq.{eid}"}, {"status": "completed"})
        return

    step = steps[0]
    lead = {"name": lead_name, "email": lead_email, **lead_data}

    _enqueue(
        to_email=lead_email,
        to_name=lead_name,
        subject=_render(step["subject"], lead),
        body_html=_render(step["body_html"], lead),
        campaign_id=cid,
        enrollment_id=eid,
        step_id=step["id"],
    )

    # Sonraki adım
    next_step = current_step + 1
    try:
        next_steps = sb_select("campaign_steps", {
            "campaign_id": f"eq.{cid}",
            "step_order":  f"eq.{next_step}",
            "select":      "delay_hours",
        })
    except Exception:
        next_steps = []

    if next_steps:
        sb_update("campaign_enrollments", {"id": f"eq.{eid}"}, {
            "current_step": next_step,
            "next_send_at": _step_time(next_steps[0]["delay_hours"]).isoformat(),
        })
    else:
        sb_update("campaign_enrollments", {"id": f"eq.{eid}"}, {
            "current_step": next_step,
            "status":       "completed",
        })


def enroll_lead(cid: str, lead_email: str, lead_name: str = "", lead_data: dict | None = None) -> bool:
    """Bir lead'i sequence kampanyasına enroll et (trigger: lead_created)."""
    campaign = get_campaign(cid)
    if not campaign or campaign["type"] != "sequence" or campaign["status"] not in ("running", "draft"):
        return False
    steps = get_steps(cid)
    if not steps:
        return False
    first_step = steps[0]
    try:
        sb_insert("campaign_enrollments", {
            "campaign_id":  cid,
            "lead_email":   lead_email.lower().strip(),
            "lead_name":    lead_name,
            "lead_data":    lead_data or {},
            "current_step": 0,
            "status":       "active",
            "next_send_at": _step_time(first_step["delay_hours"]).isoformat(),
        })
        return True
    except Exception:
        return False


# ─── STATS (Faz 4) ───────────────────────────────────────────────────────────

def get_campaign_stats(cid: str) -> dict:
    try:
        queue = sb_select("email_queue", {
            "campaign_id": f"eq.{cid}",
            "select":      "status",
        })
        events = sb_select("email_events", {
            "campaign_id": f"eq.{cid}",
            "select":      "event_type",
        })

        q_counts, e_counts = {}, {}
        for item in queue:
            s = item.get("status", "unknown")
            q_counts[s] = q_counts.get(s, 0) + 1
        for e in events:
            t = e.get("event_type", "unknown")
            e_counts[t] = e_counts.get(t, 0) + 1

        total_sent = q_counts.get("sent", 0)
        opened     = e_counts.get("email.opened", 0)
        clicked    = e_counts.get("email.clicked", 0)

        return {
            "total":     len(queue),
            "sent":      total_sent,
            "failed":    q_counts.get("failed", 0),
            "pending":   q_counts.get("pending", 0) + q_counts.get("sending", 0),
            "delivered": e_counts.get("email.delivered", 0),
            "opened":    opened,
            "clicked":   clicked,
            "bounced":   e_counts.get("email.bounced", 0),
            "complained":e_counts.get("email.complained", 0),
            "open_rate": round(opened / total_sent * 100, 1) if total_sent > 0 else 0,
            "click_rate":round(clicked / total_sent * 100, 1) if total_sent > 0 else 0,
        }
    except Exception as e:
        logger.warning(f"get_campaign_stats error: {e}")
        return {}


def get_recent_events(cid: str, limit: int = 50) -> list:
    try:
        return sb_select("email_events", {
            "campaign_id": f"eq.{cid}",
            "select":      "*",
            "order":       "occurred_at.desc",
            "limit":       str(limit),
        })
    except Exception:
        return []


def get_enrollments(cid: str) -> list:
    try:
        return sb_select("campaign_enrollments", {
            "campaign_id": f"eq.{cid}",
            "select":      "*",
            "order":       "enrolled_at.desc",
        })
    except Exception:
        return []


def get_overview_stats() -> dict:
    """Son 30 gün genel istatistik."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        sent = sb_select("email_queue", {
            "status":     "eq.sent",
            "sent_at":    f"gte.{since}",
            "select":     "id",
        })
        events = sb_select("email_events", {
            "occurred_at": f"gte.{since}",
            "select":      "event_type",
        })
        suppressions = sb_select("email_suppressions", {"select": "email"})
        active_campaigns = sb_select("campaigns", {
            "status": "eq.running",
            "select": "id",
        })

        e_counts = {}
        for e in events:
            t = e.get("event_type", "")
            e_counts[t] = e_counts.get(t, 0) + 1

        total_sent = len(sent)
        opened = e_counts.get("email.opened", 0)

        return {
            "sent_30d":         total_sent,
            "open_rate_30d":    round(opened / total_sent * 100, 1) if total_sent > 0 else 0,
            "active_campaigns": len(active_campaigns),
            "total_suppressions": len(suppressions),
        }
    except Exception as e:
        logger.warning(f"get_overview_stats error: {e}")
        return {"sent_30d": 0, "open_rate_30d": 0, "active_campaigns": 0, "total_suppressions": 0}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _render(template: str, lead: dict) -> str:
    return (template
            .replace("{firma_adi}", lead.get("name", ""))
            .replace("{ad}",        lead.get("first_name", lead.get("name", "")))
            .replace("{soyad}",     lead.get("last_name", ""))
            .replace("{email}",     lead.get("email", ""))
            .replace("{sektor}",    lead.get("sector", ""))
            .replace("{sehir}",     lead.get("city", ""))
            .replace("{domain}",    lead.get("domain", "")))


def _parse_dt(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _step_time(delay_hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=int(delay_hours or 0))
