import json
from collections import Counter
from pathlib import Path
from typing import Any
from datetime import datetime


DATA_DIR = Path("/data")

ACCEPTED_JSON_DIR = DATA_DIR / "accepted" / "json"
REJECTED_JSON_DIR = DATA_DIR / "rejected" / "json"

ACCEPTED_DIR = DATA_DIR / "accepted"
REJECTED_DIR = DATA_DIR / "rejected"
WORKING_DIR = DATA_DIR / "working"


def load_records(directory: Path) -> list[dict[str, Any]]:
    records = []

    if not directory.exists():
        return records

    for path in directory.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as file:
                record = json.load(file)

            if record.get("schema_version") == 1:
                records.append(record)

        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"Warnung: {path} konnte nicht gelesen werden: {exc}"
            )

    return records


def directory_size(directory: Path) -> int:
    total_bytes = 0

    if not directory.exists():
        return total_bytes

    for path in directory.rglob("*"):
        if not path.is_file():
            continue

        try:
            total_bytes += path.stat().st_size
        except OSError as exc:
            print(
                f"Warnung: Größe von {path} "
                f"konnte nicht gelesen werden: {exc}"
            )

    return total_bytes


def build_stats() -> dict[str, Any]:
    accepted_records = load_records(ACCEPTED_JSON_DIR)
    rejected_records = load_records(REJECTED_JSON_DIR)

    records = accepted_records + rejected_records

    accepted = len(accepted_records)
    rejected = len(rejected_records)
    total = len(records)
    today = datetime.now().date()
    observations_today = 0
    last_observation = None

    for record in records:
        timestamp = record.get("timestamp")

        if not timestamp:
            continue

        try:
            observation_time = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            continue

        if observation_time.date() == today:
            observations_today += 1

        if (
            last_observation is None
            or observation_time > last_observation
        ):
            last_observation = observation_time

    acceptance_rate = (
        accepted / total * 100
        if total
        else 0.0
    )

    # Kamerastatistik
    camera_stats = {}

    for record in records:
        camera = record.get("camera", "unknown")

        if camera not in camera_stats:
            camera_stats[camera] = {
                "total": 0,
                "accepted": 0,
                "rejected": 0,
            }

        camera_stats[camera]["total"] += 1

        if record.get("accepted"):
            camera_stats[camera]["accepted"] += 1
        else:
            camera_stats[camera]["rejected"] += 1

    for camera, values in camera_stats.items():
        camera_total = values["total"]

        values["acceptance_rate"] = (
            round(
                values["accepted"] / camera_total * 100,
                2,
            )
            if camera_total
            else 0.0
        )

    # Artenstatistik nur für akzeptierte Beobachtungen
    species = Counter()

    for record in accepted_records:
        classifications = record.get(
            "classifications",
            [],
        )

        if classifications:
            label = classifications[0].get("label")

            if label and label != "background":
                species[label] += 1


    # Speicherstatistik

    accepted_bytes = directory_size(ACCEPTED_DIR)
    rejected_bytes = directory_size(REJECTED_DIR)
    working_bytes = directory_size(WORKING_DIR)
    total_bytes = (
        accepted_bytes
        + rejected_bytes
        + working_bytes
    )

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate": round(
            acceptance_rate,
            2,
        ),

        "observations_today": observations_today,
        "last_observation": (
            last_observation.isoformat(
                timespec="microseconds"
            )
            if last_observation
            else None
        ),
        "storage": {
            "accepted_bytes": accepted_bytes,
            "rejected_bytes": rejected_bytes,
            "working_bytes": working_bytes,
            "total_bytes": total_bytes,
        },

        "cameras": camera_stats,
        "species": dict(species),

    }


if __name__ == "__main__":
    print(
        json.dumps(
            build_stats(),
            ensure_ascii=False,
            indent=2,
        )
    )
