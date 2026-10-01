# Coral Edge TPU Integration

Birdfeeder uses a Google Coral Edge TPU to accelerate bird detection and
species classification.

The Birdfeeder application does not access the Edge TPU hardware directly.
Instead, all inference requests are sent to a separate CoralAPI service.

## Architecture

RTSP camera
    |
    v
Birdfeeder
    |
    | HTTP image upload
    v
CoralAPI
    |
    v
Google Coral Edge TPU
