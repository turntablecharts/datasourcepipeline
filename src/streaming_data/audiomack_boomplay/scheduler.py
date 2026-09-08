import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.database import SessionLocal
from src.streaming_data.audiomack_boomplay.config import StreamingConfig
from src.streaming_data.audiomack_boomplay.ingestion import ingest_latest_week


logger = logging.getLogger("uvicorn.error.streaming_scheduler")
JOB_ID = "audiomack_boomplay_weekly_ingestion"
config = StreamingConfig()
scheduler = BackgroundScheduler(timezone=config.timezone)


def run_scheduled_ingestion() -> list[dict]:
    """Run the latest Friday–Thursday ingestion using a job-scoped DB session."""
    logger.info("Scheduled Audiomack/Boomplay ingestion started")
    with SessionLocal() as db:
        results = ingest_latest_week(db, trigger="scheduled", config=config)

    failures = [result for result in results if result.get("status") == "failed"]
    if failures:
        platforms = ", ".join(result.get("platform", "unknown") for result in failures)
        raise RuntimeError(f"Scheduled streaming ingestion failed for: {platforms}")

    logger.info(
        "Scheduled Audiomack/Boomplay ingestion completed: %s",
        ", ".join(
            f"{result['platform']}="
            f"{'skipped (already succeeded)' if result.get('skipped') else result['status']}"
            for result in results
        ),
    )
    return results


def start_streaming_scheduler() -> None:
    """Start one in-process scheduler for the FastAPI process."""
    if scheduler.running:
        return

    trigger = CronTrigger(day_of_week="sat", hour=10, minute=3, timezone=config.timezone)
    scheduler.add_job(
        run_scheduled_ingestion,
        trigger=trigger,
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "Streaming scheduler started in %s timezone; next run: %s",
        config.timezone,
        scheduler.get_job(JOB_ID).next_run_time.isoformat(),
    )


def stop_streaming_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Streaming scheduler stopped")
