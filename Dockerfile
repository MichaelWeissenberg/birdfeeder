FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pillow \
    requests

WORKDIR /app

COPY app.py /app/app.py

CMD ["python", "/app/app.py"]
