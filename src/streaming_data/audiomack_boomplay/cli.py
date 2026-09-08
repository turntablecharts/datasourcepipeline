import argparse
import json
from datetime import date

from src.database import SessionLocal
from src.streaming_data.audiomack_boomplay.dates import validate_reporting_week
from src.streaming_data.audiomack_boomplay.ingestion import ingest_latest_week, ingest_week


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Audiomack and Boomplay streaming data")
    parser.add_argument("command", choices=("ingest-latest-week", "ingest-week"))
    parser.add_argument("--start-date", help="Friday in YYYY-MM-DD format; required for ingest-week")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "ingest-latest-week":
            results = ingest_latest_week(db)
        else:
            if not args.start_date:
                parser.error("--start-date is required for ingest-week")
            start, end = validate_reporting_week(date.fromisoformat(args.start_date))
            results = ingest_week(db, start, end, trigger="manual")
    print(json.dumps(results, indent=2))
    return 1 if any(item.get("status") == "failed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
