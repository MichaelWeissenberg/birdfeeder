from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image


API_BASE = "http://127.0.0.1:8001"

DETECTOR_MODEL = (
    "ssd_mobilenet_v2_coco_quant_postprocess_edgetpu"
)

CLASSIFIER_MODEL = (
    "mobilenet_v2_1.0_224_inat_bird_quant_edgetpu"
)

DETECTION_THRESHOLD = 0.20
SPECIES_THRESHOLD = 0.30
SPECIES_MARGIN = 0.10
CROP_PADDING = 0.12

INPUT_DIR = Path("/input")
OUTPUT_DIR = Path("/results")
CROP_DIR = OUTPUT_DIR / "crops"

SOURCE_CSV = INPUT_DIR / "SOURCES.csv"
RESULT_JSON = OUTPUT_DIR / "benchmark-results.json"
RESULT_CSV = OUTPUT_DIR / "benchmark-results.csv"


def post_image(
    endpoint: str,
    image_path: Path,
    parameters: dict[str, str | int | float],
) -> dict:
    with image_path.open("rb") as image_file:
        response = requests.post(
            f"{API_BASE}{endpoint}",
            params=parameters,
            files={
                "file": (
                    image_path.name,
                    image_file,
                    "image/jpeg",
                )
            },
            timeout=120,
        )

    response.raise_for_status()
    return response.json()


def species_from_label(label: str | None) -> str:
    if not label:
        return ""

    return label.split(" (", 1)[0].strip()


def species_matches(
    expected: str,
    predicted: str,
) -> bool:
    expected = expected.strip().casefold()
    predicted = predicted.strip().casefold()

    if expected == predicted:
        return True

    # Das Modell führt das Haushuhn gegebenenfalls
    # unter der Stammart Gallus gallus.
    if expected == "gallus gallus domesticus":
        return predicted in {
            "gallus gallus",
            "gallus gallus domesticus",
        }

    return False


def crop_detection(
    image: Image.Image,
    box: list[float],
    output_path: Path,
) -> dict[str, int]:
    width, height = image.size

    ymin, xmin, ymax, xmax = box

    left = xmin * width
    top = ymin * height
    right = xmax * width
    bottom = ymax * height

    box_width = right - left
    box_height = bottom - top

    pad_x = box_width * CROP_PADDING
    pad_y = box_height * CROP_PADDING

    left = max(0, int(left - pad_x))
    top = max(0, int(top - pad_y))
    right = min(width, int(right + pad_x))
    bottom = min(height, int(bottom + pad_y))

    crop = image.crop((left, top, right, bottom))
    crop.save(output_path, quality=95)

    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


def classify_crop(crop_path: Path) -> list[dict]:
    payload = post_image(
        "/v1/vision/classify",
        crop_path,
        {
            "model": CLASSIFIER_MODEL,
            "top_k": 5,
        },
    )

    return payload.get("results", [])


def evaluate_classification(
    expected_species: str,
    classifications: list[dict],
) -> dict:
    if not classifications:
        return {
            "top1_label": "",
            "top1_species": "",
            "top1_score": 0.0,
            "top2_score": 0.0,
            "margin": 0.0,
            "expected_rank": None,
            "top1_correct": False,
            "accepted": False,
            "grade": "D",
        }

    top1 = classifications[0]
    top2 = classifications[1] if len(classifications) > 1 else {}

    top1_label = str(top1.get("label") or "")
    top1_species = species_from_label(top1_label)

    top1_score = float(top1.get("score") or 0.0)
    top2_score = float(top2.get("score") or 0.0)
    margin = top1_score - top2_score

    expected_rank = None

    for rank, result in enumerate(classifications, start=1):
        candidate = species_from_label(result.get("label"))

        if species_matches(expected_species, candidate):
            expected_rank = rank
            break

    top1_correct = species_matches(
        expected_species,
        top1_species,
    )

    accepted = (
        top1_label.casefold() != "background"
        and top1_score >= SPECIES_THRESHOLD
        and margin >= SPECIES_MARGIN
    )

    if top1_correct and accepted:
        grade = "A"
    elif top1_correct:
        grade = "B"
    elif expected_rank is not None:
        grade = "C"
    else:
        grade = "D"

    return {
        "top1_label": top1_label,
        "top1_species": top1_species,
        "top1_score": top1_score,
        "top2_score": top2_score,
        "margin": margin,
        "expected_rank": expected_rank,
        "top1_correct": top1_correct,
        "accepted": accepted,
        "grade": grade,
    }


def process_image(
    filename: str,
    expected_species: str,
) -> dict:
    image_path = INPUT_DIR / filename

    print()
    print(f"=== {filename} ===")
    print(f"Erwartet: {expected_species}")

    detection_payload = post_image(
        "/v1/vision/detect",
        image_path,
        {
            "model": DETECTOR_MODEL,
            "threshold": DETECTION_THRESHOLD,
        },
    )

    bird_detections = [
        detection
        for detection in detection_payload.get("results", [])
        if str(detection.get("label", "")).casefold() == "bird"
    ]

    if not bird_detections:
        print("Kein Vogel erkannt.")

        return {
            "filename": filename,
            "expected_species": expected_species,
            "bird_detected": False,
            "detections": 0,
            "best_detector_score": 0.0,
            "best_crop": "",
            "top1_label": "",
            "top1_species": "",
            "top1_score": 0.0,
            "top2_score": 0.0,
            "margin": 0.0,
            "expected_rank": None,
            "top1_correct": False,
            "accepted": False,
            "grade": "E",
            "all_candidates": [],
        }

    bird_detections.sort(
        key=lambda item: float(item.get("score") or 0.0),
        reverse=True,
    )

    image = Image.open(image_path).convert("RGB")
    candidates = []

    for number, detection in enumerate(bird_detections, start=1):
        crop_name = (
            f"{image_path.stem}-bird-{number}.jpg"
        )
        crop_path = CROP_DIR / crop_name

        crop_coordinates = crop_detection(
            image,
            detection["box"],
            crop_path,
        )

        classifications = classify_crop(crop_path)

        evaluation = evaluate_classification(
            expected_species,
            classifications,
        )

        candidate = {
            "crop": str(crop_path),
            "detector_score": float(
                detection.get("score") or 0.0
            ),
            "detector_box": detection.get("box"),
            "crop_coordinates": crop_coordinates,
            "classifications": classifications,
            **evaluation,
        }

        candidates.append(candidate)

        print(
            f"Vogel {number}: "
            f"Detektor {candidate['detector_score']:.2%}, "
            f"Top 1 {candidate['top1_label']} "
            f"{candidate['top1_score']:.2%}, "
            f"Bewertung {candidate['grade']}"
        )

    # Bestes Ergebnis bevorzugt korrekte Art, danach
    # Klassifikationswert und Detektorwert.
    best = max(
        candidates,
        key=lambda item: (
            bool(item["top1_correct"]),
            float(item["top1_score"]),
            float(item["detector_score"]),
        ),
    )

    return {
        "filename": filename,
        "expected_species": expected_species,
        "bird_detected": True,
        "detections": len(bird_detections),
        "best_detector_score": best["detector_score"],
        "best_crop": best["crop"],
        "top1_label": best["top1_label"],
        "top1_species": best["top1_species"],
        "top1_score": best["top1_score"],
        "top2_score": best["top2_score"],
        "margin": best["margin"],
        "expected_rank": best["expected_rank"],
        "top1_correct": best["top1_correct"],
        "accepted": best["accepted"],
        "grade": best["grade"],
        "all_candidates": candidates,
    }


def write_csv(results: list[dict]) -> None:
    fields = [
        "filename",
        "expected_species",
        "bird_detected",
        "detections",
        "best_detector_score",
        "best_crop",
        "top1_label",
        "top1_species",
        "top1_score",
        "top2_score",
        "margin",
        "expected_rank",
        "top1_correct",
        "accepted",
        "grade",
    ]

    with RESULT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    field: result.get(field)
                    for field in fields
                }
            )


def print_summary(results: list[dict]) -> None:
    total = len(results)
    detected = sum(
        bool(result["bird_detected"])
        for result in results
    )
    top1_correct = sum(
        bool(result["top1_correct"])
        for result in results
    )
    accepted_correct = sum(
        bool(result["top1_correct"])
        and bool(result["accepted"])
        for result in results
    )

    grades = {
        grade: sum(result["grade"] == grade for result in results)
        for grade in ("A", "B", "C", "D", "E")
    }

    print()
    print("=== ZUSAMMENFASSUNG ===")
    print(f"Bilder insgesamt:       {total}")
    print(f"Vogel erkannt:          {detected}/{total}")
    print(f"Erwartete Art Top 1:    {top1_correct}/{total}")
    print(f"Korrekt und akzeptiert: {accepted_correct}/{total}")
    print(
        "Bewertungen:           "
        + ", ".join(
            f"{grade}={count}"
            for grade, count in grades.items()
        )
    )
    print(f"CSV:  {RESULT_CSV}")
    print(f"JSON: {RESULT_JSON}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CROP_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_CSV.is_file():
        print(
            f"Fehler: {SOURCE_CSV} fehlt.",
            file=sys.stderr,
        )
        return 1

    rows = []

    with SOURCE_CSV.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        for row in csv.DictReader(handle):
            filename = row["filename"].strip()
            expected = row["expected_species"].strip()

            if not (INPUT_DIR / filename).is_file():
                print(
                    f"Warnung: {filename} fehlt und wird übersprungen.",
                    file=sys.stderr,
                )
                continue

            rows.append((filename, expected))

    results = []

    for filename, expected in rows:
        try:
            results.append(
                process_image(filename, expected)
            )
        except Exception as exc:
            print(
                f"FEHLER bei {filename}: {exc}",
                file=sys.stderr,
            )

            results.append(
                {
                    "filename": filename,
                    "expected_species": expected,
                    "bird_detected": False,
                    "detections": 0,
                    "best_detector_score": 0.0,
                    "best_crop": "",
                    "top1_label": "",
                    "top1_species": "",
                    "top1_score": 0.0,
                    "top2_score": 0.0,
                    "margin": 0.0,
                    "expected_rank": None,
                    "top1_correct": False,
                    "accepted": False,
                    "grade": "ERROR",
                    "error": str(exc),
                    "all_candidates": [],
                }
            )

        time.sleep(0.2)

    RESULT_JSON.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_csv(results)
    print_summary(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
