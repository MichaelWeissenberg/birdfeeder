import json
import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)

from stats import build_stats

LANGUAGE = os.getenv(
    "LANGUAGE",
    "en"
).lower()

SUPPORTED_LANGUAGES = {
    "en",
    "de",
}

if LANGUAGE not in SUPPORTED_LANGUAGES:
    LANGUAGE = "en"

with open(
    "translations/ui.json",
    encoding="utf-8",
) as ui_text_file:
    ui_translations = json.load(ui_text_file)

ui_text = ui_translations.get(
    LANGUAGE,
    ui_translations["en"],
)

with open(
    "translations/birds.json",
    encoding="utf-8",
) as bird_names_file:
    bird_translations = json.load(
        bird_names_file
    )

bird_names = bird_translations.get(
    LANGUAGE,
    bird_translations["en"],
)

def extract_scientific_name(
    label: str,
) -> str:
    return label.split(" (")[0].strip()

def translate_bird_name(
    label: str,
) -> str:
    scientific_name = extract_scientific_name(
        label
    )

    return bird_names.get(
        scientific_name,
        scientific_name,
    )

DATA_DIR = Path(
    os.getenv("DATA_DIR", "/data")
).resolve()

WEB_HOST = os.getenv(
    "WEB_HOST",
    "0.0.0.0",
)

WEB_PORT = int(
    os.getenv(
        "WEB_PORT",
        "8080",
    )
)

app = Flask(__name__)

def resolve_data_path(path_value: str) -> Path:
    path = (DATA_DIR / path_value).resolve()

    try:
        path.relative_to(DATA_DIR)
    except ValueError as exc:
        raise ValueError(
            f"Pfad liegt außerhalb von DATA_DIR: {path_value}"
        ) from exc

    return path

def find_observation_file(
    event_id: str,
) -> Path | None:
    if not event_id:
        return None

    accepted_file = (
        DATA_DIR
        / "accepted"
        / "json"
        / f"{event_id}.json"
    )

    rejected_file = (
        DATA_DIR
        / "rejected"
        / "json"
        / f"{event_id}.json"
    )

    for json_path in (
        accepted_file,
        rejected_file,
    ):
        if json_path.is_file():
            return json_path

    return None

def load_observation(
    event_id: str,
) -> tuple[dict, Path] | None:
    json_path = find_observation_file(event_id)

    if json_path is None:
        return None

    try:
        record = json.loads(
            json_path.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(record, dict):
        return None

    if record.get("schema_version") != 1:
        return None

    if record.get("event_id") != event_id:
        return None

    return record, json_path

def delete_observation(
    event_id: str,
) -> bool:
    loaded = load_observation(event_id)

    if loaded is None:
        return False

    record, json_path = loaded

    referenced_paths = []

    for field_name in (
        "snapshot",
        "crop",
    ):
        path_value = record.get(field_name)

        if not isinstance(path_value, str):
            continue

        try:
            referenced_path = resolve_data_path(
                path_value
            )
        except ValueError:
            continue

        referenced_paths.append(
            referenced_path
        )

    for referenced_path in referenced_paths:
        referenced_path.unlink(
            missing_ok=True
        )

    # Metadaten bewusst zuletzt löschen.
    json_path.unlink(
        missing_ok=True
    )

    return True

PAGE_TEMPLATE = """
<!doctype html>
<html lang="{{ language }}">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <meta
        http-equiv="refresh"
        content="30"
    >

    <title>{{ ui_text.page_title }}</title>

    <style>
        :root {
            color-scheme: light;
            font-family:
                Inter,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;

            --green: #315c45;
            --green-light: #e9f1ec;
            --background: #f4f2ec;
            --card: #ffffff;
            --text: #26332b;
            --muted: #6e786f;
            --border: #dfe4df;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: var(--background);
            color: var(--text);
        }

        header {
            padding: 2.5rem 1.25rem 2rem;
            text-align: center;
            background: var(--green);
            color: white;
        }

        header h1 {
            margin: 0;
            font-size: clamp(2rem, 6vw, 3.5rem);
        }

        header p {
            margin: 0.75rem 0 0;
            opacity: 0.85;
        }

        main {
            width: min(1100px, calc(100% - 2rem));
            margin: 2rem auto 4rem;
        }

        .status {
            margin-bottom: 1.5rem;
            padding: 1rem 1.25rem;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--green-light);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            padding: 1.25rem;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--card);
            box-shadow: 0 8px 24px rgb(0 0 0 / 5%);
        }

        .stat-value {
            margin: 0;
            color: var(--green);
            font-size: 2rem;
            font-weight: 800;
        }

        .stat-label {
            margin: 0.25rem 0 0;
            color: var(--muted);
            font-size: 0.9rem;
        }

        .section-title {
            margin: 2rem 0 1rem;
            font-size: 1.35rem;
        }

        .camera-grid {
            display: grid;
            grid-template-columns: repeat(
                auto-fit,
                minmax(240px, 1fr)
            );
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .camera-card {
            padding: 1rem 1.25rem;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--card);
        }

        .camera-name {
            margin: 0 0 0.5rem;
            font-weight: 700;
        }

        .camera-stats {
            margin: 0;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }

        @media (max-width: 800px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 480px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }

        .grid {
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.25rem;
        }

        .card {
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--card);
            box-shadow: 0 8px 24px rgb(0 0 0 / 6%);
        }

        .card img {
            display: block;
            width: 100%;
            aspect-ratio: 4 / 3;
            object-fit: cover;
            background: #dfe4df;
        }

        .content {
            padding: 1.25rem;
        }

        .content h2 {
            margin: 0;
            font-size: 1.35rem;
        }

        .confidence {
            margin: 0.4rem 0 0;
            color: var(--green);
            font-weight: 700;
        }

        .scientific-name {
            margin: 0.2rem 0 0;
            color: var(--muted);
            font-size: 0.9rem;
            font-style: italic;
        }

        .possible-match {
            display: grid;
            gap: 0.15rem;
            margin: 0.75rem 0 0;
            padding: 0.65rem 0.75rem;
            border-left: 3px solid #b87820;
            background: #fff8ec;
            font-size: 0.9rem;
        }

        .possible-match-label {
            color: var(--muted);
            font-size: 0.8rem;
        }

        .possible-match-scientific-name {
            color: var(--muted);
            font-size: 0.8rem;
            font-style: italic;
        }

        .possible-match-score {
            color: #8a5a19;
            font-size: 0.8rem;
            font-weight: 700;
        }

        .time {
            margin: 0.75rem 0 0;
            color: var(--muted);
            font-size: 0.9rem;
        }

        .uncertain {
            color: #8a5a19;
        }

        .empty {
            padding: 3rem 1.5rem;
            border: 1px dashed var(--border);
            border-radius: 1rem;
            background: var(--card);
            text-align: center;
        }

        footer {
            padding: 1.5rem;
            text-align: center;
            color: var(--muted);
            font-size: 0.85rem;
        }

        .filters {
            display: flex;
            flex-wrap: wrap;
            align-items: end;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding: 1rem 1.25rem;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--card);
        }

        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .filter-label {
            color: var(--muted);
            font-size: 0.85rem;
            font-weight: 600;
        }

        .filter-buttons {
            display: flex;
            gap: 0.4rem;
        }

        .filter-button,
        .pagination-button {
            display: inline-block;
            padding: 0.6rem 0.9rem;
            border: 1px solid var(--border);
            border-radius: 0.7rem;
            background: var(--card);
            color: var(--text);
            text-decoration: none;
        }

        .filter-button:hover,
        .pagination-button:hover {
            border-color: var(--green);
        }

        .filter-button.active {
            border-color: var(--green);
            background: var(--green);
            color: white;
        }

        .filter-select {
            min-width: 180px;
            padding: 0.6rem 0.75rem;
            border: 1px solid var(--border);
            border-radius: 0.7rem;
            background: var(--card);
            color: var(--text);
        }

        .pagination {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            margin: 2rem 0;
        }

        .pagination-info {
            color: var(--muted);
        }

        .pagination-button.disabled {
            opacity: 0.4;
            pointer-events: none;
        }

    </style>
</head>

<body>
    <header>
        <h1>{{ ui_text.page_title }}</h1>
        <p>{{ ui_text.page_subtitle }}</p>
    </header>

    <main>
        <div class="status">
            {{ result_count }} {{ ui_text.status_results }}
            {{ ui_text.status_autorefresh }}
        </div>

        <section class="stats-grid">
            <div class="stat-card">
                <p class="stat-value">
                    {{ statistics.total }}
                </p>
                <p class="stat-label">
                    {{ ui_text.dashboard_total }}
                </p>
            </div>

            <div class="stat-card">
                <p class="stat-value">
                    {{ statistics.accepted }}
                </p>
                <p class="stat-label">
                    {{ ui_text.dashboard_accepted }}
                </p>
            </div>

            <div class="stat-card">
                <p class="stat-value">
                    {{ statistics.rejected }}
                </p>
                <p class="stat-label">
                    {{ ui_text.dashboard_rejected }}
                </p>
            </div>

            <div class="stat-card">
                <p class="stat-value">
                    {{ statistics.acceptance_rate }} %
                </p>
                <p class="stat-label">
                    {{ ui_text.dashboard_acceptance_rate }}
                </p>
            </div>
        </section>


        {% if statistics.cameras %}
            <h2 class="section-title">
                {{ ui_text.dashboard_cameras }}
            </h2>

            <section class="camera-grid">
                {% for camera, values in statistics.cameras.items() %}
                    <div class="camera-card">
                        <p class="camera-name">
                            {{ camera }}
                        </p>

                        <p class="camera-stats">
                            {{ values.total }}
                            {{ ui_text.dashboard_camera_total }}
                            <br>

                            {{ values.accepted }}
                            {{ ui_text.dashboard_camera_accepted }}
                            ·
                            {{ values.rejected }}
                            {{ ui_text.dashboard_camera_rejected }}
                            <br>

                            {{ ui_text.dashboard_acceptance_rate }}:
                            {{ values.acceptance_rate }} %
                        </p>
                    </div>
                {% endfor %}
            </section>
        {% endif %}

        <h2 class="section-title">
            {{ ui_text.dashboard_latest }}
        </h2>

        <div class="filters">

            <div class="filter-group">
                <span class="filter-label">
                    {{ ui_text.filter_status }}
                </span>

                <div class="filter-buttons">
                    <a
                        class="filter-button{% if status == 'all' %} active{% endif %}"
                        href="{{ url_for('index', status='all', camera=camera, page=1) }}"
                    >
                        {{ ui_text.filter_all }}
                    </a>

                    <a
                        class="filter-button{% if status == 'accepted' %} active{% endif %}"
                        href="{{ url_for('index', status='accepted', camera=camera, page=1) }}"
                    >
                        {{ ui_text.filter_accepted }}
                    </a>

                    <a
                        class="filter-button{% if status == 'rejected' %} active{% endif %}"
                        href="{{ url_for('index', status='rejected', camera=camera, page=1) }}"
                    >
                        {{ ui_text.filter_rejected }}
                    </a>
                </div>

            </div>

            <div class="filter-group">
                <label
                    class="filter-label"
                    for="camera-filter"
                >
                    {{ ui_text.filter_camera }}
                </label>

                <select
                    id="camera-filter"
                    class="filter-select"
                    onchange="
                        window.location.href =
                            '?status={{ status }}&camera='
                            + encodeURIComponent(this.value)
                            + '&page=1';
                    "
                >
                    <option
                        value="all"
                        {% if camera == 'all' %}selected{% endif %}
                    >
                        {{ ui_text.filter_all_cameras }}
                    </option>

                    {% for camera_name in statistics.cameras %}
                        <option
                            value="{{ camera_name }}"
                            {% if camera == camera_name %}selected{% endif %}
                        >
                            {{ camera_name }}
                        </option>
                    {% endfor %}
                </select>
            </div>

        </div>

        {% if observations %}
            <section class="grid">
                {% for observation in observations %}
                    <article class="card">
                        {% if observation.image %}
                            <img src="{{ observation.image }}">
                        {% endif %}

                        <div class="content">
                            <h2>
                                {{ observation.label }}
                            </h2>

                            {% if observation.scientific_name %}
                                <p class="scientific-name">
                                    {{ observation.scientific_name }}
                                </p>
                            {% endif %}

                            {% if observation.possible_match %}
                                <div class="possible-match">
                                    <span class="possible-match-label">
                                        {{ ui_text.possible_match }}
                                    </span>

                                    <strong>
                                        {{ observation.possible_match }}
                                    </strong>

                                    {% if observation.possible_match_scientific_name %}
                                        <span class="possible-match-scientific-name">
                                            {{ observation.possible_match_scientific_name }}
                                        </span>
                                    {% endif %}

                                    {% if observation.possible_match_score %}
                                        <span class="possible-match-score">
                                            {{ ui_text.uncertain_detection }}
                                            {{ observation.possible_match_score }}
                                        </span>
                                    {% endif %}
                                </div>
                            {% endif %}

                            {% if not observation.possible_match %}
                                <p
                                    class="confidence
                                    {% if not observation.accepted %}
                                        uncertain
                                    {% endif %}"
                                >
                                    {% if observation.accepted %}
                                        {{ ui_text.accepted_detection }}
                                    {% else %}
                                        {{ ui_text.uncertain_detection }}
                                    {% endif %}

                                    {{ observation.score }}
                                </p>
                            {% endif %}

                            <p class="time">
                                {{ observation.timestamp }}
                            </p>
                        </div>
                    </article>
                {% endfor %}
            </section>
        {% else %}
            <div class="empty">
                <h2>{{ ui_text.no_bird_detected }}</h2>
                <p>
                    {{ ui_text.waiting_for_first_observation }}
                </p>
            </div>
        {% endif %}

        {% if total_pages > 1 %}
            <nav class="pagination">
                {% if page > 1 %}
                    <a
                        class="pagination-button"
                        href="{{ url_for('index', status=status, camera=camera, page=page - 1) }}"
                    >
                        &larr; {{ ui_text.pagination_previous }}
                    </a>
                {% else %}
                    <span class="pagination-button disabled">
                        &larr; {{ ui_text.pagination_previous }}
                    </span>
                {% endif %}

                <span class="pagination-info">
                    {{ ui_text.pagination_page }}
                    {{ page }}
                    {{ ui_text.pagination_of }}
                    {{ total_pages }}
                </span>

                {% if page < total_pages %}
                    <a
                        class="pagination-button"
                        href="{{ url_for('index', status=status, camera=camera, page=page + 1) }}"
                    >
                        {{ ui_text.pagination_next }} &rarr;
                    </a>
                {% else %}
                    <span class="pagination-button disabled">
                        {{ ui_text.pagination_next }} &rarr;
                    </span>
                {% endif %}
            </nav>
        {% endif %}

    </main>

    <footer>
        {{ ui_text.footer }}
    </footer>
</body>
</html>
"""


def safe_media_url(path_value: str | None) -> str | None:
    if not path_value:
        return None

    try:
        path = (DATA_DIR / path_value).resolve()
        relative_path = path.relative_to(DATA_DIR)
    except (OSError, ValueError):
        return None

    return f"/media/{relative_path.as_posix()}"

def format_timestamp(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return timestamp

    return dt.strftime(ui_text["datetime_format"])

def read_observations(
    page: int = 1,
    per_page: int = 24,
    status: str = "all",
    camera: str = "all",
):
    result_files = sorted(
        list(
            (DATA_DIR / "accepted" / "json").glob("*.json")
        )
        + list(
            (DATA_DIR / "rejected" / "json").glob("*.json")
        ),
        reverse=True,
    )

    observations = []

    for result_file in result_files:
        try:
            record = json.loads(
                result_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(record, dict):
            continue

        if record.get("schema_version") != 1:
            continue

        # Status filtern
        accepted = bool(record.get("accepted", False))

        if status == "accepted" and not accepted:
            continue

        if status == "rejected" and accepted:
            continue

        # Kamera filtern
        record_camera = record.get("camera", "unknown")

        if camera != "all" and record_camera != camera:
            continue

        classifications = record.get(
            "classifications",
            [],
        )

        top_result = (
            classifications[0]
            if classifications
            else {}
        )

        original_label = top_result.get(
            "label",
            "background",
        )

        score = float(
            top_result.get(
                "score",
                0,
            )
        )

        possible_match = None
        possible_match_scientific_name = None
        possible_match_score = None

        if original_label == "background":
            label = ui_text["unknown_species"]
            scientific_name = None

            best_species_result = next(
                (
                    classification
                    for classification in classifications
                    if classification.get("label")
                    != "background"
                ),
                None,
            )

            if best_species_result:
                possible_match_original_label = (
                    best_species_result.get(
                        "label",
                        "",
                    )
                )

                possible_match_scientific_name = (
                    extract_scientific_name(
                        possible_match_original_label
                    )
                )

                possible_match = translate_bird_name(
                    possible_match_original_label
                )

                possible_match_score = (
                    f"{float(best_species_result.get('score', 0)):.1%}"
                )

        else:
            scientific_name = extract_scientific_name(
                original_label
            )

            label = translate_bird_name(
                original_label
            )

        observations.append(
            {
                "event_id": record.get("event_id"),
                "camera": record_camera,
                "timestamp": format_timestamp(
                    record.get("timestamp", "")
                ),
                "accepted": accepted,
                "label": label,
                "scientific_name": scientific_name,
                "score": f"{score:.1%}",
                "possible_match": possible_match,
                "possible_match_scientific_name": (
                    possible_match_scientific_name
                ),
                "possible_match_score": (
                    possible_match_score
                ),
                "image": safe_media_url(
                    record.get("crop")
                ),
            }
        )

    # Wichtig: erst nach der Filterung zählen
    total = len(observations)

    # Ungültige Werte abfangen
    page = max(page, 1)
    per_page = max(per_page, 1)

    total_pages = max(
        1,
        (total + per_page - 1) // per_page,
    )

    # Seite oberhalb der letzten Seite abfangen
    page = min(page, total_pages)

    start = (page - 1) * per_page
    end = start + per_page

    observations = observations[start:end]

    return observations, total, total_pages, page

@app.get("/")
def index() -> str:
    page = request.args.get(
        "page",
        1,
        type=int,
    )

    status = request.args.get(
        "status",
        "all",
    )

    camera = request.args.get(
        "camera",
        "all",
    )

    observations, result_count, total_pages, page = (
        read_observations(
            page=page,
            per_page=24,
            status=status,
            camera=camera,
        )
    )

    statistics = build_stats()

    return render_template_string(
        PAGE_TEMPLATE,
        observations=observations,
        result_count=result_count,
        statistics=statistics,
        page=page,
        total_pages=total_pages,
        status=status,
        camera=camera,
        language=LANGUAGE,
        ui_text=ui_text,
    )

@app.post("/observations/<event_id>/delete")
def delete_observation_route(
    event_id: str,
):
    deleted = delete_observation(
        event_id
    )

    if not deleted:
        abort(404)

    status = request.form.get(
        "status",
        "all",
    )

    camera = request.form.get(
        "camera",
        "all",
    )

    page = request.form.get(
        "page",
        1,
        type=int,
    )

    return redirect(
        url_for(
            "index",
            status=status,
            camera=camera,
            page=max(page, 1),
        )
    )

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "data_directory": str(DATA_DIR),
    }


@app.get("/media/<path:relative_path>")
def media(relative_path: str):
    requested_path = (
        DATA_DIR / relative_path
    ).resolve()

    try:
        requested_path.relative_to(DATA_DIR)
    except ValueError:
        abort(403)

    if not requested_path.is_file():
        abort(404)

    return send_file(requested_path)


if __name__ == "__main__":
    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
       debug=False,
        use_reloader=False,
    )
