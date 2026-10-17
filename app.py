from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import signal
import time

from datetime import datetime
from pathlib import Path

import requests
from PIL import Image

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraConfig:
    name: str
    label: str
    url: str
    enabled: bool


def parse_env_bool(
    value: str,
    *,
    variable_name: str,
) -> bool:
    normalized = value.strip().lower()

    if normalized in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise RuntimeError(
        f"{variable_name} must be true or false"
    )


def normalize_camera_name(
    value: str,
) -> str:
    camera_name = "".join(
        character
        if character.isalnum()
        or character in {"-", "_"}
        else "-"
        for character in value.strip().lower()
    ).strip("-_")

    if not camera_name:
        raise RuntimeError(
            "Camera name must not be empty"
        )

    return camera_name


def load_cameras() -> list[CameraConfig]:
    try:
        camera_count = int(
            os.getenv(
                "CAMERA_COUNT",
                "0",
            )
        )
    except ValueError as exc:
        raise RuntimeError(
            "CAMERA_COUNT must be an integer"
        ) from exc

    if camera_count < 1:
        raise RuntimeError(
            "CAMERA_COUNT must be at least 1"
        )

    cameras = []

    for number in range(
        1,
        camera_count + 1,
    ):
        prefix = f"CAMERA_{number}"

        name_variable = f"{prefix}_NAME"
        label_variable = f"{prefix}_LABEL"
        url_variable = f"{prefix}_URL"
        enabled_variable = f"{prefix}_ENABLED"

        name = normalize_camera_name(
            os.getenv(
                name_variable,
                f"camera_{number}",
            )
        )

        label = os.getenv(
            label_variable,
            name,
        ).strip() or name

        url = os.getenv(
            url_variable,
            "",
        ).strip()

        enabled = parse_env_bool(
            os.getenv(
                enabled_variable,
                "true",
            ),
            variable_name=enabled_variable,
        )

        if enabled and not url:
            raise RuntimeError(
                f"{url_variable} must be configured "
                f"for enabled camera {name}"
            )

        cameras.append(
            CameraConfig(
                name=name,
                label=label,
                url=url,
                enabled=enabled,
            )
        )

    names = [
        camera.name
        for camera in cameras
    ]

    if len(names) != len(set(names)):
        raise RuntimeError(
            "Camera names must be unique"
        )

    if not any(
        camera.enabled
        for camera in cameras
    ):
        raise RuntimeError(
            "At least one camera must be enabled"
        )

    return cameras

CAMERAS = load_cameras()

ENABLED_CAMERAS = [
    camera
    for camera in CAMERAS
    if camera.enabled
]

if len(ENABLED_CAMERAS) > 1:
    raise RuntimeError(
        "Multiple enabled cameras are configured, "
        "but multi-camera runtime is not enabled yet"
    )

ACTIVE_CAMERA = ENABLED_CAMERAS[0]

CAMERA_NAME = ACTIVE_CAMERA.name
CAMERA_URL = ACTIVE_CAMERA.url

RUN_ONCE = os.getenv("RUN_ONCE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

try:
    INTERVAL_SECONDS = float(
        os.getenv("INTERVAL_SECONDS", "5")
    )
except ValueError as exc:
    raise RuntimeError(
        "INTERVAL_SECONDS muss eine Zahl sein"
    ) from exc

if INTERVAL_SECONDS <= 0:
    raise RuntimeError(
        "INTERVAL_SECONDS muss größer als 0 sein"
    )

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

WORKING_DIR = DATA_DIR / "working"

ACCEPTED_DIR = DATA_DIR / "accepted"
REJECTED_DIR = DATA_DIR / "rejected"

ACCEPTED_SNAPSHOT_DIR = ACCEPTED_DIR / "snapshots"
ACCEPTED_CROP_DIR = ACCEPTED_DIR / "crops"
ACCEPTED_JSON_DIR = ACCEPTED_DIR / "json"

REJECTED_SNAPSHOT_DIR = REJECTED_DIR / "snapshots"
REJECTED_CROP_DIR = REJECTED_DIR / "crops"
REJECTED_JSON_DIR = REJECTED_DIR / "json"

DETECTOR_MODEL = (
    "ssd_mobilenet_v2_coco_quant_postprocess_edgetpu"
)
CLASSIFIER_MODEL = (
    "mobilenet_v2_1.0_224_inat_bird_quant_edgetpu"
)


def initialize_storage() -> None:
    directories = [
        WORKING_DIR,
        ACCEPTED_SNAPSHOT_DIR,
        ACCEPTED_CROP_DIR,
        ACCEPTED_JSON_DIR,
        REJECTED_SNAPSHOT_DIR,
        REJECTED_CROP_DIR,
        REJECTED_JSON_DIR,
    ]

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

def get_storage_directories(
    accepted: bool,
) -> tuple[Path, Path, Path]:
    if accepted:
        return (
            ACCEPTED_SNAPSHOT_DIR,
            ACCEPTED_CROP_DIR,
            ACCEPTED_JSON_DIR,
        )

    return (
        REJECTED_SNAPSHOT_DIR,
        REJECTED_CROP_DIR,
        REJECTED_JSON_DIR,
    )


def relative_data_path(path: Path) -> str:
    return str(path.relative_to(DATA_DIR))


def store_detection(
    *,
    event_id: str,
    snapshot_source: Path,
    crop_source: Path,
    record: dict,
    accepted: bool,
) -> Path:
    (
        snapshot_directory,
        crop_directory,
        json_directory,
    ) = get_storage_directories(accepted)

    snapshot_target = (
        snapshot_directory /
        f"{event_id}-full.jpg"
    )
    crop_target = (
        crop_directory /
        f"{event_id}-bird.jpg"
    )
    json_target = (
        json_directory /
        f"{event_id}.json"
    )

    shutil.copy2(
        snapshot_source,
        snapshot_target,
    )
    shutil.move(
        str(crop_source),
        str(crop_target),
    )

    record["snapshot"] = relative_data_path(
        snapshot_target
    )
    record["crop"] = relative_data_path(
        crop_target
    )
    record["metadata_file"] = relative_data_path(
        json_target
    )

    json_target.write_text(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return json_target

def cleanup_directory(
    directory: Path,
    retention_days: int,
) -> None:

    if retention_days <= 0:
        return

    cutoff = (
        datetime.now()
        - timedelta(days=retention_days)
    )

    for file in directory.glob("*"):
        if not file.is_file():
            continue

        modified = datetime.fromtimestamp(
            file.stat().st_mtime
        )

        if modified < cutoff:
            file.unlink()

            print(
                f"Retention: gelöscht {file}",
                flush=True,
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


stop_requested = False


def request_stop(
    signum: int,
    frame: object,
) -> None:
    del signum, frame

    global stop_requested
    stop_requested = True

    print(
        "Stoppsignal empfangen. "
        "Birdfeeder wird sauber beendet.",
        flush=True,
    )


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)

def run_once() -> int:
    initialize_storage()

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S-%f")

    snapshot_working_path = (
        WORKING_DIR /
        f"{timestamp}-{CAMERA_NAME}-full.jpg"
    )

    print(
        f"Erzeuge Kamerabild für {CAMERA_NAME} ...",
        flush=True,
    )

    create_snapshot(snapshot_working_path)

    try:
        print(
            "Suche Vögel auf der Coral ...",
            flush=True,
        )

        birds = detect_birds(
            snapshot_working_path
        )

        if not birds:
            print("Kein Vogel erkannt.")
            return 0

        print(
            f"{len(birds)} Vogel-Treffer erkannt.",
            flush=True,
        )

        for number, detection in enumerate(
            birds,
            start=1,
        ):
            event_id = (
                f"{timestamp}-{CAMERA_NAME}-bird-{number}"
            )

            crop_working_path = (
                WORKING_DIR /
                f"{event_id}.jpg"
            )

            crop_bird(
                snapshot_working_path,
                crop_working_path,
                detection["box"],
            )

            try:
                classifications = classify_bird(
                    crop_working_path
                )

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

                score_margin = (
                    top_score - second_score
                )

                accepted = bool(
                    top_result
                    and top_result.get("label")
                    != "background"
                    and top_score
                    >= CLASSIFICATION_THRESHOLD
                    and score_margin
                    >= CLASSIFICATION_MARGIN
                )

                record = {
                    "schema_version": 1,
                    "event_id": event_id,
                    "timestamp": now.isoformat(
                        timespec="microseconds"
                    ),
                    "camera": CAMERA_NAME,
                    "detector": detection,
                    "classifications": classifications,
                    "decision": {
                        "top_score": top_score,
                        "second_score": second_score,
                        "margin": score_margin,
                        "required_score": (
                            CLASSIFICATION_THRESHOLD
                        ),
                        "required_margin": (
                            CLASSIFICATION_MARGIN
                        ),
                    },
                    "accepted": accepted,
                }

                result_path = store_detection(
                    event_id=event_id,
                    snapshot_source=(
                        snapshot_working_path
                    ),
                    crop_source=crop_working_path,
                    record=record,
                    accepted=accepted,
                )

                status = (
                    "accepted"
                    if accepted
                    else "rejected"
                )

                print(
                    f"Vogel {number}: "
                    f"{status}; gespeichert unter "
                    f"{result_path}",
                    flush=True,
                )

                if not top_result:
                    print(
                        f"Vogel {number}: "
                        "Keine Artenklassifikation "
                        "verfügbar."
                    )

                elif accepted:
                    print(
                        f"Vogel {number}:",
                        top_result.get("label"),
                        f"{top_score:.2%}",
                        f"(Abstand "
                        f"{score_margin:.2%})",
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
                        f"(Abstand "
                        f"{score_margin:.2%})",
                    )

            finally:
                crop_working_path.unlink(
                    missing_ok=True
                )

        return 0

    finally:
        snapshot_working_path.unlink(
            missing_ok=True
        )

def main() -> int:
    initialize_storage()

    print(
        "Configured cameras: "
        + ", ".join(
            camera.name
            for camera in CAMERAS
        ),
        flush=True,
    )

    print(
        "Enabled cameras: "
        + ", ".join(
            camera.name
            for camera in ENABLED_CAMERAS
        ),
        flush=True,
    )

    print(
        "Pipeline camera: "
        f"{ACTIVE_CAMERA.name}",
        flush=True,
    )

    if RUN_ONCE:
        return run_once()

    print(
        "Birdfeeder läuft im Dauerbetrieb.",
        flush=True,
    )
    print(
        f"Analyseintervall: {INTERVAL_SECONDS:.1f} Sekunden",
        flush=True,
    )

    while not stop_requested:
        started_at = time.monotonic()

        try:
            run_once()
        except Exception as exc:
            print(
                f"Durchlauf fehlgeschlagen: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )

        elapsed = time.monotonic() - started_at
        remaining = max(
            0.0,
            INTERVAL_SECONDS - elapsed,
        )

        while remaining > 0 and not stop_requested:
            sleep_for = min(0.5, remaining)
            time.sleep(sleep_for)
            remaining -= sleep_for

    print(
        "Birdfeeder wurde beendet.",
        flush=True,
    )

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
