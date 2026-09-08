import json
import ssl
import urllib.request
from datetime import date

import certifi


def build_ingestion_alert(
    *,
    status: str,
    platform: str,
    start: date,
    end: date,
    loaded_files: int,
    expected_files: int,
    loaded_rows: int,
    run_id: str,
    missing_dates: list[date] | None = None,
    error_count: int = 0,
    error_type: str | None = None,
) -> dict:
    styles = {
        "succeeded": ("✅", "Ingestion completed successfully"),
        "partial": ("⚠️", "Ingestion completed with warnings"),
        "failed": ("❌", "Ingestion failed"),
    }
    emoji, title = styles.get(status, ("ℹ️", "Ingestion update"))
    platform_name = platform.replace("_", " ").title()
    fallback = f"{emoji} {title}: {platform_name}, {start} to {end}"
    fields = [
        {"type": "mrkdwn", "text": f"*Platform*\n{platform_name}"},
        {"type": "mrkdwn", "text": f"*Date range*\n{start} → {end}"},
        {"type": "mrkdwn", "text": f"*Files processed*\n{loaded_files}/{expected_files}"},
        {"type": "mrkdwn", "text": f"*Rows stored*\n{loaded_rows:,}"},
    ]
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {title}"}},
        {"type": "section", "fields": fields},
    ]
    if missing_dates:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Missing source dates*\n" + ", ".join(item.isoformat() for item in missing_dates),
            },
        })
    if status == "failed":
        reason = error_type or "Processing error"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Failure summary*\n{reason} ({error_count or 1} error(s)). Review the service logs for details.",
            },
        })
    blocks.extend([
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Run ID: `{run_id}` • Stored rows have at least 1,000 daily streams"}
            ],
        },
    ])
    return {"text": fallback, "blocks": blocks}


def send_slack_alert(webhook_url: str | None, message: str | dict) -> str:
    if not webhook_url:
        return "not_configured"
    payload = message if isinstance(message, dict) else {"text": message}
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            if response.status >= 300:
                return f"failed_http_{response.status}"
    except Exception as exc:
        return f"failed_{exc.__class__.__name__}"
    return "sent"
