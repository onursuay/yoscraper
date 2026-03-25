"""
Click Bot - Flask Blueprint
Tum click bot route'lari /clickbot/* altinda calisir.
Bot tamamen ayri bir Python process'te calisir (subprocess).
"""

import json
import os
from flask import Blueprint, render_template, request, jsonify
from clickbot.subprocess_runner import SubprocessBotManager

clickbot_bp = Blueprint("clickbot", __name__, url_prefix="/clickbot")

CLICKBOT_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "clickbot_config.json",
)

bot_manager = None
_socketio = None


def _load_config():
    if os.path.exists(CLICKBOT_CONFIG_FILE):
        with open(CLICKBOT_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(data):
    existing = _load_config()
    existing.update(data)
    with open(CLICKBOT_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def init_clickbot(socketio_instance):
    """SubprocessBotManager'i SocketIO callback'leriyle baslat."""
    global bot_manager, _socketio
    _socketio = socketio_instance

    def emit_log(msg, level="info"):
        _socketio.emit("clickbot_log", {"message": msg, "level": level})

    def emit_stats(stats):
        _socketio.emit("clickbot_stats", stats)

    def emit_history(entry):
        _socketio.emit("clickbot_history", {"entry": entry})

    bot_manager = SubprocessBotManager(
        emit_log=emit_log, emit_stats=emit_stats, emit_history=emit_history
    )


def register_socketio_handlers(socketio_instance):
    @socketio_instance.on("connect")
    def handle_connect():
        if bot_manager:
            # Güncel stats gönder
            socketio_instance.emit("clickbot_stats", bot_manager.stats)
            # Son log mesajlarını replay et (sekme geçişinde kaybolmasın)
            for entry in bot_manager.log_buffer[-100:]:
                socketio_instance.emit("clickbot_log", entry)


# --- Routes ---


@clickbot_bp.route("")
@clickbot_bp.route("/")
def clickbot_dashboard():
    return render_template("clickbot.html")


@clickbot_bp.route("/api/get-config")
def get_config():
    cfg = _load_config()
    safe = {}
    if cfg.get("sheets"):
        safe["sheets"] = {
            "sheet_id": cfg["sheets"].get("sheet_id", ""),
            "credentials_path": cfg["sheets"].get("credentials_path", ""),
            "worksheet_name": cfg["sheets"].get("worksheet_name", ""),
        }
    if cfg.get("email"):
        safe["email"] = {
            "smtp_server": cfg["email"].get("smtp_server", ""),
            "smtp_port": cfg["email"].get("smtp_port", 587),
            "email": cfg["email"].get("email", ""),
            "password": cfg["email"].get("password", ""),
            "recipient": cfg["email"].get("recipient", ""),
        }
    return jsonify(safe)


@clickbot_bp.route("/api/start", methods=["POST"])
def start_bot():
    data = request.get_json()
    cities = data.get("cities", [])
    keywords = data.get("keywords", [])
    settings = data.get("settings", {})

    if not cities or not keywords:
        return jsonify({"error": "Sehir ve anahtar kelime gerekli."}), 400

    # Subprocess ölmüş ama running flag True kalmışsa düzelt
    if bot_manager.running and bot_manager._process:
        if bot_manager._process.poll() is not None:
            bot_manager.running = False
            bot_manager.stats["status"] = "idle"

    if bot_manager.running:
        return jsonify({"error": "Bot zaten calisiyor."}), 400

    bot_manager.start(cities, keywords, settings)
    return jsonify({"status": "started"})


@clickbot_bp.route("/api/stop", methods=["POST"])
def stop_bot():
    bot_manager.stop()
    return jsonify({"status": "stopped"})


@clickbot_bp.route("/api/pause", methods=["POST"])
def pause_bot():
    bot_manager.pause()
    return jsonify({"status": "paused"})


@clickbot_bp.route("/api/resume", methods=["POST"])
def resume_bot():
    bot_manager.resume()
    return jsonify({"status": "resumed"})


@clickbot_bp.route("/api/stats")
def get_stats():
    # Subprocess ölmüşse running'i düzelt
    if bot_manager.running and bot_manager._process:
        if bot_manager._process.poll() is not None:
            bot_manager.running = False
            bot_manager.stats["status"] = "idle"
    return jsonify(bot_manager.stats)


@clickbot_bp.route("/api/history")
def get_history():
    return jsonify(bot_manager.click_history[-200:])


@clickbot_bp.route("/api/clear-history", methods=["POST"])
def clear_history():
    bot_manager.click_history.clear()
    bot_manager.stats.update({
        "total_searches": 0,
        "total_ads_found": 0,
        "total_clicks": 0,
        "successful_clicks": 0,
        "failed_clicks": 0,
        "captcha_count": 0,
    })
    if _socketio:
        _socketio.emit("clickbot_stats", bot_manager.stats)
    return jsonify({"status": "cleared"})
