# Birdfeeder Deployment Guide

This document describes how to deploy and operate Birdfeeder v0.5.0.

Birdfeeder consists of three application services:

- `birdfeeder`
- `birdfeeder-web`
- `birdfeeder-retention`

All services use the same locally built Docker image.

Object detection and species classification are provided by a separately deployed CoralAPI service running on a Google Coral Edge TPU.

## Architecture

```text
RTSP Cameras
      |
      v
birdfeeder
      |
      v
CoralAPI
      |
      v
Google Coral Edge TPU

birdfeeder
      |
      v
/srv/birdfeeder
      |
      +--> birdfeeder-web
      |
      +--> birdfeeder-retention
```

Enabled cameras are processed sequentially.

Camera configuration is described in:

- CAMERAS.md

Coral integration is described in:

- CORAL.md

## Services

### birdfeeder

Runs:

```text
python /app/app.py
```

Responsibilities:

- capture RTSP snapshots
- perform bird detection
- perform species classification
- store observations
- maintain temporary working files

### birdfeeder-web

Runs:

```text
python /app/web.py
```

Provides:

- dashboard
- observation gallery
- observation details
- camera statistics
- storage statistics
- health endpoint
- manual observation deletion

### birdfeeder-retention

Runs:

```text
python /app/retention.py --delete --loop
```

Provides:

- automatic retention processing
- accepted observation cleanup
- rejected observation cleanup
- periodic retention execution

## Environment Configuration

Create a local configuration:

```bash
cp .env.example .env
nano .env
```

The complete camera reference configuration can be found in:

```text
.env.example
```

The complete camera configuration model is documented in:

```text
docs/CAMERAS.md
```

Important runtime settings:

```env
CORAL_API_URL=http://127.0.0.1:8001

DETECTION_THRESHOLD=0.30
CLASSIFICATION_THRESHOLD=0.30
CLASSIFICATION_MARGIN=0.10

RUN_ONCE=false
INTERVAL_SECONDS=5

RETENTION_ACCEPTED_DAYS=365
RETENTION_REJECTED_DAYS=30
RETENTION_INTERVAL_DAYS=1
```

Do not commit the local `.env` file.

## Persistent Storage

Birdfeeder stores all observation data below:

```text
/srv/birdfeeder
```

Current directory structure:

```text
/srv/birdfeeder/
├── accepted/
│   ├── snapshots/
│   ├── crops/
│   └── json/
├── rejected/
│   ├── snapshots/
│   ├── crops/
│   └── json/
└── working/
```

Each observation consists of:

```text
1 JSON record
1 full snapshot
1 bird crop
```

Accepted and rejected observations are stored separately.

## Validation

Validate Python files:

```bash
python3 -m py_compile \
  app.py \
  web.py \
  stats.py \
  retention.py
```

Validate translations:

```bash
python3 -m json.tool translations/ui.json >/dev/null
python3 -m json.tool translations/birds.json >/dev/null
```

Validate Compose:

```bash
docker compose config --quiet
```

Check whitespace issues:

```bash
git diff --check
```

## Build

Build the shared image:

```bash
docker compose build birdfeeder
```

Image:

```text
birdfeeder:local
```

The web and retention services reuse the same image.

## Start Services

Start all services:

```bash
docker compose up -d
```

Or explicitly:

```bash
docker compose up -d \
  birdfeeder \
  birdfeeder-web \
  birdfeeder-retention
```

After code changes:

```bash
docker compose build birdfeeder

docker compose up -d --force-recreate \
  birdfeeder \
  birdfeeder-web \
  birdfeeder-retention
```

## Monitoring

Container status:

```bash
docker compose ps
```

Main application log:

```bash
docker compose logs -f --tail=100 -t birdfeeder
```

Web service log:

```bash
docker compose logs -f --tail=100 -t birdfeeder-web
```

Retention log:

```bash
docker compose logs -f --tail=100 -t birdfeeder-retention
```

Expected startup messages include:

```text
Configured cameras: ...
Enabled cameras: ...
Multi-camera runtime: sequential
```

## Web Interface

Default URL:

```text
http://SERVER-IP:8080
```

The dashboard provides:

- total observations
- accepted observations
- uncertain observations
- acceptance rate
- observations today
- latest observation
- storage usage
- camera statistics

Observation detail pages provide:

- snapshot
- crop
- classifier results
- detector results
- decision values

Observations can be deleted after a separate confirmation step.

## Retention

Review retention logs:

```bash
docker compose logs --tail=100 birdfeeder-retention
```

Dry run:

```bash
docker compose run --rm birdfeeder \
  python /app/retention.py
```

Apply immediately:

```bash
docker compose run --rm birdfeeder \
  python /app/retention.py --delete
```

Retention always deletes:

```text
snapshot
crop
JSON metadata
```

as one logical observation.

## Backup

Recommended backup targets:

```text
/srv/docker/compose/birdfeeder
/srv/birdfeeder
```

Example:

```bash
mkdir -p /srv/backups/birdfeeder

tar -czf \
  "/srv/backups/birdfeeder/birdfeeder-$(date +%Y%m%d-%H%M).tar.gz" \
  /srv/docker/compose/birdfeeder \
  /srv/birdfeeder
```

## Troubleshooting

### Camera capture issues

Test the RTSP stream directly with FFmpeg:

```bash
ffmpeg \
  -hide_banner \
  -loglevel error \
  -rtsp_transport tcp \
  -i 'rtsp://camera-user:camera-password@camera-ip:554/stream' \
  -frames:v 1 \
  -y \
  camera-test.jpg
```

### CoralAPI unavailable

```bash
docker ps --filter name=coralapi
docker logs --tail=100 coralapi
```

### Statistics return zero

Run statistics inside Compose:

```bash
docker compose run --rm birdfeeder \
  python /app/stats.py
```

### Port already in use

```bash
sudo ss -ltnp | grep ':8080'
```

## Release Checklist

Before creating a release:

- Python files compile successfully
- translations are valid JSON
- Compose configuration validates
- all three services start successfully
- enabled cameras are processed
- CoralAPI inference works
- WebUI is reachable
- retention works as expected
- dashboard statistics are plausible
- `.env` is not tracked by Git

## Related Documentation

- CAMERAS.md
- CORAL.md
- README.md
