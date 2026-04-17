"""Email Marketing — Flask Blueprint (sayfa + API route'ları)."""
from flask import Blueprint, render_template, request, jsonify
from .campaigns import (
    list_campaigns, get_campaign, create_campaign, update_campaign,
    launch_campaign, cancel_campaign,
    get_campaign_stats, get_recent_events, get_enrollments,
    get_overview_stats, get_steps, save_steps, enroll_lead,
)
from .segments import load_leads

marketing_bp = Blueprint("marketing", __name__)

# ─── SAYFA ROUTE'LARI ────────────────────────────────────────────────────────

@marketing_bp.route("/marketing")
def marketing_index():
    return render_template("marketing_index.html")


@marketing_bp.route("/marketing/campaigns/new")
def marketing_campaign_new():
    from dashboard import SECTORS  # kampanya wizard sektör listesi için
    sectors = list(SECTORS.keys())
    return render_template("marketing_campaign_new.html", sectors=sectors)


@marketing_bp.route("/marketing/campaigns/<cid>")
def marketing_campaign_detail(cid):
    return render_template("marketing_campaign_detail.html", campaign_id=cid)


# ─── API: GENEL ──────────────────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/stats")
def api_marketing_stats():
    return jsonify(get_overview_stats())


@marketing_bp.route("/api/marketing/segment/preview")
def api_segment_preview():
    """Filtre parametrelerine göre kaç lead eşleştiğini döndür."""
    f = {
        "sector":       request.args.get("sector", ""),
        "name_contains": request.args.get("name_contains", ""),
        "date_from":    request.args.get("date_from", ""),
        "date_to":      request.args.get("date_to", ""),
    }
    try:
        leads = load_leads(f)
        return jsonify({"count": len(leads)})
    except Exception as e:
        return jsonify({"count": 0, "error": str(e)})


# ─── API: KAMPANYALAR ────────────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/campaigns", methods=["GET"])
def api_campaigns_list():
    return jsonify(list_campaigns())


@marketing_bp.route("/api/marketing/campaigns", methods=["POST"])
def api_campaigns_create():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "Kampanya adı zorunlu"}), 400
    if data.get("type") not in ("broadcast", "sequence"):
        return jsonify({"error": "Tür broadcast veya sequence olmalı"}), 400
    campaign = create_campaign(data)
    return jsonify(campaign), 201


@marketing_bp.route("/api/marketing/campaigns/<cid>", methods=["GET"])
def api_campaign_get(cid):
    campaign = get_campaign(cid)
    if not campaign:
        return jsonify({"error": "Bulunamadı"}), 404
    campaign["steps"] = get_steps(cid)
    return jsonify(campaign)


@marketing_bp.route("/api/marketing/campaigns/<cid>", methods=["PATCH"])
def api_campaign_update(cid):
    data = request.json or {}
    updated = update_campaign(cid, data)
    if data.get("steps") is not None:
        save_steps(cid, data["steps"])
    return jsonify(updated)


@marketing_bp.route("/api/marketing/campaigns/<cid>/launch", methods=["POST"])
def api_campaign_launch(cid):
    result = launch_campaign(cid)
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


@marketing_bp.route("/api/marketing/campaigns/<cid>/cancel", methods=["POST"])
def api_campaign_cancel(cid):
    return jsonify(cancel_campaign(cid))


# ─── API: İSTATİSTİK & EVENTS ────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/campaigns/<cid>/stats")
def api_campaign_stats(cid):
    return jsonify(get_campaign_stats(cid))


@marketing_bp.route("/api/marketing/campaigns/<cid>/events")
def api_campaign_events(cid):
    limit = min(int(request.args.get("limit", 50)), 200)
    return jsonify(get_recent_events(cid, limit))


# ─── API: ENROLLMENTS (Faz 3) ────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/campaigns/<cid>/enrollments")
def api_campaign_enrollments(cid):
    return jsonify(get_enrollments(cid))


@marketing_bp.route("/api/marketing/campaigns/<cid>/enroll", methods=["POST"])
def api_campaign_enroll(cid):
    data = request.json or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "E-posta zorunlu"}), 400
    ok = enroll_lead(cid, email, data.get("name", ""), data.get("lead_data"))
    return jsonify({"ok": ok})
