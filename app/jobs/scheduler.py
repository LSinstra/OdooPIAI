import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import get_settings
from .daily_digest import run_daily_digest
from .risk_scan import run_risk_scan

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler

    s = get_settings()
    sched = AsyncIOScheduler(timezone=s.TIMEZONE)

    sched.add_job(
        run_daily_digest,
        CronTrigger(hour=s.DAILY_DIGEST_HOUR, minute=s.DAILY_DIGEST_MINUTE),
        id="daily_digest",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        run_risk_scan,
        IntervalTrigger(hours=s.RISK_SCAN_INTERVAL_HOURS),
        id="risk_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info("scheduler started: digest=%02d:%02d, risk every %sh",
                s.DAILY_DIGEST_HOUR, s.DAILY_DIGEST_MINUTE, s.RISK_SCAN_INTERVAL_HOURS)
    return sched


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
