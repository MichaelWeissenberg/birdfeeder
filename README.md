TL:DR Lightweight bird feeder monitoring system powered by Google Coral TPU. Captures RTSP camera snapshots, detects birds, classifies species, stores observations as JSON records, and provides a simple Flask-based web interface for browsing bird visitors and image crops.

# Birdfeeder

Birdfeeder is a lightweight bird monitoring system running on a Google Coral TPU.

Features:

- RTSP camera integration
- Bird detection using EdgeTPU
- Bird species classification
- Automatic crop generation
- JSON-based observation history
- Lightweight Flask web interface
- Docker-based deployment

The project was designed with a strong KISS (Keep It Simple, Stupid) philosophy and replaces a more complex stack consisting of Frigate, go2rtc and WatchMyBirds.
