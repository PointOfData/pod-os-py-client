"""Pod-OS message protocol implementation."""

from pod_os_client.message.constants import MAX_MESSAGE_SIZE
from pod_os_client.message.decoder import decode_message
from pod_os_client.message.encoder import (
    encode_message,
    format_batch_events_payload,
    format_batch_link_events_payload,
    format_batch_tags_payload,
    serialize_tag_value,
)
from pod_os_client.message.header import construct_header
from pod_os_client.message.intents import Intent
from pod_os_client.message.types import Envelope, EventFields, Message
from pod_os_client.message.utils import get_timestamp, get_timestamp_from_datetime

__all__ = [
    "Message",
    "Envelope",
    "EventFields",
    "Intent",
    "encode_message",
    "decode_message",
    "construct_header",
    "MAX_MESSAGE_SIZE",
    "get_timestamp",
    "get_timestamp_from_datetime",
    "serialize_tag_value",
    "format_batch_events_payload",
    "format_batch_link_events_payload",
    "format_batch_tags_payload",
]
