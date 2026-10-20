# Camera Configuration

Birdfeeder supports one or more RTSP cameras.

The complete reference configuration can be found in:

    .env.example

Each camera consists of:

- technical identifier
- visible human-readable label
- RTSP URL
- enabled state


## Camera Slots

Birdfeeder loads camera slots from `1` to `CAMERA_COUNT`.

Example:

```env
CAMERA_COUNT=3

CAMERA_1_...
CAMERA_2_...
CAMERA_3_...
```

Each enabled camera is processed sequentially.

### Examples:

```env
CAMERA_COUNT=2

CAMERA_1_NAME=tuya1
CAMERA_1_LABEL=Tuya Cam Outdoor 2
CAMERA_1_URL=rtsp://...
CAMERA_1_ENABLED=true

CAMERA_2_NAME=tapo_c200
CAMERA_2_LABEL=Tapo C200 Outdoor 1
CAMERA_2_URL=rtsp://...
CAMERA_2_ENABLED=true
```

## Camera Name

The camera name is a stable technical identifier.
> Camera names must be unique because the technical name is stored in event
> IDs, filenames, JSON records, filters, and statistics.

It is used in:

- event IDs
- filenames
- JSON records
- filters
- statistics

### Examples:

- tuya
- tapo_c200
- north_feeder

## Camera Label

The camera label is shown in the WebUI.

### Example:

```text
Technical name: tapo_84d25c3841
Human readable label: Tapo C200 Outdoor 1
```

Changing the label does not affect stored observations.

## Runtime

Birdfeeder processes all enabled cameras sequentially.

```text
Camera 1
→ Snapshot
→ Detection
→ Classification
→ Storage

Camera 2
→ Snapshot
→ Detection
→ Classification
→ Storage

Next processing round
```

Only after the complete round has finished does the next round begin.
No parallel FFmpeg processes are used.
No concurrent CoralAPI requests are used.

## Observation Records

Each observation stores the technical camera name:

```json
{
    "camera": "tapo_c200"
}
```

Camera labels are displayed in the WebUI while the technical camera name remains stored in observation metadata and filter values.

## Validation

Review configured cameras:

```bash
grep -E \
'^(CAMERA_COUNT|CAMERA_[0-9]+_(NAME|LABEL|ENABLED))=' \
.env
```

## Related Documentation
- [Deployment Guide](DEPLOYMENT.md)
- [Coral Edge TPU Integration](CORAL.md)
- [Project README](../README.md)
