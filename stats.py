import json
from collections import Counter
from pathlib import Path
from typing import Any


DATA_DIR = Path("/data")

ACCEPTED_JSON_DIR = DATA_DIR / "accepted" / "json"
REJECTED_JSON_DIR = DATA_DIR / "rejected" / "json"


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


def build_stats() -> dict[str, Any]:
    accepted_records = load_records(ACCEPTED_JSON_DIR)
    rejected_records = load_records(REJECTED_JSON_DIR)

    records = accepted_records + rejected_records

    accepted = len(accepted_records)
    rejected = len(rejected_records)
    total = len(records)

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

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate": round(
            acceptance_rate,
            2,
        ),
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
