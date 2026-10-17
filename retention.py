import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DATA_DIR = Path("/data").resolve()

ACCEPTED_JSON_DIR = DATA_DIR / "accepted" / "json"
REJECTED_JSON_DIR = DATA_DIR / "rejected" / "json"

RETENTION_ACCEPTED_DAYS = int(
    os.getenv("RETENTION_ACCEPTED_DAYS", "0")
)

RETENTION_REJECTED_DAYS = int(
    os.getenv("RETENTION_REJECTED_DAYS", "30")
)

RETENTION_INTERVAL_DAYS = float(
    os.getenv(
        "RETENTION_INTERVAL_DAYS",
        "1",
    )
)

if RETENTION_INTERVAL_DAYS <= 0:
    raise RuntimeError(
        "RETENTION_INTERVAL_DAYS must be greater than 0"
    )

RETENTION_INTERVAL_SECONDS = (
    RETENTION_INTERVAL_DAYS
    * 24
    * 60
    * 60
)

def run_loop() -> None:
    print(
        "Birdfeeder retention service started"
    )

    print(
        "Retention interval: "
        f"{RETENTION_INTERVAL_DAYS:g} day(s)"
    )

    while True:
        try:
            run_retention(
                dry_run=False
            )
        except Exception as exc:
            print(
                "Retention run failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

        print(
            "Next retention run in "
            f"{RETENTION_INTERVAL_DAYS:g} day(s)",
            flush=True,
        )

        time.sleep(
            RETENTION_INTERVAL_SECONDS
        )

def load_record(json_path: Path) -> dict[str, Any] | None:
    try:
        with json_path.open("r", encoding="utf-8") as file:
            record = json.load(file)

        if record.get("schema_version") != 1:
            print(f"Überspringe unbekanntes Schema: {json_path}")
            return None

        return record

    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"Warnung: {json_path} konnte nicht gelesen werden: {exc}"
        )
        return None


def get_record_timestamp(record: dict[str, Any]) -> datetime | None:
    timestamp = record.get("timestamp")

    if not timestamp:
        return None

    try:
        return datetime.fromisoformat(timestamp)

    except ValueError:
        return None


def resolve_data_path(relative_path: str) -> Path:
    path = (DATA_DIR / relative_path).resolve()

    if DATA_DIR not in path.parents:
        raise ValueError(
            f"Ungültiger Pfad außerhalb von DATA_DIR: {relative_path}"
        )

    return path


def delete_file(path: Path, dry_run: bool) -> bool:
    if not path.exists():
        print(f"  fehlt bereits: {path}")
        return False

    if dry_run:
        print(f"  würde löschen: {path}")
        return True

    path.unlink()
    print(f"  gelöscht: {path}")
    return True


def delete_record(
    json_path: Path,
    record: dict[str, Any],
    dry_run: bool,
) -> None:
    event_id = record.get("event_id", json_path.stem)

    print(f"\nDatensatz: {event_id}")

    for field in ("snapshot", "crop"):
        relative_path = record.get(field)

        if not relative_path:
            print(f"  keine Referenz für {field}")
            continue

        try:
            path = resolve_data_path(relative_path)
            delete_file(path, dry_run)

        except ValueError as exc:
            print(f"  WARNUNG: {exc}")

    # JSON bewusst zuletzt löschen.
    delete_file(json_path, dry_run)


def process_retention(
    directory: Path,
    retention_days: int,
    label: str,
    dry_run: bool,
) -> dict[str, int]:
    result = {
        "checked": 0,
        "expired": 0,
    }

    print(
        f"\n{label}: Retention = {retention_days} Tage"
    )

    if retention_days <= 0:
        print("  automatische Löschung deaktiviert")
        return result

    if not directory.exists():
        print(f"  Verzeichnis existiert nicht: {directory}")
        return result

    cutoff = datetime.now() - timedelta(days=retention_days)

    for json_path in sorted(directory.glob("*.json")):
        result["checked"] += 1

        record = load_record(json_path)

        if record is None:
            continue

        timestamp = get_record_timestamp(record)

        if timestamp is None:
            print(
                f"  ungültiger oder fehlender Timestamp: {json_path}"
            )
            continue

        if timestamp >= cutoff:
            continue

        result["expired"] += 1

        delete_record(
            json_path=json_path,
            record=record,
            dry_run=dry_run,
        )

    return result


def run_retention(dry_run: bool = True) -> None:
    mode = "DRY-RUN" if dry_run else "LÖSCHEN"

    print("Birdfeeder Retention")
    print(f"Modus: {mode}")

    accepted = process_retention(
        ACCEPTED_JSON_DIR,
        RETENTION_ACCEPTED_DAYS,
        "Accepted",
        dry_run,
    )

    rejected = process_retention(
        REJECTED_JSON_DIR,
        RETENTION_REJECTED_DAYS,
        "Rejected",
        dry_run,
    )

    print("\nZusammenfassung")

    print(
        f"Accepted: {accepted['checked']} geprüft, "
        f"{accepted['expired']} abgelaufen"
    )

    print(
        f"Rejected: {rejected['checked']} geprüft, "
        f"{rejected['expired']} abgelaufen"
    )

    if dry_run:
        print("\nKeine Dateien wurden gelöscht.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Birdfeeder Retention Management"
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        help="Abgelaufene Datensätze tatsächlich löschen",
    )

    parser.add_argument(
        "--loop",
        action="store_true",
        help="Retention dauerhaft im Intervall ausführen",
    )

    args = parser.parse_args()

    if args.loop:
        if not args.delete:
            parser.error(
                "--loop requires --delete"
            )

        run_loop()

    else:
        run_retention(
            dry_run=not args.delete
        )
