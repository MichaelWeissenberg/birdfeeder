# Coral Edge TPU Integration

Birdfeeder uses a Google Coral Edge TPU to accelerate bird detection and
species classification.

The Birdfeeder application does not access the Edge TPU hardware directly.
All inference requests are sent over HTTP to a separately deployed CoralAPI
service.

## Architecture

```text
RTSP camera 1 ─┐
RTSP camera 2 ─┼─► Birdfeeder ──HTTP──► CoralAPI ──► Google Coral Edge TPU
RTSP camera N ─┘
```

Birdfeeder is responsible for:

- capturing snapshots from enabled RTSP cameras
- sending snapshots to CoralAPI for object detection
- selecting detections labelled as `bird`
- creating padded image crops
- sending the crops to CoralAPI for species classification
- evaluating classification confidence
- storing the resulting observations

CoralAPI is responsible for:

- accessing the Google Coral Edge TPU
- loading Edge-TPU-compatible models
- performing object detection
- performing species classification
- returning inference results through an HTTP API

## Sequential multi-camera processing

Birdfeeder processes enabled cameras sequentially.

For each camera, Birdfeeder completes:

```text
Snapshot capture
Detection request
Crop generation
Classification request
Observation storage
```

Only after the current camera has completed does Birdfeeder continue with the
next enabled camera.

Birdfeeder does not send concurrent inference requests to CoralAPI. This keeps
Coral TPU access predictable and avoids contention between multiple camera
pipelines.

A failure while processing one camera is logged without preventing the next
enabled camera from being processed.

## CoralAPI configuration

Configure the CoralAPI base URL in `.env`:

```env
CORAL_API_URL=http://127.0.0.1:8001
```

The reference deployment runs CoralAPI on the same host and publishes the
service only on the loopback interface.

Birdfeeder sends inference requests to:

```text
POST /v1/vision/detect
POST /v1/vision/classify
```

## Models

Birdfeeder currently requests the following CoralAPI models.

Object detection:

```text
ssd_mobilenet_v2_coco_quant_postprocess_edgetpu
```

Species classification:

```text
mobilenet_v2_1.0_224_inat_bird_quant_edgetpu
```

The model files are provided by CoralAPI and are not part of the Birdfeeder
repository.

## Detection workflow

Birdfeeder sends the complete camera snapshot to:

```text
/v1/vision/detect
```

Only detection results with the label:

```text
bird
```

are processed further.

The minimum detection confidence is configured with:

```env
DETECTION_THRESHOLD=0.30
```

Each selected detection is converted into a padded crop before species
classification.

## Classification workflow

Birdfeeder sends every bird crop to:

```text
/v1/vision/classify
```

CoralAPI returns up to five classification results.

Birdfeeder accepts a species classification only when:

- the best result is not `background`
- the best score meets `CLASSIFICATION_THRESHOLD`
- the difference between the best and second-best scores meets
  `CLASSIFICATION_MARGIN`

Example configuration:

```env
CLASSIFICATION_THRESHOLD=0.30
CLASSIFICATION_MARGIN=0.10
```

Results that do not meet both requirements are stored as uncertain
observations. They remain available in the WebUI for review.

## Verifying CoralAPI

Check whether the CoralAPI container is running:

```bash
docker ps --filter name=coralapi
```

Inspect the container state:

```bash
docker inspect \
  --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' \
  coralapi
```

Review recent logs:

```bash
docker logs --tail 100 coralapi
```

Review the configured address without displaying unrelated environment values:

```bash
grep '^CORAL_API_URL=' .env
```

## Verifying Birdfeeder inference

Follow the Birdfeeder logs:

```bash
docker compose logs -f --tail=100 -t birdfeeder
```

Expected messages include:

```text
[tuya] Starte Verarbeitung.
Erzeuge Kamerabild für tuya ...
Suche Vögel auf der Coral ...
Kein Vogel erkannt.

[tapo_c200] Starte Verarbeitung.
Erzeuge Kamerabild für tapo_c200 ...
Suche Vögel auf der Coral ...
```

The exact camera IDs depend on the local camera configuration.

## Timeouts

Birdfeeder uses separate timeouts for image capture and inference:

```text
FFmpeg snapshot capture: 30 seconds
CoralAPI HTTP request:    60 seconds
```

A camera or inference failure is logged. During multi-camera operation, a
failure on one camera does not prevent Birdfeeder from continuing with the
remaining enabled cameras.

## Troubleshooting

### CoralAPI cannot be reached

Check the configured endpoint:

```bash
grep '^CORAL_API_URL=' .env
```

Check the CoralAPI container:

```bash
docker ps --filter name=coralapi
docker logs --tail 100 coralapi
```

If Birdfeeder and CoralAPI run on the same host, confirm that CoralAPI is
reachable through the configured loopback address and port.

### Detection works but classification fails

Review the CoralAPI log for model-loading or inference errors:

```bash
docker logs --tail 100 coralapi
```

Confirm that the classification model is available to CoralAPI:

```text
mobilenet_v2_1.0_224_inat_bird_quant_edgetpu
```

### No birds are detected

Possible causes include:

- the camera snapshot does not contain a visible bird
- the bird is too small in the image
- lighting or exposure reduces image quality
- the bird is partly obscured
- `DETECTION_THRESHOLD` is too high
- the detection model is unavailable

First inspect the camera image and verify the RTSP stream. Do not lower the
threshold without reviewing sample images and detection results.

### Species remains uncertain

Possible causes include:

- the crop contains a large amount of feeder or background
- the bird occupies too little of the crop
- lighting or image resolution is insufficient
- the best classification score is below the configured threshold
- the score margin between the first and second result is too small
- the species is not represented well by the classification model

Uncertain observations are intentionally stored so the thresholds and image
quality can be evaluated using real field data.

### One camera works and another fails

CoralAPI is shared by all enabled cameras, but Birdfeeder processes requests
sequentially.

If only one camera fails, the issue is more likely related to:

- the camera's RTSP stream
- credentials
- network connectivity
- exposure or image quality
- camera-specific snapshot capture

Review the Birdfeeder log entry tagged with the affected camera ID.

## Network and security

The reference deployment is intended for a trusted local network.

Recommended precautions:

- do not expose CoralAPI directly to the public internet
- bind CoralAPI to a loopback or trusted internal interface
- restrict access with firewall rules
- do not publish camera credentials or complete RTSP URLs
- keep the local `.env` file outside version control
- expose the Coral TPU device only to the CoralAPI service

## Related documentation

- [Camera Configuration](CAMERAS.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Project README](../README.md)
