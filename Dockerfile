FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/requirements.txt

WORKDIR /app

COPY app.py /app/app.py
COPY benchmark_species.py /app/benchmark_species.py
COPY web.py /app/web.py
COPY translations /app/translations

CMD ["python", "/app/app.py"]
