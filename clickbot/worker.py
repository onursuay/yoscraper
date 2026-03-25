#!/usr/bin/env python3
"""
Click Bot Worker - Ayrı process'te çalışır.
stdin'den JSON parametrelerini alır, stdout'a JSON-lines yazar.
stdin'den kontrol komutları alır (stop/pause/resume).
"""

import sys
import os
import json
import signal
import threading

# Unbuffered stdout
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

# Parent process sinyallerini yoksay - browser'in kapanmasini engelle
signal.signal(signal.SIGINT, signal.SIG_IGN)
signal.signal(signal.SIGHUP, signal.SIG_IGN)

# Proje root'unu path'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def json_out(data):
    """stdout'a JSON satırı yaz."""
    try:
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def main():
    # Parametreleri stdin'den oku
    params_line = sys.stdin.readline().strip()
    if not params_line:
        json_out({"type": "log", "message": "Parametre alınamadı!", "level": "error"})
        return

    params = json.loads(params_line)
    cities = params["cities"]
    keywords = params["keywords"]
    settings = params.get("settings", {})

    # bot.py'nin logging'ini stderr'e yönlendir (stdout JSON-lines için ayrılmış)
    import logging
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

    from clickbot.bot import AdClickBot

    def emit_log(msg, level="info"):
        json_out({"type": "log", "message": msg, "level": level})

    def emit_stats(stats):
        json_out({"type": "stats", "data": stats})

    def emit_click(entry):
        json_out({"type": "history", "entry": entry})

    bot = AdClickBot(emit_log=emit_log, emit_stats=emit_stats, emit_click=emit_click)

    # stdin'den kontrol komutları dinle
    def control_listener():
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
                if cmd.get("cmd") == "stop":
                    bot.stop()
                    break
                elif cmd.get("cmd") == "pause":
                    bot.pause()
                elif cmd.get("cmd") == "resume":
                    bot.resume()
            except Exception:
                pass

    listener = threading.Thread(target=control_listener, daemon=True)
    listener.start()

    # Bot'u başlat (bu thread'de çalışacak)
    bot.start(cities, keywords, settings)

    # Bot thread'inin bitmesini bekle
    if bot._thread:
        bot._thread.join()


if __name__ == "__main__":
    main()
