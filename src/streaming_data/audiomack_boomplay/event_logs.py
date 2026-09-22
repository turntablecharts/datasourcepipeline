import json
import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.models import StreamingIngestionRunEvent
from src.utils.constant import EnvConstants


logger = logging.getLogger(__name__)


def _redact(value: str, additional_secrets: list[str] | None = None) -> str:
    secrets = [
        EnvConstants.DB_PASSWORD,
        EnvConstants.FTP_PASS,
        EnvConstants.GPG_PASSPHRASE,
        EnvConstants.SLACK_WEBHOOK_URL,
        *(additional_secrets or []),
    ]
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result[:4000]


def safe_exception_details(exc: Exception, additional_secrets: list[str] | None = None) -> dict:
    return {
        "exception_type": exc.__class__.__name__,
        "message": _redact(str(exc), additional_secrets),
    }


def write_ingestion_event(
    db: Session,
    run_id: str,
    level: str,
    event_type: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    source_file: str | None = None,
    play_date: date | None = None,
) -> bool:
    """Persist an ingestion event without allowing log failure to mask the pipeline result."""
    try:
        serialized_details = json.dumps(details, default=str) if details else None
        db.add(StreamingIngestionRunEvent(
            ingestion_run_id=run_id,
            level=level.upper(),
            event_type=event_type,
            message=_redact(message),
            details=_redact(serialized_details) if serialized_details else None,
            source_file=source_file,
            play_date=play_date,
        ))
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception("Could not persist ingestion event %s for run %s", event_type, run_id)
        return False


def serialize_event(event: StreamingIngestionRunEvent) -> dict:
    try:
        details = json.loads(event.details) if event.details else None
    except json.JSONDecodeError:
        details = {"message": event.details}
    return {
        "id": event.id,
        "ingestion_run_id": event.ingestion_run_id,
        "level": event.level,
        "event_type": event.event_type,
        "message": event.message,
        "details": details,
        "source_file": event.source_file,
        "play_date": event.play_date.isoformat() if event.play_date else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
