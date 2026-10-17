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
                            <a href="{{ observation.detail_url }}">
                                <img src="{{ observation.image }}" alt="{{ observation.label }}">
                            </a>
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


DETAIL_TEMPLATE = """
!doctype html>
<html lang="{{ language }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ ui_text.detail_title }} - {{ ui_text.page_title }}</title>
    <style>
        :root {
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            --green: #315c45;
            --green-light: #e9f1ec;
            --background: #f4f2ec;
            --card: #ffffff;
            --text: #26332b;
            --muted: #6e786f;
            --border: #dfe4df;
            --warning: #b87820;
        }
        * { box-sizing: border-box; }
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
            opacity: .85;
        }

        main {
            width: min(1100px, calc(100% - 2rem));
            margin: 2rem auto 4rem;
        }

        .back-link {
            display: inline-block;
            margin-bottom: 1.5rem;
            color: var(--green);
            font-weight: 700;
            text-decoration: none;
        }

        .back-link:hover {
            text-decoration: underline;
        }

        .detail-header {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .detail-header h2 {
            margin: 0;
            font-size: 1.8rem;
        }

        .status-badge {
            padding: .5rem .75rem;
            border-radius: 999px;
            background: var(--green-light);
            color: var(--green);
            font-weight: 800;
        }

        .status-badge.uncertain {
            background: #fff8ec;
            color: #8a5a19;
        }

        .image-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .panel {
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--card);
            box-shadow: 0 8px 24px rgb(0 0 0 / 5%);
        }

        .panel h3 {
            margin: 0;
            padding: 1rem 1.25rem;
            font-size: 1rem;
        }

        .panel img {
            display: block;
            width: 100%;
            aspect-ratio: 4 / 3;
            object-fit: contain;
            background: #dfe4df;
        }

        .no-image {
            padding: 3rem 1.5rem;
            color: var(--muted);
            text-align: center;
        }

        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1.25rem;
        }

        .section {
            padding: 1.25rem;
            border: 1px solid var(--border);
            border-radius: 1rem;
            background: var(--card);
        }

        .section h2 {
            margin: 0 0 1rem;
            font-size: 1.25rem;
        }

        .detail-list {
            display: grid;
            grid-template-columns: minmax(160px, .4fr) 1fr;
            gap: .75rem 1rem;
            margin: 0;
        }

        .detail-list dt {
            color: var(--muted);
        }

        .detail-list dd {
            margin: 0;
            word-break: break-word;
        }

        .decision-list dd {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .classifications {
            margin-top: 1.25rem;
        }

        .classification {
            display: grid;
            grid-template-columns: 32px 1fr auto;
            gap: .75rem;
            padding: .75rem 0;
            border-bottom: 1px solid var(--border);
        }

        .classification:last-child {
            border-bottom: 0;
        }

        .classification-name {
            font-weight: 700;
        }

        .scientific {
            color: var(--muted);
            font-size: .85rem;
            font-style: italic;
        }

        footer {
            padding: 1.5rem;
            text-align: center;
            color: var(--muted);
            font-size: .85rem;
        }


        .danger-zone {
            margin-top: 1.25rem;
            padding: 1.25rem;
            border: 1px solid #edcaca;
            border-radius: 1rem;
            background: #fffafa;
        }

        .danger-zone h2 {
            margin: 0 0 0.75rem;
            color: #a12b2b;
            font-size: 1.25rem;
        }

        .danger-zone p {
            margin: 0 0 1rem;
            color: var(--muted);
        }

        .danger-link {
            display: inline-block;
            padding: 0.7rem 1rem;
            border: 1px solid #a12b2b;
            border-radius: 0.7rem;
            background: #a12b2b;
            color: white;
            font-weight: 700;
            text-decoration: none;
        }

        .danger-link:hover {
            border-color: #7d2020;
            background: #7d2020;
        }

        @media (max-width: 750px) {
            .image-grid, .info-grid {
                grid-template-columns: 1fr;
            }
        }

    </style>
</head>


<body>
    <header>
        <h1>{{ ui_text.page_title }}</h1>
        <p>{{ ui_text.page_subtitle }}</p>
    </header>
    <main>
        <a class="back-link" href="{{ url_for('index', status=status, camera=camera, page=page) }}">
            &larr; {{ ui_text.detail_back }}
        </a>
        <div class="detail-header">
            <h2>{{ ui_text.detail_title }}</h2>
            <span class="status-badge{% if not observation.accepted %} uncertain{% endif %}">{{ observation.status_label }}</span>
        </div>
        <section class="image-grid">
            <div class="panel">
                <h3>{{ ui_text.detail_snapshot }}</h3>
                {% if observation.snapshot %}
                    <img src="{{ observation.snapshot }}" alt="{{ ui_text.detail_snapshot }}">
                {% else %}
                    <div class="no-image">{{ ui_text.detail_no_image }}</div>
                {% endif %}
            </div>
            <div class="panel">
                <h3>{{ ui_text.detail_crop }}</h3>
                {% if observation.crop %}
                    <img src="{{ observation.crop }}" alt="{{ ui_text.detail_crop }}">
                {% else %}
                    <div class="no-image">{{ ui_text.detail_no_image }}</div>
                {% endif %}
            </div>
        </section>
        <section class="info-grid">
            <div class="section">
                <h2>{{ ui_text.detail_information }}</h2>
                <dl class="detail-list">
                    <dt>{{ ui_text.detail_status }}</dt><dd>{{ observation.status_label }}</dd>
                    <dt>{{ ui_text.detail_camera }}</dt><dd>{{ observation.camera }}</dd>
                    <dt>{{ ui_text.detail_timestamp }}</dt><dd>{{ observation.timestamp }}</dd>
                    <dt>{{ ui_text.detail_event_id }}</dt><dd>{{ observation.event_id }}</dd>
                </dl>
            </div>
            <div class="section">
                <h2>{{ ui_text.detail_decision }}</h2>
                <dl class="detail-list decision-list">
                    <dt>{{ ui_text.detail_detector_score }}</dt><dd>{{ observation.detector_score }}</dd>
                    <dt>{{ ui_text.detail_top_score }}</dt><dd>{{ observation.top_score }}</dd>
                    <dt>{{ ui_text.detail_second_score }}</dt><dd>{{ observation.second_score }}</dd>
                    <dt>{{ ui_text.detail_margin }}</dt><dd>{{ observation.margin }}</dd>
                    <dt>{{ ui_text.detail_required_score }}</dt><dd>{{ observation.required_score }}</dd>
                    <dt>{{ ui_text.detail_required_margin }}</dt><dd>{{ observation.required_margin }}</dd>
                </dl>
            </div>
        </section>
        <section class="section classifications">
            <h2>{{ ui_text.detail_classifications }}</h2>
            {% if observation.classifications %}
                {% for classification in observation.classifications %}
                    <div class="classification">
                        <span>{{ loop.index }}</span>
                        <div>
                            <div class="classification-name">{{ classification.name }}</div>
                            {% if classification.scientific_name %}
                                <div class="scientific">{{ classification.scientific_name }}</div>
                            {% endif %}
                        </div>
                        <strong>{{ classification.score }}</strong>
                    </div>
                {% endfor %}
            {% endif %}
        </section>

        <section class="danger-zone">
            <h2>
                {{ ui_text.delete_danger_title }}
            </h2>

            <p>
                {{ ui_text.delete_danger_text }}
            </p>

            <a class="danger-link"
                href="{{ url_for('confirm_delete_observation',
                event_id=observation.event_id,
                status=status,
                camera=camera,
                page=page) }}"
            >
               {{ ui_text.delete_action }}
            </a>
        </section>

    </main>
    <footer>{{ ui_text.footer }}</footer>
</body>
</html>
"""

DELETE_CONFIRM_TEMPLATE = """
<!doctype html>
<html lang="{{ language }}">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>
        {{ ui_text.delete_confirm_title }}
        -
        {{ ui_text.page_title }}
    </title>

    <style>
        :root {
            font-family:
                Inter,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;

            --green: #315c45;
            --background: #f4f2ec;
            --card: #ffffff;
            --text: #26332b;
            --muted: #6e786f;
            --border: #dfe4df;
            --danger: #a12b2b;
            --danger-dark: #7d2020;
            --danger-light: #fff0f0;
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
            width: min(680px, calc(100% - 2rem));
            margin: 3rem auto 4rem;
        }

        .confirm-card {
            padding: 1.5rem;
            border: 1px solid #edcaca;
            border-radius: 1rem;
            background: var(--card);
            box-shadow: 0 8px 24px rgb(0 0 0 / 5%);
        }

        .confirm-card h2 {
            margin: 0 0 1rem;
            color: var(--danger);
        }

        .warning {
            margin: 1rem 0;
            padding: 1rem;
            border-left: 4px solid var(--danger);
            background: var(--danger-light);
        }

        .metadata {
            color: var(--muted);
            line-height: 1.6;
            word-break: break-word;
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-top: 1.5rem;
        }

        .button {
            display: inline-block;
            padding: 0.7rem 1rem;
            border: 1px solid var(--border);
            border-radius: 0.7rem;
            background: var(--card);
            color: var(--text);
            font: inherit;
            text-decoration: none;
            cursor: pointer;
        }

        .button:hover {
            border-color: var(--green);
        }

        .button-danger {
            border-color: var(--danger);
            background: var(--danger);
            color: white;
        }

        .button-danger:hover {
            border-color: var(--danger-dark);
            background: var(--danger-dark);
        }

        footer {
            padding: 1.5rem;
            text-align: center;
            color: var(--muted);
            font-size: 0.85rem;
        }
    </style>
</head>

<body>
    <header>
        <h1>{{ ui_text.page_title }}</h1>
        <p>{{ ui_text.page_subtitle }}</p>
    </header>

    <main>
        <section class="confirm-card">
            <h2>
                {{ ui_text.delete_confirm_title }}
            </h2>

            <p>
                {{ ui_text.delete_confirm_text }}
            </p>

            <div class="warning">
                {{ ui_text.delete_irreversible }}
            </div>

            <p class="metadata">
                {{ ui_text.detail_event_id }}:
                {{ observation.event_id }}
                <br>

                {{ ui_text.detail_camera }}:
                {{ observation.camera }}
                <br>

                {{ ui_text.detail_timestamp }}:
                {{ observation.timestamp }}
            </p>

            <div class="actions">
                <a
                    class="button"
                    href="{{
                        url_for('observation_detail',
                        event_id=observation.event_id,
                        status=status,
                        camera=camera,
                        page=page)
                    }}"
                >
                    {{ ui_text.delete_cancel }}
                </a>

                <form
                    method="post"
                    action="{{ url_for('delete_observation_route', event_id=observation.event_id) }}"
                >
                    <input
                        type="hidden"
                        name="status"
                        value="{{ status }}"
                    >

                    <input
                        type="hidden"
                        name="camera"
                        value="{{ camera }}"
                    >

                    <input
                        type="hidden"
                        name="page"
                        value="{{ page }}"
                    >

                    <button
                        class="button button-danger"
                        type="submit"
                    >
                        {{ ui_text.delete_confirm_action }}
                    </button>
                </form>
            </div>
        </section>
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

def format_percentage(value: object) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "–"

def build_observation_detail(
    record: dict,
) -> dict:
    detector = record.get("detector", {})
    decision = record.get("decision", {})
    classifications = record.get(
        "classifications",
        [],
    )

    formatted_classifications = []

    for classification in classifications:
        original_label = classification.get(
            "label",
            "",
        )

        if original_label == "background":
            display_name = ui_text["unknown_species"]
            scientific_name = None
        else:
            display_name = translate_bird_name(
                original_label
            )
            scientific_name = extract_scientific_name(
                original_label
            )

        formatted_classifications.append(
            {
                "name": display_name,
                "scientific_name": scientific_name,
                "score": format_percentage(
                    classification.get("score", 0)
                ),
            }
        )

    accepted = bool(
        record.get("accepted", False)
    )

    return {
        "event_id": record.get("event_id", ""),
        "camera": record.get(
            "camera",
            "unknown",
        ),
        "timestamp": format_timestamp(
            record.get("timestamp", "")
        ),
        "accepted": accepted,
        "status_label": (
            ui_text["dashboard_accepted"]
            if accepted
            else ui_text["dashboard_rejected"]
        ),
        "snapshot": safe_media_url(
            record.get("snapshot")
        ),
        "crop": safe_media_url(
            record.get("crop")
        ),
        "detector_score": format_percentage(
            detector.get("score", 0)
        ),
        "top_score": format_percentage(
            decision.get("top_score", 0)
        ),
        "second_score": format_percentage(
            decision.get("second_score", 0)
        ),
        "margin": format_percentage(
            decision.get("margin", 0)
        ),
        "required_score": format_percentage(
            decision.get("required_score", 0)
        ),
        "required_margin": format_percentage(
            decision.get("required_margin", 0)
        ),
        "classifications": formatted_classifications,
    }

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
                "detail_url": url_for(
                    "observation_detail",
                    event_id=record.get("event_id"),
                    status=status,
                    camera=camera,
                    page=page,
                ),
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


@app.get("/observations/<event_id>")
def observation_detail(
    event_id: str,
) -> str:
    loaded = load_observation(event_id)

    if loaded is None:
        abort(404)

    record, _ = loaded

    observation = build_observation_detail(
        record
    )

    status = request.args.get(
        "status",
        "all",
    )

    camera = request.args.get(
        "camera",
        "all",
    )

    page = request.args.get(
        "page",
        1,
        type=int,
    )

    return render_template_string(
        DETAIL_TEMPLATE,
        observation=observation,
        status=status,
        camera=camera,
        page=max(page, 1),
        language=LANGUAGE,
        ui_text=ui_text,
    )

@app.get("/observations/<event_id>/delete/confirm")
def confirm_delete_observation(
    event_id: str,
) -> str:
    loaded = load_observation(event_id)

    if loaded is None:
        abort(404)

    record, _ = loaded

    observation = build_observation_detail(
        record
    )

    status = request.args.get(
        "status",
        "all",
    )

    camera = request.args.get(
        "camera",
        "all",
    )

    page = request.args.get(
        "page",
        1,
        type=int,
    )

    return render_template_string(
        DELETE_CONFIRM_TEMPLATE,
        observation=observation,
        status=status,
        camera=camera,
        page=max(page, 1),
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
