"""Optional Kafka producer (full profile). Fails soft when Kafka is absent."""

import json
import logging

logger = logging.getLogger(__name__)


class DetectionProducer:
    def __init__(self, bootstrap_servers: str, enabled: bool = False) -> None:
        self.enabled = enabled
        self.producer = None
        if not enabled:
            return
        try:
            from kafka import KafkaProducer

            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode(),
                linger_ms=50,
            )
        except Exception:
            logger.exception("Kafka unavailable - continuing without streaming bus")
            self.enabled = False

    def send(self, topic: str, message: dict) -> None:
        if self.enabled and self.producer is not None:
            try:
                self.producer.send(topic, message)
            except Exception:
                logger.exception("kafka send failed")
