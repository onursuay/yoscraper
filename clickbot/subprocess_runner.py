"""
Click Bot Subprocess Runner
Bot'u tamamen ayrı bir Python process'i olarak çalıştırır (subprocess.Popen).
Ana process ile JSON-lines pipe üzerinden haberleşir.
"""

import subprocess
import threading
import json
import os
import sys
import signal
import logging

log = logging.getLogger("subprocess_runner")


class SubprocessBotManager:
    """Click Bot'u ayrı process'te yönetir."""

    def __init__(self, emit_log, emit_stats, emit_history=None):
        self._emit_log = emit_log
        self._emit_stats = emit_stats
        self._emit_history = emit_history
        self._process = None
        self._monitor_thread = None
        self._stderr_thread = None
        self.running = False
        self.paused = False
        self.stats = {
            "total_searches": 0,
            "total_ads_found": 0,
            "total_clicks": 0,
            "successful_clicks": 0,
            "failed_clicks": 0,
            "captcha_count": 0,
            "current_keyword": "",
            "current_city": "",
            "status": "idle",
        }
        self.click_history = []
        self.log_buffer = []  # Son log mesajlarını sakla (reconnect'te replay için)

    def _safe_emit_log(self, msg, level="info"):
        """SocketIO emit hatalarını yut - reader thread ölmesin."""
        # Log'u buffer'a kaydet (reconnect'te replay için)
        self.log_buffer.append({"message": msg, "level": level})
        if len(self.log_buffer) > 200:
            self.log_buffer = self.log_buffer[-100:]
        try:
            self._emit_log(msg, level)
        except Exception:
            pass

    def _safe_emit_stats(self, stats):
        """SocketIO emit hatalarını yut - reader thread ölmesin."""
        try:
            self._emit_stats(stats)
        except Exception:
            pass

    def _safe_emit_history(self, entry):
        """SocketIO emit hatalarını yut - reader thread ölmesin."""
        try:
            if self._emit_history:
                self._emit_history(entry)
        except Exception:
            pass

    @staticmethod
    def _kill_orphan_workers():
        """Önceki dashboard'dan kalmış yetim worker process'lerini temizle."""
        import subprocess as _sp
        try:
            result = _sp.run(
                ["pgrep", "-f", "clickbot/worker.py"],
                capture_output=True, text=True, timeout=5,
            )
            for pid_str in result.stdout.strip().split("\n"):
                pid_str = pid_str.strip()
                if pid_str and pid_str.isdigit():
                    try:
                        os.kill(int(pid_str), signal.SIGTERM)
                        log.info(f"Yetim worker temizlendi: PID {pid_str}")
                    except ProcessLookupError:
                        pass
        except Exception:
            pass

    def start(self, cities, keywords, settings=None):
        if self.running:
            # Process ölmüş mü kontrol et
            if self._process and self._process.poll() is not None:
                self._cleanup()
            else:
                self._safe_emit_log("Bot zaten çalışıyor!", "warning")
                return

        # Önceki dashboard'dan kalmış yetim worker'ları temizle
        self._kill_orphan_workers()

        # Bot'u ayrı process olarak başlat
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        worker_script = os.path.join(os.path.dirname(__file__), "worker.py")

        params = json.dumps({
            "cities": cities,
            "keywords": keywords,
            "settings": settings or {},
        })

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        self._process = subprocess.Popen(
            [sys.executable, "-u", worker_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
            text=True,
            bufsize=1,
            env=env,
            start_new_session=True,  # Yeni process group - parent sinyalleri etkilemez
        )

        # Parametreleri gönder
        self._process.stdin.write(params + "\n")
        self._process.stdin.flush()

        self.running = True
        self.paused = False
        self.stats["status"] = "running"
        self._safe_emit_stats(self.stats)

        # stdout'u okuyan process referansını yakala (cleanup sırasında None olursa diye)
        proc = self._process

        # stdout monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_stdout, args=(proc,), daemon=True
        )
        self._monitor_thread.start()

        # stderr monitor thread
        self._stderr_thread = threading.Thread(
            target=self._monitor_stderr, args=(proc,), daemon=True
        )
        self._stderr_thread.start()

        # Process ölümünü izleyen thread
        self._watchdog_thread = threading.Thread(
            target=self._watchdog, args=(proc,), daemon=True
        )
        self._watchdog_thread.start()

    def _monitor_stdout(self, proc):
        """Subprocess stdout'undan JSON-lines oku.

        Her satır bağımsız try/except içinde - tek bir emit hatası
        tüm okuma döngüsünü öldürmez. Bu sayede subprocess'in
        stdout buffer'ı dolmaz ve bot donmaz.
        """
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg_type = data.get("type")

                    if msg_type == "log":
                        self._safe_emit_log(data["message"], data.get("level", "info"))

                    elif msg_type == "stats":
                        self.stats.update(data["data"])
                        self._safe_emit_stats(self.stats)

                    elif msg_type == "history":
                        self.click_history.append(data["entry"])
                        self._safe_emit_history(data["entry"])

                except Exception:
                    # JSON parse veya emit hatası - satırı atla, döngü devam etsin
                    pass
        except Exception:
            # stdout pipe kapandı - process ölmüş demektir
            pass

    def _monitor_stderr(self, proc):
        """Subprocess stderr'ını oku ve hataları logla."""
        try:
            for line in proc.stderr:
                line = line.strip()
                if not line:
                    continue
                try:
                    if any(x in line.lower() for x in ["error", "traceback", "exception", "failed"]):
                        self._safe_emit_log(f"[BOT HATA] {line}", "error")
                except Exception:
                    pass
        except Exception:
            pass

    def _watchdog(self, proc):
        """Process'in ölümünü izle ve temizle."""
        try:
            proc.wait()
        except Exception:
            pass
        self._cleanup()

    def _cleanup(self):
        """Process öldükten sonra state'i temizle."""
        self.running = False
        self.paused = False
        self.stats["status"] = "idle"
        self.stats["current_keyword"] = ""
        self.stats["current_city"] = ""
        self._safe_emit_stats(self.stats)
        self._safe_emit_log("Bot tamamlandı.", "info")
        self._process = None

    def stop(self):
        if not self._process:
            self._cleanup()
            return
        try:
            self._process.stdin.write(json.dumps({"cmd": "stop"}) + "\n")
            self._process.stdin.flush()
        except Exception:
            pass
        # Process'in kapanmasını bekle
        try:
            self._process.wait(timeout=15)
        except (subprocess.TimeoutExpired, Exception):
            # Tüm process group'u sonlandır (browser dahil)
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except Exception:
                pass
            try:
                self._process.kill()
            except Exception:
                pass
        self._cleanup()

    def pause(self):
        if not self.running or not self._process:
            return
        try:
            self._process.stdin.write(json.dumps({"cmd": "pause"}) + "\n")
            self._process.stdin.flush()
        except Exception:
            pass
        self.paused = True
        self.stats["status"] = "paused"
        self._safe_emit_stats(self.stats)

    def resume(self):
        if not self.running or not self._process:
            return
        try:
            self._process.stdin.write(json.dumps({"cmd": "resume"}) + "\n")
            self._process.stdin.flush()
        except Exception:
            pass
        self.paused = False
        self.stats["status"] = "running"
        self._safe_emit_stats(self.stats)
