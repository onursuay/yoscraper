"""APScheduler kurulumu — Flask app içinde background job'lar."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(daemon=True, timezone="UTC")

    _scheduler.add_job(
        _run_queue_processor,
        trigger="interval",
        minutes=1,
        id="queue_processor",
        replace_existing=True,
    )

    _scheduler.add_job(
        _run_advance_sequences,
        trigger="interval",
        minutes=5,
        id="advance_sequences",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("APScheduler started (queue_processor@1min, advance_sequences@5min)")


def _run_queue_processor():
    from .queue import process_queue
    try:
        process_queue()
    except Exception as e:
        logger.warning(f"queue_processor error: {e}")


def _run_advance_sequences():
    from .campaigns import advance_sequences
    try:
        advance_sequences()
    except Exception as e:
        logger.warning(f"advance_sequences error: {e}")
