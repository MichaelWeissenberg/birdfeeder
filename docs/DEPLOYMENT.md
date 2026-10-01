# Birdfeeder Deployment Guide

This document describes how to deploy Birdfeeder with Docker Compose.

Birdfeeder consists of two application services:

- `birdfeeder` captures camera images and processes observations.
- `birdfeeder-web` displays stored observations through a web interface.

Both services use the same locally built Docker image.

Bird detection and species classification are performed by a separately
deployed CoralAPI service.

## Architecture

```text
RTSP camera
    |
    v
birdfeeder
    |
    | HTTP inference requests
    v
CoralAPI
    |
    v
Google Coral Edge TPU

birdfeeder
    |
    | JSON records, snapshots, and crops
    v
Persistent data directory
    |
    v
birdfeeder-web
    |
    v
Web browser
```

## Service responsibilities

### birdfeeder

The `birdfeeder` service runs:

```text
/app/app.py
```

It is responsible for:

- capturing images from an RTSP camera
- sending snapshots to CoralAPI for object detection
- selecting detections labelled as `bird`
- generating padded bird crops
- sending crops to CoralAPI for species classification
- evaluating prediction confidence
- storing JSON observation records
- storing full snapshots and bird crops

### birdfeeder-web

The `birdfeeder-web` service runs:

```text
/app/web.py
```

It is responsible for:

- reading observation JSON files
- displaying recent observations
- displaying bird crops
- showing classification scores
- distinguishing accepted and uncertain predictions
- serving a health endpoint
- serving stored media files

### CoralAPI

CoralAPI is deployed separately.

It is responsible for:

- accessing the Google Coral Edge TPU
- loading Edge-TPU-compatible models
- running object detection
- running bird species classification
- returning inference results through an HTTP API

See [Coral Edge TPU Integration](CORAL.md) for additional information.

## Prerequisites

The host requires:

- a Linux operating system
- Docker Engine
- the Docker Compose plugin
- Git
- access to an RTSP-compatible camera
- a running CoralAPI instance
- a supported Google Coral Edge TPU
- compatible detection and classification models

The currently used models are:

```text
ssd_mobilenet_v2_coco_quant_postprocess_edgetpu
mobilenet_v2_1.0_224_inat_bird_quant_edgetpu
```

The model files are provided by CoralAPI and are not part of the Birdfeeder
repository.

## Camera requirements

The camera must provide an RTSP stream that is reachable from the Birdfeeder
host.

Before deployment, verify that FFmpeg can capture a valid image from the
camera.

See [Camera Configuration](CAMERAS.md) for manufacturer-specific examples and
troubleshooting.

## Recommended directory layout

The following layout is used by the reference deployment:

```text
/srv/
├── birdfeeder/
├── coralapi/
└── docker/
    └── compose/
        ├── birdfeeder/
        └── coralapi/
```

The Birdfeeder repository is located at:

```text
/srv/docker/compose/birdfeeder
```

Persistent observation data is stored at:

```text
/srv/birdfeeder
```

## Repository layout

```text
birdfeeder/
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── app.py
├── benchmark_species.py
├── docker-compose.yml
├── requirements.txt
├── web.py
└── docs/
    ├── CAMERAS.md
    ├── CORAL.md
    └── DEPLOYMENT.md
```

Some files shown above may be introduced as part of a later release.

## Clone the repository

Create or enter the parent directory:

```bash
cd /srv/docker/compose
```

Clone the repository:

```bash
git clone git@github.com:OWNER/birdfeeder.git
```

Enter the project directory:

```bash
cd birdfeeder
```

Replace `OWNER` with the GitHub account or organization that owns the
repository.

For a private repository, the host must have permission to access it.

## Environment configuration

Birdfeeder reads its runtime configuration from a local `.env` file.

Create the local file from the provided example:

```bash
cp .env.example .env
```

Edit the local configuration:

```bash
nano .env
```

At minimum, configure:

```env
CAMERA_URL=rtsp://camera-user:camera-password@camera-ip:554/stream
CORAL_API_URL=http://127.0.0.1:8001
```

The real `.env` file can contain camera credentials and must not be committed
to Git.

## Environment variables

### Camera

```env
CAMERA_URL=rtsp://camera-user:camera-password@camera-ip:554/stream
```

This variable is required.

It specifies the RTSP stream from which FFmpeg captures snapshots.

### CoralAPI

```env
CORAL_API_URL=http://127.0.0.1:8001
```

This variable specifies the CoralAPI base address.

The reference deployment runs CoralAPI on the same host and publishes it on
the loopback interface.

### Detection threshold

```env
DETECTION_THRESHOLD=0.30
```

This variable defines the minimum confidence required for object detection.

### Classification threshold

```env
CLASSIFICATION_THRESHOLD=0.30
```

This variable defines the minimum confidence required before a bird species
can be accepted.

### Classification margin

```env
CLASSIFICATION_MARGIN=0.10
```

This variable defines the minimum difference between the best and second-best
species predictions.

### Runtime mode

```env
RUN_ONCE=false
```

Available values:

```text
true  = process one image and then exit
false = continue processing images
```

### Analysis interval

```env
INTERVAL_SECONDS=5
```

This variable defines the minimum interval between processing cycles.

The actual time between cycle starts also depends on the time required for
snapshot capture, detection, cropping, and classification.

### Web interface

```env
WEB_HOST=0.0.0.0
WEB_PORT=8080
```

These values define the Flask bind address and listening port.

The current web service can also use its built-in defaults when these
variables are not explicitly passed to that service.

## Secret handling

The local `.env` file must remain untracked.

Recommended `.gitignore` rules:

```gitignore
# Local environment files
.env
.env.*
!.env.example
```

Verify that `.env` is ignored:

```bash
git check-ignore -v .env
```

Review all tracked files:

```bash
git ls-files
```

The output must not contain:

```text
.env
```

Do not print or publish the complete `.env` file because it can contain camera
credentials.

For deployments with stronger security requirements, use an appropriate
secret-management mechanism instead of plain environment variables.

## Create the persistent data directory

Create the host data directory:

```bash
sudo mkdir -p /srv/birdfeeder
```

Assign ownership to the user managing the deployment:

```bash
sudo chown "$(id -u):$(id -g)" /srv/birdfeeder
```

Create the initial subdirectories:

```bash
mkdir -p \
  /srv/birdfeeder/snapshots \
  /srv/birdfeeder/crops
```

The application can also create these two subdirectories automatically.

## Validate the camera connection

Before building the containers, test the RTSP stream directly.

Capture one image:

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

Verify the result:

```bash
file camera-test.jpg
ls -lh camera-test.jpg
```

Remove the temporary file:

```bash
rm camera-test.jpg
```

If FFmpeg cannot capture the image, resolve the camera connection before
starting Birdfeeder.

## Verify CoralAPI

Check whether the CoralAPI container is running:

```bash
docker ps --filter name=coralapi
```

Review its status:

```bash
docker inspect \
  --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' \
  coralapi
```

Review recent logs:

```bash
docker logs --tail 100 coralapi
```

Birdfeeder cannot perform detection or classification when CoralAPI is
unavailable.

## Docker image

The Dockerfile uses:

```text
python:3.12-slim-bookworm
```

The image installs:

- FFmpeg
- Flask
- Pillow
- Requests

The image contains:

- `app.py`
- `web.py`
- `benchmark_species.py`

The default image command is:

```text
python /app/app.py
```

The web service overrides the default command and runs:

```text
python /app/web.py
```

## Compose services

The Compose project defines two Birdfeeder services.

### Main service

The main service:

- builds the shared image
- uses host networking
- loads the local `.env` file
- mounts `/srv/birdfeeder` with write access
- runs `app.py`
- restarts unless deliberately stopped

### Web service

The web service:

- uses the shared image
- runs `web.py`
- mounts `/srv/birdfeeder` read-only
- publishes TCP port 8080
- restarts unless deliberately stopped

The read-only mount prevents the current web interface from modifying stored
observation data.

A future version with delete functionality will require a controlled write
mechanism and appropriate protection against unauthorized deletion.

## Validate the Compose file

Run:

```bash
docker compose config --quiet \
  && echo "OK: Compose configuration is valid"
```

If this command reports an error, correct the Compose configuration before
building or starting containers.

## Build Birdfeeder

Build the shared image through the service that contains the `build`
configuration:

```bash
docker compose build birdfeeder
```

The reference deployment names the resulting image:

```text
birdfeeder-atlas:local
```

The `birdfeeder-web` service does not have its own `build` section.

Running the following command can therefore report that there are no services
to build:

```bash
docker compose build birdfeeder-web
```

Always rebuild through:

```bash
docker compose build birdfeeder
```

## Start Birdfeeder

Start both services:

```bash
docker compose up -d \
  birdfeeder \
  birdfeeder-web
```

When replacing existing containers after a code change, use:

```bash
docker compose up -d \
  --force-recreate \
  birdfeeder \
  birdfeeder-web
```

## Verify container status

Run:

```bash
docker compose ps
```

Expected services:

```text
birdfeeder
birdfeeder-web
```

Both services should show an `Up` status.

The web service should publish:

```text
0.0.0.0:8080->8080/tcp
```

## Review application logs

Main service:

```bash
docker compose logs \
  --tail 100 \
  birdfeeder
```

Follow the main service logs:

```bash
docker compose logs \
  --tail 100 \
  -f \
  birdfeeder
```

Web service:

```bash
docker compose logs \
  --tail 100 \
  birdfeeder-web
```

Expected Birdfeeder messages include:

```text
Birdfeeder läuft im Dauerbetrieb.
Analyseintervall: 5.0 Sekunden
Erzeuge Kamerabild ...
Suche Vögel auf der Coral ...
```

## Web interface

Open the web interface using the host IP address:

```text
http://SERVER-IP:8080
```

The interface displays up to 30 recent observations.

Each observation can contain:

- a bird crop
- the top classification label
- the classification confidence
- the observation timestamp
- an accepted or uncertain status

The page automatically refreshes every 30 seconds.

## Health endpoint

Test the web application locally:

```bash
curl http://127.0.0.1:8080/health
```

Expected response structure:

```json
{
  "data_directory": "/data",
  "status": "ok"
}
```

The health endpoint confirms that the Flask application is responding.

It does not verify:

- camera availability
- CoralAPI availability
- Edge TPU availability
- successful inference
- available disk space

## Media endpoint

Stored crop images are available under:

```text
/media/crops/FILENAME.jpg
```

Test an existing crop:

```bash
curl -I \
  http://127.0.0.1:8080/media/crops/EXAMPLE-bird-1.jpg
```

A successful response contains:

```text
HTTP/1.1 200 OK
Content-Type: image/jpeg
```

The media route resolves requested files within the configured data directory
and rejects paths outside that directory.

## Persistent data

Birdfeeder stores observation data under:

```text
/srv/birdfeeder
```

The directory contains:

```text
/srv/birdfeeder/
├── YYYYMMDD-HHMMSS.json
├── crops/
│   └── YYYYMMDD-HHMMSS-bird-N.jpg
└── snapshots/
    └── YYYYMMDD-HHMMSS-full.jpg
```

### JSON records

Each JSON record contains:

- timestamp
- snapshot path
- crop path
- detector output
- classification results
- score comparison
- required thresholds
- accepted status

### Snapshots

When no bird is detected, the temporary full snapshot is deleted.

When at least one bird is detected, the full snapshot is retained.

### Crops

A separate crop is created for every detected bird in the snapshot.

## Current retention behavior

The current version does not automatically delete accepted observations.

Stored files can therefore grow over time.

Monitor storage usage:

```bash
du -sh /srv/birdfeeder
```

Count stored files:

```bash
find /srv/birdfeeder -type f | wc -l
```

Planned retention features include:

- configurable retention
- a default retention period of 90 days
- deletion of individual observations
- deletion through the web interface
- deletion of all files related to an observation
- storage usage information in the web interface

## Removing test data

Stop the main service first to prevent new files from being created during
cleanup:

```bash
docker compose stop birdfeeder
```

Remove JSON observation records:

```bash
rm -f /srv/birdfeeder/*.json
```

Remove snapshots:

```bash
rm -f /srv/birdfeeder/snapshots/*.jpg
```

Remove crops:

```bash
rm -f /srv/birdfeeder/crops/*.jpg
```

Verify:

```bash
find /srv/birdfeeder -type f | wc -l
```

Restart the main service:

```bash
docker compose start birdfeeder
```

Reload the web interface. It should display the empty-state message until a
new bird is detected.

## Updating Birdfeeder

Confirm that the working tree is clean:

```bash
git status
```

Fetch and integrate repository updates:

```bash
git pull --ff-only
```

Validate Python syntax:

```bash
python3 -m py_compile app.py
python3 -m py_compile web.py
```

Validate Compose:

```bash
docker compose config --quiet \
  && echo "OK: Compose configuration is valid"
```

Rebuild the shared image:

```bash
docker compose build birdfeeder
```

Recreate both services:

```bash
docker compose up -d \
  --force-recreate \
  birdfeeder \
  birdfeeder-web
```

Verify:

```bash
docker compose ps
docker compose logs --tail 50 birdfeeder
docker compose logs --tail 50 birdfeeder-web
```

## Confirm the deployed source version

The web service runs the copy of `web.py` contained in the Docker image.

After changing `web.py`, restarting an old container without rebuilding the
image does not deploy the changed file.

Compare the host file and container file:

```bash
sha256sum web.py
docker exec birdfeeder-web sha256sum /app/web.py
```

For `app.py`:

```bash
sha256sum app.py
docker exec birdfeeder sha256sum /app/app.py
```

Matching hashes confirm that the container contains the current source file.

## Restart behavior

Both Birdfeeder services use:

```yaml
restart: "unless-stopped"
```

Docker restarts the services after:

- a host restart
- a Docker daemon restart
- an unexpected container stop

A deliberately stopped container remains stopped until it is started again or
the applicable Docker restart behavior is triggered.

## Stop the services

Stop both containers without removing them:

```bash
docker compose stop \
  birdfeeder \
  birdfeeder-web
```

Start them again:

```bash
docker compose start \
  birdfeeder \
  birdfeeder-web
```

## Remove the containers

Remove the project containers:

```bash
docker compose down
```

The persistent data under `/srv/birdfeeder` remains present because it is
stored in a host directory.

## Backup recommendations

Back up the application repository:

```text
/srv/docker/compose/birdfeeder
```

Back up the persistent data:

```text
/srv/birdfeeder
```

Example archive:

```bash
mkdir -p /srv/backups/birdfeeder

tar -czf \
  "/srv/backups/birdfeeder/birdfeeder-$(date +%Y%m%d-%H%M).tar.gz" \
  /srv/docker/compose/birdfeeder \
  /srv/birdfeeder
```

Verify the archive:

```bash
ls -lh /srv/backups/birdfeeder
```

List archive contents without extracting:

```bash
tar -tzf \
  /srv/backups/birdfeeder/birdfeeder-YYYYMMDD-HHMM.tar.gz \
  | head
```

Protect backup archives because they can contain camera URLs or other local
configuration when the `.env` file is included.

## Restore overview

A basic restore requires:

1. restoring the repository directory
2. restoring the persistent data directory
3. reviewing the local `.env` file
4. confirming CoralAPI availability
5. validating the Compose configuration
6. rebuilding the Birdfeeder image
7. starting both services
8. verifying logs and web access

Example validation after restoring:

```bash
cd /srv/docker/compose/birdfeeder

docker compose config --quiet \
  && echo "OK: Compose configuration is valid"

docker compose build birdfeeder

docker compose up -d \
  birdfeeder \
  birdfeeder-web

docker compose ps
```

## Troubleshooting

### `No services to build`

Cause:

The `birdfeeder-web` service uses the shared image but does not define its own
build configuration.

Solution:

```bash
docker compose build birdfeeder
```

Then recreate the web service:

```bash
docker compose up -d \
  --force-recreate \
  birdfeeder-web
```

### Web interface contains old content

Cause:

The container can still contain an older image version.

Check:

```bash
sha256sum web.py
docker exec birdfeeder-web sha256sum /app/web.py
```

Rebuild and recreate:

```bash
docker compose build birdfeeder

docker compose up -d \
  --force-recreate \
  birdfeeder \
  birdfeeder-web
```

### Web interface runs but images are missing

Test a known image directly:

```bash
curl -I \
  http://127.0.0.1:8080/media/crops/EXAMPLE-bird-1.jpg
```

Check whether the file exists:

```bash
find /srv/birdfeeder/crops \
  -type f \
  -name '*.jpg' \
  | head
```

Check the web service logs:

```bash
docker compose logs \
  --tail 100 \
  birdfeeder-web
```

Inspect the data mount:

```bash
docker inspect birdfeeder-web
```

### Main service cannot capture images

Test the RTSP stream with FFmpeg.

Review:

```bash
docker compose logs \
  --tail 100 \
  birdfeeder
```

Check the configured camera variable without displaying unrelated secrets:

```bash
grep '^CAMERA_URL=' .env | sed 's#//.*@#//***:***@#'
```

### CoralAPI cannot be reached

Check:

```bash
docker ps --filter name=coralapi
docker logs --tail 100 coralapi
```

Review the configured base address:

```bash
grep '^CORAL_API_URL=' .env
```

See [Coral Edge TPU Integration](CORAL.md).

### Compose validation fails

Run the full configuration output:

```bash
docker compose config
```

Review:

- YAML indentation
- missing environment files
- duplicate keys
- invalid service properties
- unavailable bind-mounted paths

### Permission errors in the data directory

Inspect ownership:

```bash
ls -ld \
  /srv/birdfeeder \
  /srv/birdfeeder/snapshots \
  /srv/birdfeeder/crops
```

Correct ownership according to the user and container configuration used by
the deployment.

Do not apply broad permissions such as `chmod 777` as a general fix.

### Port 8080 is already in use

Identify the process:

```bash
sudo ss -ltnp | grep ':8080'
```

Either stop the conflicting service or change the published port in
`docker-compose.yml`.

## Network exposure

The reference deployment is intended for a trusted local network.

Before exposing the web interface outside the local network, add:

- authentication
- HTTPS
- a reverse proxy
- access restrictions
- protection for future delete operations
- appropriate logging
- secure secret management

Do not expose:

- the RTSP camera stream
- CoralAPI
- the Edge TPU device
- administrative delete operations

directly to the public internet.

## Planned improvements

Planned Version 2 features include:

- a documented `.env.example`
- Python dependency management through `requirements.txt`
- German common bird names
- a configurable 90-day retention policy
- deletion of individual observations through the web interface
- deletion of all observations through the web interface
- display of storage usage
- observation statistics
- improved public deployment documentation

## Related documentation

- [Camera Configuration](CAMERAS.md)
- [Coral Edge TPU Integration](CORAL.md)
- [Docker Compose environment variables](https://docs.docker.com/compose/how-tos/environment-variables/)
EOF

echo
echo "Created docs/DEPLOYMENT.md"
wc -l docs/DEPLOYMENT.md
git status --short
