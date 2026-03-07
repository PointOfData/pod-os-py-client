"""Pod-OS message encoder for wire format."""

import base64
import json
from typing import TYPE_CHECKING, Any

from pod_os_client.errors import EncodeError, EncodeErrorCode
from pod_os_client.message.constants import MAX_MESSAGE_SIZE
from pod_os_client.message.header import construct_header

from pod_os_client.message.types import (
    BatchEventSpec,
    BatchLinkEventSpec,
    Tag,
)

if TYPE_CHECKING:
    from pod_os_client.message.intents import Intent
    from pod_os_client.message.types import Message

__all__ = [
    "encode_message",
    "serialize_tag_value",
    "format_batch_events_payload",
    "format_batch_link_events_payload",
    "format_batch_tags_payload",
]


def _force_ascii(s: str) -> str:
    """Force string to ASCII by removing invalid characters."""
    return "".join(c for c in s if ord(c) <= 127)


def serialize_tag_value(value: Any) -> str:
    """Serialize a Tag value of any type to its string representation.

    Supports: string, int, float, bool, bytes (base64), and complex types (JSON).

    Args:
        value: The value to serialize

    Returns:
        Serialized string representation

    Examples:
        >>> serialize_tag_value("hello")
        'hello'
        >>> serialize_tag_value(42)
        '42'
        >>> serialize_tag_value(True)
        'true'
        >>> serialize_tag_value({"key": "value"})
        '{"key": "value"}'
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value
    elif isinstance(value, bool):
        # Must check bool before int (bool is subclass of int)
        return "true" if value else "false"
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        return str(value)
    elif isinstance(value, bytes):
        return base64.standard_b64encode(value).decode("ascii")
    elif isinstance(value, (dict, list, tuple)):
        # For complex types, serialize as JSON
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
    else:
        # Fallback to string representation
        return str(value)


def format_batch_events_payload(events: list["BatchEventSpec"]) -> str:
    """Format a list of BatchEventSpec into payload format for StoreBatchEvents.

    Each event is formatted as a tab-separated line using Pod-OS socket field names.
    Events are joined with newlines.

    Args:
        events: List of batch event specifications to format

    Returns:
        Formatted payload string ready for use in Message.payload.data

    Example:
        >>> from pod_os_client.message.types import BatchEventSpec, EventFields, Tag
        >>> spec = BatchEventSpec(
        ...     event=EventFields(unique_id="event1", type="test"),
        ...     tags=[Tag(key="category", value="important")]
        ... )
        >>> payload = format_batch_events_payload([spec])
    """
    if not events:
        return ""

    lines: list[str] = []

    for spec in events:
        fields: list[str] = []
        event = spec.event

        # Format event fields using Pod-OS field names
        if event.unique_id:
            fields.append(f"unique_id={event.unique_id}")
        if event.id:
            fields.append(f"event_id={event.id}")
        if event.local_id:
            fields.append(f"local_id={event.local_id}")
        if event.owner:
            fields.append(f"owner={event.owner}")
        if event.owner_unique_id:
            fields.append(f"owner_unique_id={event.owner_unique_id}")
        if event.timestamp:
            fields.append(f"timestamp={event.timestamp}")
        if event.location:
            fields.append(f"loc={event.location}")
        if event.location_separator and event.location_separator != "|":
            fields.append(f"loc_delim={event.location_separator}")
        if event.type:
            fields.append(f"type={event.type}")

        # Append tags to each event line if present.
        # Format matches Go: tag_{i}={frequency}:{key}={value}
        if spec.tags:
            for i, tag in enumerate(spec.tags):
                tag_value = serialize_tag_value(tag.value)
                tag_str = f"{tag.key}={tag_value}" if tag.key else tag_value
                fields.append(f"tag_{i}={tag.frequency}:{tag_str}")

        lines.append("\t".join(fields))

    return "\n".join(lines)


def format_batch_link_events_payload(events: list["BatchLinkEventSpec"]) -> str:
    """Format a list of BatchLinkEventSpec into payload format for BatchLinkEvents.

    Each link is formatted as a tab-separated line using Pod-OS socket field names.
    Events are joined with newlines.

    Required fields:
    - owner_event_id OR owner_unique_id
    - event_id_a OR unique_id_a
    - event_id_b OR unique_id_b
    - strength_a AND strength_b
    - category

    Args:
        events: List of batch link event specifications to format

    Returns:
        Formatted payload string ready for use in Message.payload.data

    Example:
        >>> from pod_os_client.message.types import BatchLinkEventSpec, EventFields, LinkFields
        >>> spec = BatchLinkEventSpec(
        ...     event=EventFields(unique_id="event1"),
        ...     link=LinkFields(event_a="evt1", event_b="evt2", strength_a=1.0, strength_b=0.5)
        ... )
        >>> payload = format_batch_link_events_payload([spec])
    """
    if not events:
        return ""

    lines: list[str] = []

    for spec in events:
        fields: list[str] = []
        event = spec.event
        link = spec.link

        # Format EventFields
        if event.unique_id:
            fields.append(f"unique_id={event.unique_id}")
        if event.id:
            fields.append(f"event_id={event.id}")
        if event.local_id:
            fields.append(f"local_id={event.local_id}")
        if event.owner:
            fields.append(f"owner={event.owner}")
        if event.owner_unique_id:
            fields.append(f"owner_unique_id={event.owner_unique_id}")
        if event.timestamp:
            fields.append(f"timestamp={event.timestamp}")
        if event.location:
            fields.append(f"loc={event.location}")
        if event.location_separator:
            fields.append(f"loc_delim={event.location_separator}")
        if event.type:
            fields.append(f"type={event.type}")

        # Format LinkFields
        if link.unique_id:
            fields.append(f"link_unique_id={link.unique_id}")
        if link.event_a:
            fields.append(f"event_id_a={link.event_a}")
        if link.event_b:
            fields.append(f"event_id_b={link.event_b}")
        if link.unique_id_a:
            fields.append(f"unique_id_a={link.unique_id_a}")
        if link.unique_id_b:
            fields.append(f"unique_id_b={link.unique_id_b}")
        if link.strength_a:
            fields.append(f"strength_a={link.strength_a}")
        else:
            fields.append(f"strength_a=0.0")
        if link.strength_b:
            fields.append(f"strength_b={link.strength_b}")
        else:
            fields.append(f"strength_b=0.0")
        if link.category:
            fields.append(f"category={link.category}")
        if link.owner_unique_id:
            fields.append(f"owner_unique_id={link.owner_unique_id}")
        if link.owner_event_id:
            fields.append(f"owner_event_id={link.owner_event_id}")

        lines.append("\t".join(fields))

    return "\n".join(lines)


def format_batch_tags_payload(tags: list[Tag]) -> str:
    """Format a list of Tag into the payload format for StoreBatchTags and UpdateBatchTags.

    Each tag is one line: frequency=key=value, where value is from serialize_tag_value.
    Lines are newline-separated with no trailing newline. Matches Go FormatBatchTagsPayload.

    Args:
        tags: List of tags to format (may be empty or None).

    Returns:
        Formatted payload string (newline-separated lines, no trailing newline).
    """
    if not tags:
        return ""

    lines: list[str] = []
    for tag in tags:
        value_str = serialize_tag_value(tag.value)
        lines.append(f"{tag.frequency}={tag.key}={value_str}")
    return "\n".join(lines)


def _payload_to_bytes(msg: "Message", intent_name: str) -> bytes:
    """Convert message payload to bytes based on intent.

    StoreBatchEvents accepts list[BatchEventSpec], str, or list[str] (str/list[str] for backward compatibility).
    StoreBatchLinks accepts list[BatchLinkEventSpec] or str (str for backward compatibility).
    StoreBatchTags/UpdateBatchTags accept list[Tag], str, or neural_memory.tags (str for backward compatibility).
    """
    payload_data = msg.payload.data if msg.payload else None

    if intent_name in ("GatewayId", "GatewayStreamOn"):
        return b""

    if intent_name == "StoreBatchEvents":
        if payload_data is not None and payload_data != []:
            if isinstance(payload_data, list) and all(
                isinstance(x, BatchEventSpec) for x in payload_data
            ):
                return format_batch_events_payload(payload_data).encode("utf-8")
            if isinstance(payload_data, str):
                return payload_data.encode("utf-8")
            if isinstance(payload_data, list) and all(
                isinstance(x, str) for x in payload_data
            ):
                return "".join(payload_data).encode("utf-8")
            raise EncodeError(
                "StoreBatchEvents requires payload.data to be a list of BatchEventSpec, str, or list[str]",
                field="PayloadData",
                code=EncodeErrorCode.ENCODE_BATCH_PAYLOAD_FAILED,
            )
        # Fall back to neural_memory.batch_events
        if msg.neural_memory and msg.neural_memory.batch_events:
            return format_batch_events_payload(msg.neural_memory.batch_events).encode("utf-8")
        return b""

    if intent_name == "StoreBatchLinks":
        if payload_data is not None and payload_data != []:
            if isinstance(payload_data, list) and all(
                isinstance(x, BatchLinkEventSpec) for x in payload_data
            ):
                return format_batch_link_events_payload(payload_data).encode("utf-8")
            if isinstance(payload_data, str):
                return payload_data.encode("utf-8")
            raise EncodeError(
                "StoreBatchLinks requires payload.data to be a list of BatchLinkEventSpec or str",
                field="PayloadData",
                code=EncodeErrorCode.ENCODE_BATCH_PAYLOAD_FAILED,
            )
        # Fall back to neural_memory.batch_links
        if msg.neural_memory and msg.neural_memory.batch_links:
            return format_batch_link_events_payload(msg.neural_memory.batch_links).encode("utf-8")
        return b""

    if intent_name in ("StoreBatchTags", "UpdateBatchTags"):
        if msg.payload is not None and msg.payload.data is not None:
            payload_data = msg.payload.data
            if isinstance(payload_data, list) and all(
                isinstance(x, Tag) for x in payload_data
            ):
                return format_batch_tags_payload(payload_data).encode("utf-8")
            if isinstance(payload_data, str):
                return payload_data.encode("utf-8")
            raise EncodeError(
                "StoreBatchTags/UpdateBatchTags require payload.data to be a list of Tag, str (or use neural_memory.tags)",
                field="PayloadData",
                code=EncodeErrorCode.ENCODE_BATCH_PAYLOAD_FAILED,
            )
        if msg.neural_memory and msg.neural_memory.tags:
            return format_batch_tags_payload(msg.neural_memory.tags).encode("utf-8")
        return format_batch_tags_payload([]).encode("utf-8")

    # Other intents: str, bytes, or list[str] only
    if payload_data is None:
        return b""
    if isinstance(payload_data, str):
        return payload_data.encode("utf-8")
    if isinstance(payload_data, bytes):
        return payload_data
    if isinstance(payload_data, list) and all(isinstance(x, str) for x in payload_data):
        return "".join(payload_data).encode("utf-8")
    raise EncodeError(
        "payload.data must be str, bytes, or list[str] for this intent",
        field="PayloadData",
        code=EncodeErrorCode.ENCODE_BATCH_PAYLOAD_FAILED,
    )


def encode_message(msg: "Message", intent: "Intent", conversation_uuid: str) -> bytes:
    """Encode a message to Pod-OS wire format.

    For StoreBatchEvents, StoreBatchLinks, StoreBatchTags, and UpdateBatchTags the
    encoder expects structured payloads only: list of BatchEventSpec, BatchLinkEventSpec,
    or Tag respectively. For StoreBatchTags/UpdateBatchTags, tags may also be provided
    via msg.neural_memory.tags when payload.data is empty.

    Wire format:
        - Total Length (9 bytes, hex with 'x' prefix): x00000000
        - To Length (9 bytes, hex with 'x' prefix): x00000000
        - From Length (9 bytes, hex with 'x' prefix): x00000000
        - Header Length (9 bytes, hex with 'x' prefix): x00000000
        - Message Type (9 bytes, decimal, zero-padded): 000000000
        - Data Type (9 bytes, decimal, zero-padded): 000000000
        - Payload Data Length (9 bytes, hex with 'x' prefix): x00000000
        - To (variable length, ASCII)
        - From (variable length, ASCII)
        - Header (variable length, ASCII)
        - Payload Data (variable length, bytes)

    Args:
        msg: Message to encode
        intent: Intent type for the message
        conversation_uuid: Conversation/connection UUID

    Returns:
        Encoded message as bytes

    Raises:
        EncodeError: If encoding fails or payload type is invalid for the intent
    """
    if msg is None:
        raise EncodeError(
            "message cannot be None",
            code=EncodeErrorCode.ENCODE_MESSAGE_NIL,
        )

    data_type = msg.payload.data_type if msg.payload else 0
    data_bytes = _payload_to_bytes(msg, intent.name)

    if len(data_bytes) > MAX_MESSAGE_SIZE:
        raise EncodeError(
            f"payload size {len(data_bytes)} bytes exceeds maximum {MAX_MESSAGE_SIZE} bytes",
            field="PayloadData",
            code=EncodeErrorCode.ENCODE_PAYLOAD_TOO_LARGE,
        )

    # Construct header
    message_header = construct_header(msg, intent, conversation_uuid)

    # Validate To address
    if "@" not in msg.to:
        raise EncodeError(
            f"To address must be in format <Actor>@<Gateway>: {msg.to}",
            field="To",
            code=EncodeErrorCode.ENCODE_INVALID_ADDRESS,
        )
    local_to = msg.to.split("@")[0]
    local_gateway = msg.to.split("@")[1]
    if not local_to:
        raise EncodeError(
            "Actor name is required in To address",
            field="To",
            code=EncodeErrorCode.ENCODE_INVALID_ADDRESS,
        )
    if not local_gateway:
        raise EncodeError(
            "Gateway name is required in To address",
            field="To",
            code=EncodeErrorCode.ENCODE_INVALID_ADDRESS,
        )

    # Validate From address
    if "@" not in msg.from_:
        raise EncodeError(
            f"From address must be in format <Client>@<Gateway>: {msg.from_}",
            field="From",
            code=EncodeErrorCode.ENCODE_INVALID_ADDRESS,
        )
    local_from = msg.from_.split("@")[0]
    local_from_gateway = msg.from_.split("@")[1]
    if not local_from:
        raise EncodeError(
            "Client name is required in From address",
            field="From",
            code=EncodeErrorCode.ENCODE_INVALID_ADDRESS,
        )
    if not local_from_gateway:
        raise EncodeError(
            "Gateway name is required in From address",
            field="From",
            code=EncodeErrorCode.ENCODE_INVALID_ADDRESS,
        )

    # Encode lengths (9 bytes each, hex with 'x' prefix)
    payload_data_length_encoded = f"x{len(data_bytes):08x}"
    to_length_encoded = f"x{len(msg.to):08x}"
    from_length_encoded = f"x{len(msg.from_):08x}"
    header_length_encoded = f"x{len(message_header):08x}"

    # Encode message type and data type (9 bytes each, decimal, zero-padded)
    message_type_encoded = f"{intent.message_type:09d}"
    data_type_encoded = f"{data_type:09d}"

    # Calculate total length
    total_length = (
        len(msg.to)
        + 9  # to length field
        + len(msg.from_)
        + 9  # from length field
        + len(message_header)
        + 9  # header length field
        + len(message_type_encoded)
        + len(data_type_encoded)
        + len(data_bytes)
        + 9  # payload length field
        + 9  # total length field
    )

    if total_length > MAX_MESSAGE_SIZE:
        raise EncodeError(
            f"encoded message size {total_length} bytes exceeds maximum {MAX_MESSAGE_SIZE} bytes",
            field="message",
            code=EncodeErrorCode.ENCODE_PAYLOAD_TOO_LARGE,
        )

    total_length_encoded = f"x{total_length:08x}"

    # Construct the socket message
    parts = [
        _force_ascii(total_length_encoded),
        _force_ascii(to_length_encoded),
        _force_ascii(from_length_encoded),
        _force_ascii(header_length_encoded),
        _force_ascii(message_type_encoded),
        _force_ascii(data_type_encoded),
        _force_ascii(payload_data_length_encoded),
        _force_ascii(msg.to),
        _force_ascii(msg.from_),
        _force_ascii(message_header),
    ]

    # Join all parts and append data bytes
    header_part = "".join(parts).encode("ascii")
    return header_part + data_bytes
