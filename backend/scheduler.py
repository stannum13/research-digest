from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from agent import run_digest
from database import SessionLocal
from settings import Settings

_scheduler: BackgroundScheduler | None = None


def start_scheduler(settings: Settings) -> BackgroundScheduler | None:
    global _scheduler
    if not settings.enable_scheduler:
        return None
    if _scheduler and _scheduler.running:
        return _scheduler

    hour, minute = [int(part) for part in settings.digest_run_time.split(":", maxsplit=1)]
    scheduler = BackgroundScheduler(timezone=settings.digest_timezone)
    scheduler.add_job(
        _scheduled_run, "cron", hour=hour, minute=minute, args=[settings], id="daily_digest", replace_existing=True
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def _scheduled_run(settings: Settings) -> None:
    db: Session = SessionLocal()
    try:
        run_digest(db, settings)
    finally:
        db.close()
