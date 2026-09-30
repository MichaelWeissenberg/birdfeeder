from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image


CAMERA_URL = os.environ["CAMERA_URL"]
CORAL_API_URL = os.getenv(
    "CORAL_API_URL",
    "http://127.0.0.1:8001",
).rstrip("/")

DETECTION_THRESHOLD = float(
    os.getenv("DETECTION_THRESHOLD", "0.30")
)
CLASSIFICATION_THRESHOLD = float(
    os.getenv("CLASSIFICATION_THRESHOLD", "0.30")
)
CLASSIFICATION_MARGIN = float(
    os.getenv("CLASSIFICATION_MARGIN", "0.10")
)

DATA_DIR = Path("/data")
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CROP_DIR = DATA_DIR / "crops"

DETECTOR_MODEL = (
    "ssd_mobilenet_v2_coco_quant_postprocess_edgetpu"
)
CLASSIFIER_MODEL = (
    "mobilenet_v2_1.0_224_inat_bird_quant_edgetpu"
)


def create_snapshot(target: Path) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        CAMERA_URL,
        "-frames:v",
        "1",
        "-y",
        str(target),
    ]

    subprocess.run(
        command,
        check=True,
        timeout=30,
    )


def post_image(
    endpoint: str,
    image_path: Path,
    params: dict[str, str],
) -> dict:
    with image_path.open("rb") as handle:
        response = requests.post(
            f"{CORAL_API_URL}{endpoint}",
            params=params,
            files={
                "file": (
                    image_path.name,
                    handle,
                    "image/jpeg",
                )
            },
            timeout=60,
        )

    response.raise_for_status()
    return response.json()


def detect_birds(image_path: Path) -> list[dict]:
    result = post_image(
        "/v1/vision/detect",
        image_path,
        {
            "model": DETECTOR_MODEL,
            "threshold": str(DETECTION_THRESHOLD),
        },
    )

    return [
        detection
        for detection in result.get("results", [])
        if detection.get("label") == "bird"
    ]


def crop_bird(
    source_path: Path,
    target_path: Path,
    box: list[float],
    padding_ratio: float = 0.12,
) -> None:
    image = Image.open(source_path).convert("RGB")
    width, height = image.size

    ymin, xmin, ymax, xmax = box

    left = int(xmin * width)
    top = int(ymin * height)
    right = int(xmax * width)
    bottom = int(ymax * height)

    box_width = max(1, right - left)
    box_height = max(1, bottom - top)

    padding_x = int(box_width * padding_ratio)
    padding_y = int(box_height * padding_ratio)

    left = max(0, left - padding_x)
    top = max(0, top - padding_y)
    right = min(width, right + padding_x)
    bottom = min(height, bottom + padding_y)

    image.crop(
        (left, top, right, bottom)
    ).save(
        target_path,
        format="JPEG",
        quality=92,
    )


def classify_bird(image_path: Path) -> list[dict]:
    result = post_image(
        "/v1/vision/classify",
        image_path,
        {
            "model": CLASSIFIER_MODEL,
            "top_k": "5",
        },
    )

    return result.get("results", [])


def main() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    CROP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    snapshot_path = (
        SNAPSHOT_DIR / f"{timestamp}-full.jpg"
    )

    print("Erzeuge Kamerabild ...", flush=True)
    create_snapshot(snapshot_path)

    print("Suche Vögel auf der Coral ...", flush=True)
    birds = detect_birds(snapshot_path)

    if not birds:
        print("Kein Vogel erkannt.")
        snapshot_path.unlink(missing_ok=True)
        return 0

    print(
        f"{len(birds)} Vogel-Treffer erkannt.",
        flush=True,
    )

    records: list[dict] = []

    for number, detection in enumerate(birds, start=1):
        crop_path = (
            CROP_DIR /
            f"{timestamp}-bird-{number}.jpg"
        )

        crop_bird(
            snapshot_path,
            crop_path,
            detection["box"],
        )

        classifications = classify_bird(crop_path)

        top_result = (
            classifications[0]
            if classifications
            else None
        )

        second_result = (
            classifications[1]
            if len(classifications) > 1
            else None
        )

        top_score = float(
            top_result.get("score", 0)
            if top_result
            else 0
        )
        second_score = float(
            second_result.get("score", 0)
            if second_result
            else 0
        )
        score_margin = top_score - second_score

        accepted = bool(
            top_result
            and top_result.get("label") != "background"
            and top_score >= CLASSIFICATION_THRESHOLD
            and score_margin >= CLASSIFICATION_MARGIN
        )

        record = {
            "timestamp": timestamp,
            "snapshot": str(snapshot_path),
            "crop": str(crop_path),
            "detector": detection,
            "classifications": classifications,
            "decision": {
                "top_score": top_score,
                "second_score": second_score,
                "margin": score_margin,
                "required_score": CLASSIFICATION_THRESHOLD,
                "required_margin": CLASSIFICATION_MARGIN,
            },
            "accepted": accepted,
        }

        records.append(record)

        if not top_result:
            print(
                f"Vogel {number}: "
                "Keine Artenklassifikation verfügbar."
            )
        elif accepted:
            print(
                f"Vogel {number}:",
                top_result.get("label"),
                f"{top_score:.2%}",
                f"(Abstand {score_margin:.2%})",
            )
        else:
            print(
                f"Vogel {number}: "
                "Art nicht sicher bestimmbar."
            )
            print(
                "  Bester Vorschlag:",
                top_result.get("label"),
                f"{top_score:.2%}",
                f"(Abstand {score_margin:.2%})",
            )

    result_path = DATA_DIR / f"{timestamp}.json"

    result_path.write_text(
        json.dumps(
            records,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Ergebnis gespeichert: {result_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"FEHLER: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
