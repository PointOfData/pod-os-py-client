"""Pod-OS message decoder for wire format."""

from pod_os_client.errors import DecodeError, DecodeErrorCode
from pod_os_client.message.intents import intent_from_message_type_and_command
from pod_os_client.message.responses import (
    parse_get_event_response,
    parse_get_events_for_tags_payload,
    parse_link_event_batch_payload,
    parse_store_batch_events_payload,
)
from pod_os_client.message.types import (
    DateTimeObject,
    EventFields,
    Message,
    PayloadFields,
    ResponseFields,
)

__all__ = ["decode_message"]


def _decode_size_param(param: bytes) -> int:
    """Decode a message size parameter from bytes.

    Args:
        param: Size parameter bytes

    Returns:
        Decoded size as integer
    """
    # Trim null bytes and whitespace
    param_str = param.rstrip(b"\x00").decode("ascii").strip()

    if not param_str:
        return 0

    # Check if hex (starts with 'x')
    if param_str.startswith("x"):
        return int(param_str[1:], 16)
    else:
        return int(param_str, 10)


def _decode_header(header_str: str) -> dict[str, str]:
    """Decode header string into a dictionary.

    Args:
        header_str: Header string with tab-separated key=value pairs

    Returns:
        Dictionary of header fields
    """
    header_map: dict[str, str] = {}

    # Split by tab character
    parts = header_str.split("\t")
    for part in parts:
        if "=" in part:
            # Split on first '=' only
            key, value = part.split("=", 1)
            header_map[key.strip()] = value.strip()

    return header_map


def _decode_event_fields_from_header(header_map: dict[str, str]) -> EventFields:
    """Decode event fields from header map.

    Handles multiple field name variants and parses datetime components,
    coordinates, and other event metadata.

    Args:
        header_map: Dictionary of header field names to values

    Returns:
        EventFields with populated fields
    """
    event = EventFields()

    # Event ID - multiple possible field names
    event.id = (
        header_map.get("_event_id")
        or header_map.get("event_id")
        or ""
    )

    # Local ID
    event.local_id = (
        header_map.get("local_id")
        or header_map.get("_event_local_id")
        or ""
    )

    # Unique ID
    event.unique_id = (
        header_map.get("unique_id")
        or header_map.get("_unique_id")
        or ""
    )

    # Event type
    event.type = (
        header_map.get("event_type")
        or header_map.get("_type")
        or header_map.get("type")
        or ""
    )

    # Owner
    event.owner = (
        header_map.get("_owner_id")
        or header_map.get("owner")
        or header_map.get("_event_owner")
        or ""
    )

    # Timestamp
    event.timestamp = (
        header_map.get("timestamp")
        or header_map.get("_timestamp")
        or ""
    )

    # Parse datetime components
    date_time = DateTimeObject()
    try:
        date_time.year = int(header_map.get("event_year") or header_map.get("_event_year") or 0)
        date_time.month = int(header_map.get("event_mon") or header_map.get("_event_month") or 0)
        date_time.day = int(header_map.get("event_day") or header_map.get("_event_day") or 0)
        date_time.hour = int(header_map.get("event_hour") or header_map.get("_event_hour") or 0)
        date_time.minute = int(header_map.get("event_min") or header_map.get("_event_min") or 0)
        date_time.second = int(header_map.get("event_sec") or header_map.get("_event_sec") or 0)
        date_time.microsecond = int(header_map.get("event_usec") or header_map.get("_event_usec") or 0)
    except ValueError:
        pass  # Keep default values if parsing fails
    event.date_time = date_time

    # Parse coordinates (up to 9 coordinate fields)
    location_parts = []
    for i in range(1, 10):
        coord_key = f"_coordinate_0{i}"
        coord_key_alt = f"coordinate_0{i}"
        coord = header_map.get(coord_key) or header_map.get(coord_key_alt)
        if coord:
            location_parts.append(coord)
    if location_parts:
        event.location = "|".join(location_parts)
        event.location_separator = "|"

    return event


def decode_message(data: bytes) -> Message:
    """Decode Pod-OS wire format to Message.

    Wire format:
        - Total Length (9 bytes)
        - To Length (9 bytes)
        - From Length (9 bytes)
        - Header Length (9 bytes)
        - Message Type (9 bytes)
        - Data Type (9 bytes)
        - Payload Data Length (9 bytes)
        - To (variable)
        - From (variable)
        - Header (variable)
        - Payload Data (variable)

    Args:
        data: Raw bytes from socket

    Returns:
        Decoded Message

    Raises:
        DecodeError: If decoding fails
    """
    MIN_MESSAGE_SIZE = 63  # 7 fields * 9 bytes each

    if len(data) < MIN_MESSAGE_SIZE:
        raise DecodeError(
            f"message too short, expected at least {MIN_MESSAGE_SIZE} bytes, got {len(data)} bytes",
            field="message",
            code=DecodeErrorCode.DECODE_MESSAGE_TOO_SHORT,
        )

    offset = 0

    # Decode lengths (each 9 bytes)
    try:
        _total_length = _decode_size_param(data[offset : offset + 9])  # noqa: F841
        offset += 9

        to_length = _decode_size_param(data[offset : offset + 9])
        offset += 9

        from_length = _decode_size_param(data[offset : offset + 9])
        offset += 9

        header_length = _decode_size_param(data[offset : offset + 9])
        offset += 9

        message_type = int(data[offset : offset + 9].decode("ascii").strip())
        offset += 9

        data_type = int(data[offset : offset + 9].decode("ascii").strip())
        offset += 9

        payload_data_length = _decode_size_param(data[offset : offset + 9])
        offset += 9
    except (ValueError, UnicodeDecodeError) as e:
        raise DecodeError(
            f"failed to decode size parameters: {e}",
            field="length_fields",
            code=DecodeErrorCode.DECODE_INVALID_SIZE_PARAM,
            original_error=e,
        )

    # Validate we have enough data for variable fields
    required_length = offset + to_length + from_length + header_length + payload_data_length
    if len(data) < required_length:
        raise DecodeError(
            f"message too short for declared fields, expected at least {required_length} bytes, got {len(data)} bytes",
            field="message",
            code=DecodeErrorCode.DECODE_MESSAGE_TOO_SHORT,
        )

    # Decode variable-length fields
    try:
        to_addr = data[offset : offset + to_length].decode("utf-8")
        offset += to_length

        from_addr = data[offset : offset + from_length].decode("utf-8")
        offset += from_length

        header_str = data[offset : offset + header_length].decode("utf-8")
        offset += header_length
    except UnicodeDecodeError as e:
        raise DecodeError(
            f"failed to decode header fields: {e}",
            field="header",
            code=DecodeErrorCode.DECODE_INVALID_HEADER,
            original_error=e,
        )

    payload_data = data[offset : offset + payload_data_length]

    # Decode header
    try:
        header_map = _decode_header(header_str)
    except Exception as e:
        raise DecodeError(
            f"failed to parse header: {e}",
            field="header",
            code=DecodeErrorCode.DECODE_INVALID_HEADER,
            original_error=e,
        )

    # Extract actual address from from_addr if routing data is present
    # Format: address|gateway,client,timestamp
    # We only want the address part (position 0)
    if "|" in from_addr:
        from_addr = from_addr.split("|")[0]

    # Determine intent from message type and command
    command = header_map.get("_db_cmd") or header_map.get("_type") or header_map.get("_command") or ""
    intent = intent_from_message_type_and_command(message_type, command)

    # Create message with envelope fields
    msg = Message(
        to=to_addr,
        from_=from_addr,
        intent=intent.name if intent else "",
        message_id=header_map.get("_msg_id", ""),
        client_name=header_map.get("id:name", ""),
        passcode=header_map.get("id:passcode", ""),
        user_name=header_map.get("id:user", ""),
    )

    # Decode event fields from header
    msg.event = _decode_event_fields_from_header(header_map)

    # Decode payload fields from header
    payload_fields = PayloadFields()
    payload_fields.mime_type = header_map.get("mime") or header_map.get("_mimetype") or ""
    payload_fields.data_type = data_type
    if "_datasize" in header_map:
        try:
            payload_fields.data_size = int(header_map["_datasize"])
        except ValueError:
            payload_fields.data_size = len(payload_data)
    else:
        payload_fields.data_size = len(payload_data)

    # Decode payload data if present
    if payload_data:
        # Determine how to decode based on MIME type
        if payload_fields.mime_type == "application/octet-stream":
            payload_fields.data = payload_data
        elif payload_fields.mime_type == "application/json":
            try:
                payload_fields.data = payload_data.decode("utf-8")
            except UnicodeDecodeError:
                payload_fields.data = payload_data
        elif payload_fields.mime_type == "text/plain":
            try:
                payload_fields.data = payload_data.decode("utf-8")
            except UnicodeDecodeError:
                payload_fields.data = payload_data
        else:
            # Try UTF-8 decode, fall back to bytes
            try:
                payload_fields.data = payload_data.decode("utf-8")
            except UnicodeDecodeError:
                payload_fields.data = payload_data

    msg.payload = payload_fields

    # Initialize and populate response fields for response messages
    if message_type in (1001, 30, 3) or (intent and "Response" in intent.name) or (intent and intent.name == "Status"):
        response = ResponseFields(
            status=header_map.get("_status", ""),
            message=header_map.get("_msg", ""),
            type=header_map.get("_type", ""),
        )

        # Map all response count fields
        # Total events (multiple possible field names)
        if "_total_event_hits" in header_map:
            try:
                response.total_events = int(header_map["_total_event_hits"])
            except ValueError:
                pass
        elif "_count" in header_map:
            try:
                response.total_events = int(header_map["_count"])
            except ValueError:
                pass
        elif "total_link_requests_found" in header_map:
            try:
                response.total_events = int(header_map["total_link_requests_found"])
            except ValueError:
                pass
        elif "_total_link_requests_found" in header_map:
            try:
                response.total_events = int(header_map["_total_link_requests_found"])
            except ValueError:
                pass

        # Storage success count
        if "links_ok" in header_map:
            try:
                response.storage_success_count = int(header_map["links_ok"])
            except ValueError:
                pass
        elif "_links_ok" in header_map:
            try:
                response.storage_success_count = int(header_map["_links_ok"])
            except ValueError:
                pass

        # Storage error count
        if "links_with_errors" in header_map:
            try:
                response.storage_error_count = int(header_map["links_with_errors"])
            except ValueError:
                pass
        elif "_links_with_errors" in header_map:
            try:
                response.storage_error_count = int(header_map["_links_with_errors"])
            except ValueError:
                pass

        # Pagination fields
        if "_start_result" in header_map:
            try:
                response.start_result = int(header_map["_start_result"])
            except ValueError:
                pass

        if "_end_result" in header_map:
            try:
                response.end_result = int(header_map["_end_result"])
            except ValueError:
                pass

        # Returned events
        if "_returned_event_hits" in header_map:
            try:
                response.returned_events = int(header_map["_returned_event_hits"])
            except ValueError:
                pass

        # Link count
        if "_set_link_count" in header_map:
            try:
                response.link_count = int(header_map["_set_link_count"])
            except ValueError:
                pass
        elif "_link_count" in header_map:
            try:
                response.link_count = int(header_map["_link_count"])
            except ValueError:
                pass

        # Tag count
        if "_tag_count" in header_map:
            try:
                response.tag_count = int(header_map["_tag_count"])
            except ValueError:
                pass

        # Link ID for LinkEventResponse
        if "link_event" in header_map:
            response.link_id = header_map["link_event"]

        msg.response = response

        # Parse payload for specific intents
        if intent and payload_data:
            intent_name = intent.name

            # Handle both Request and Response intent names
            if intent_name in ("GetEvent", "GetEventResponse"):
                # Parse tags and links from GetEvent response
                if payload_fields.mime_type != "application/octet-stream":
                    tags, links, ok = parse_get_event_response(msg, header_map)
                    if ok and msg.event:
                        msg.response.event_records = [msg.event]
                        msg.response.event_records[0].tags = tags
                        msg.response.event_records[0].links = links

            elif intent_name in ("GetEventsForTags", "GetEventsForTagsResponse"):
                event_records, ok = parse_get_events_for_tags_payload(msg)
                if ok:
                    msg.response.event_records = event_records

            elif intent_name in ("StoreBatchEvents", "StoreBatchEventsResponse"):
                batch_record, ok = parse_store_batch_events_payload(msg)
                if ok:
                    msg.response.store_batch_event_record = batch_record

            elif intent_name in ("StoreBatchLinks", "StoreBatchLinksResponse"):
                link_record, ok = parse_link_event_batch_payload(msg)
                if ok:
                    msg.response.store_link_batch_event_record = link_record

            # Other response types (StoreBatchTags, UpdateBatchTags, StoreEvent, LinkEvent, UnlinkEvent)
            # use only header fields, no payload parsing needed

    return msg
