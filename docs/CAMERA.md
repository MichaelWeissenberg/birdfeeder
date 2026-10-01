# Camera Configuration

Birdfeeder obtains images from an RTSP-compatible network camera.

The camera stream is configured through the "CAMERA_URL"
environment variable.

## Requirements

The camera must support:

- RTSP streaming
- network access from the Birdfeeder host
- JPEG-capable video stream
- continuous availability

Birdfeeder captures a single image every cycle using FFmpeg.

---

## Camera URL

The camera stream is configured in ".env":

CAMERA_URL=rtsp://user:password@camera-ip:554/stream
