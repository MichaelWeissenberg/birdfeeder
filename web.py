import json
import os
from pathlib import Path

from flask import Flask, abort, render_template_string, send_file

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

                            <p
                                class="confidence
                                {% if not observation.accepted %}
                                    uncertain
                                {% endif %}"
                            >
                                {% if observation.accepted %}
                                    Sicher erkannt:
                                {% else %}
                                    Unsicherer Vorschlag:
                                {% endif %}

                                {{ observation.score }}
                            </p>

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
        path = Path(path_value).resolve()
        relative_path = path.relative_to(DATA_DIR)
    except (OSError, ValueError):
        return None

    return f"/media/{relative_path.as_posix()}"


def format_timestamp(timestamp: str) -> str:
    if len(timestamp) != 15:
        return timestamp

    try:
        return (
            f"{timestamp[6:8]}.{timestamp[4:6]}.{timestamp[0:4]}"
            f" um {timestamp[9:11]}:{timestamp[11:13]} Uhr"
        )
    except IndexError:
        return timestamp


def read_observations(limit: int = 30) -> tuple[list[dict], int]:
    result_files = sorted(
        DATA_DIR.glob("*.json"),
        reverse=True,
    )

    observations: list[dict] = []

    for result_file in result_files:
        try:
            records = json.loads(
                result_file.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        if not isinstance(records, list):
            continue

        for record in records:
            classifications = record.get(
                "classifications",
                [],
            )

            top_result = (
                classifications[0]
                if classifications
                else {}
            )

            label = top_result.get(
                "label",
                ui_text["unknown_species"],
            )

            if label == "background":
                label = ui_text["unknown_species"]

            score = float(
                top_result.get(
                    "score",
                    0,
                )
            )

            observations.append(
                {
                    "timestamp": format_timestamp(
                        record.get(
                            "timestamp",
                            result_file.stem,
                        )
                    ),
                    "accepted": bool(
                        record.get(
                            "accepted",
                            False,
                        )
                    ),
                    "label": label,
                    "score": f"{score:.1%}",
                    "image": safe_media_url(
                        record.get("crop")
                    ),
                }
            )

            if len(observations) >= limit:
                return observations, len(result_files)

    return observations, len(result_files)


@app.get("/")
def index() -> str:
    observations, result_count = read_observations()

    return render_template_string(
        PAGE_TEMPLATE,
        observations=observations,
        result_count=result_count,
        language=LANGUAGE,
        ui_text=ui_text
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
