"""Response payload parsing for Pod-OS messages.

This module provides sophisticated parsing for various response types,
implementing single-pass O(N) algorithms for efficient payload processing.
"""

from typing import Any

from pod_os_client.message.types import (
    BriefHitRecord,
    DateTimeObject,
    EventFields,
    LinkFields,
    Message,
    PayloadFields,
    StoreBatchEventRecord,
    StoreLinkBatchEventRecord,
    TagOutput,
)

__all__ = [
    "parse_get_events_for_tags_payload",
    "parse_get_event_response",
    "parse_store_batch_events_payload",
    "parse_link_event_batch_payload",
    "parse_tags_from_payload",
]


def _parse_tab_delimited_line(line: str) -> dict[str, str]:
    """Parse a tab-delimited line of key=value pairs into a dictionary.

    Args:
        line: Tab-delimited string with key=value pairs

    Returns:
        Dictionary mapping keys to values
    """
    record_map: dict[str, str] = {}
    fields = line.split("\t")

    for field in fields:
        if not field:
            continue
        parts = field.split("=", 1)
        if len(parts) == 2:
            record_map[parts[0]] = parts[1]

    return record_map


def _decode_event_fields(event_map: dict[str, str]) -> EventFields:
    """Decode event fields from a field map.

    Handles multiple field name variants and parses datetime components,
    coordinates, and other event metadata.

    Args:
        event_map: Dictionary of field names to values

    Returns:
        EventFields with populated fields
    """
    event = EventFields()

    # Event ID - multiple possible field names
    event.id = (
        event_map.get("_event_id")
        or event_map.get("event_id")
        or ""
    )

    # Local ID
    event.local_id = (
        event_map.get("local_id")
        or event_map.get("_event_local_id")
        or ""
    )

    # Unique ID - multiple sources
    event.unique_id = (
        event_map.get("unique_id")
        or event_map.get("_unique_id")
        or event_map.get("tag:1:_unique_id")  # Special case for GetEventsForTags
        or ""
    )

    # Event type
    event.type = (
        event_map.get("event_type")
        or event_map.get("_type")
        or event_map.get("type")
        or ""
    )

    # Owner
    event.owner = (
        event_map.get("_owner_id")
        or event_map.get("owner")
        or event_map.get("_event_owner")
        or ""
    )

    # Timestamp
    event.timestamp = (
        event_map.get("timestamp")
        or event_map.get("_timestamp")
        or ""
    )

    # Parse datetime components
    date_time = DateTimeObject()
    date_time.year = int(event_map.get("event_year") or event_map.get("_event_year") or 0)
    date_time.month = int(event_map.get("event_mon") or event_map.get("_event_month") or 0)
    date_time.day = int(event_map.get("event_day") or event_map.get("_event_day") or 0)
    date_time.hour = int(event_map.get("event_hour") or event_map.get("_event_hour") or 0)
    date_time.minute = int(event_map.get("event_min") or event_map.get("_event_min") or 0)
    date_time.second = int(event_map.get("event_sec") or event_map.get("_event_sec") or 0)
    date_time.microsecond = int(event_map.get("event_usec") or event_map.get("_event_usec") or 0)
    event.date_time = date_time

    # Parse coordinates (up to 9 coordinate fields)
    location_parts = []
    for i in range(1, 10):
        coord_key = f"_coordinate_0{i}"
        coord_key_alt = f"coordinate_0{i}"
        coord = event_map.get(coord_key) or event_map.get(coord_key_alt)
        if coord:
            location_parts.append(coord)
    event.location = "|".join(location_parts)
    event.location_separator = "|"

    return event


def _decode_link_event_fields(link_map: dict[str, str]) -> LinkFields:
    """Decode link fields from a field map.

    Args:
        link_map: Dictionary of field names to values

    Returns:
        LinkFields with populated fields
    """
    link = LinkFields()

    # Link ID
    link.id = link_map.get("_event_id") or link_map.get("event_id") or ""

    # Local ID
    link.local_id = (
        link_map.get("local_id")
        or link_map.get("_event_local_id")
        or ""
    )

    # Unique ID
    link.unique_id = (
        link_map.get("unique_id")
        or link_map.get("_unique_id")
        or ""
    )

    # Event type
    link.type = (
        link_map.get("event_type")
        or link_map.get("_type")
        or ""
    )

    # Owner
    link.owner = (
        link_map.get("_user")
        or link_map.get("_owner_id")
        or ""
    )

    # Timestamp
    link.timestamp = (
        link_map.get("timestamp")
        or link_map.get("_timestamp")
        or ""
    )

    # Parse datetime components
    date_time = DateTimeObject()
    date_time.year = int(link_map.get("event_year") or link_map.get("_event_year") or 0)
    date_time.month = int(link_map.get("event_mon") or link_map.get("_event_month") or 0)
    date_time.day = int(link_map.get("event_day") or link_map.get("_event_day") or 0)
    date_time.hour = int(link_map.get("event_hour") or link_map.get("_event_hour") or 0)
    date_time.minute = int(link_map.get("event_min") or link_map.get("_event_min") or 0)
    date_time.second = int(link_map.get("event_sec") or link_map.get("_event_sec") or 0)
    date_time.microsecond = int(link_map.get("event_usec") or link_map.get("_event_usec") or 0)
    link.date_time = date_time

    # Parse coordinates
    location_parts = []
    for i in range(1, 10):
        coord_key = f"_coordinate_0{i}"
        coord_key_alt = f"coordinate_0{i}"
        coord = link_map.get(coord_key) or link_map.get(coord_key_alt)
        if coord:
            location_parts.append(coord)
    link.location = "|".join(location_parts)
    link.location_separator = "|"

    return link


def parse_tags_from_payload(payload: str) -> list[TagOutput]:
    """Parse tags from a payload string.

    Payload Format: <frequency> <tab> <tag category> <tab> <tag value>
    Example: 1	*	word1

    Each line represents one tag entry.

    Args:
        payload: Tab-delimited tag data

    Returns:
        List of TagOutput objects
    """
    results: list[TagOutput] = []

    lines = payload.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse each line as tab-separated: frequency <tab> category <tab> value
        fields = line.split("\t")
        if len(fields) >= 3:
            tag = TagOutput()

            # Parse frequency (first field)
            try:
                tag.frequency = int(fields[0].strip())
            except ValueError:
                tag.frequency = 1

            # Parse category (second field)
            tag.category = fields[1].strip()

            # Parse value (third field)
            tag.value = fields[2].strip()

            results.append(tag)
        elif len(fields) == 2:
            # Handle case with only frequency and value (no category)
            tag = TagOutput()
            try:
                tag.frequency = int(fields[0].strip())
            except ValueError:
                tag.frequency = 1
            tag.value = fields[1].strip()
            results.append(tag)

    return results


def parse_get_events_for_tags_payload(msg: Message) -> tuple[list[EventFields], bool]:
    """Parse the buffered payload for GetEventsForTags response.

    Uses single-pass indexing for O(N) complexity regardless of payload size.
    The payload contains tab-separated field=value pairs, newline-terminated records.

    Line types by prefix:
      - _event_id=: Event object with inline tags
      - _link=: Link between events (source field identifies parent event)
      - _linktag=: Tags for a link (first field is link ID)
      - _targettag=: Tags describing link's target event (first field is target ID)
      - _brief_hit=: Brief hit record (when include_brief_hits=Y)

    Args:
        msg: Message with payload to parse

    Returns:
        Tuple of (event_results list, success bool)
    """
    if not msg.payload or not isinstance(msg.payload.data, str):
        return [], False

    payload_str: str = msg.payload.data
    lines = payload_str.split("\n")

    # Check if this is a brief hits response
    is_brief_hits_response = False
    for line in lines:
        line = line.rstrip("\x00")
        if not line or line == "\x0F" or line == "\x00":
            continue
        is_brief_hits_response = line.startswith("_brief_hit=")
        break

    # Handle brief hits response
    if is_brief_hits_response:
        if not msg.response:
            return [], False
        for line in lines:
            line = line.rstrip("\x00")
            if not line or line == "\x0F" or line == "\x00":
                continue
            if line.startswith("_brief_hit="):
                _parse_brief_hit_line(line, msg)
        return [], True

    # Pre-allocate maps with estimated capacity
    estimated_events = max(len(lines) // 10, 16)

    events_map: dict[str, EventFields] = {}
    event_order: list[str] = []

    links_map: dict[str, LinkFields] = {}
    links_by_source: dict[str, list[str]] = {}  # source_event_id -> list of link_ids

    link_tags_map: dict[str, list[TagOutput]] = {}
    target_tags_map: dict[str, list[TagOutput]] = {}

    # SINGLE PASS: categorize and index all lines
    for line in lines:
        line = line.rstrip("\x00")
        if not line or line == "\x0F" or line == "\x00":
            continue

        # Determine line type by prefix
        if line.startswith("_event_id="):
            event_id, event = _parse_event_id_line(line, msg)
            if event_id and event:
                events_map[event_id] = event
                event_order.append(event_id)

        elif line.startswith("_link="):
            link_id, link = _parse_link_line(line)
            if link_id and link:
                links_map[link_id] = link
                # Index by source for O(1) lookup
                if link.event_a:
                    if link.event_a not in links_by_source:
                        links_by_source[link.event_a] = []
                    links_by_source[link.event_a].append(link_id)

        elif line.startswith("_linktag="):
            link_id, tag = _parse_link_tag_line(line)
            if link_id and tag:
                if link_id not in link_tags_map:
                    link_tags_map[link_id] = []
                link_tags_map[link_id].append(tag)

        elif line.startswith("_targettag="):
            target_id, tag = _parse_target_tag_line(line)
            if target_id and tag:
                if target_id not in target_tags_map:
                    target_tags_map[target_id] = []
                target_tags_map[target_id].append(tag)

    # ASSEMBLY PHASE: Build final results using map lookups
    results: list[EventFields] = []

    for event_id in event_order:
        event = events_map.get(event_id)
        if not event:
            continue

        # Get all links for this event via index
        link_ids = links_by_source.get(event_id, [])
        links: list[LinkFields] = []

        for link_id in link_ids:
            link = links_map.get(link_id)
            if not link:
                continue

            # Attach link tags (O(1) lookup)
            if link_id in link_tags_map:
                link.tags = link_tags_map[link_id]

            # Attach target tags using the link's target event ID
            if link.event_b and link.event_b in target_tags_map:
                link.target_tags = target_tags_map[link.event_b]

            links.append(link)

        event.links = links
        results.append(event)

    return results, True


def _parse_event_id_line(line: str, msg: Message) -> tuple[str, EventFields | None]:
    """Parse an _event_id line and extract the event with inline tags."""
    record_map = _parse_tab_delimited_line(line)

    event_id = record_map.get("_event_id", "")
    if not event_id:
        return "", None

    event = _decode_event_fields(record_map)

    # Parse datasize/mimetype
    if "datasize" in record_map:
        try:
            datasize = int(record_map["_datasize"])
            if not event.payload_data:
                event.payload_data = PayloadFields()
            event.payload_data.data_size = datasize
        except ValueError:
            pass

    if "_mimetype" in record_map:
        if not event.payload_data:
            event.payload_data = PayloadFields()
        event.payload_data.mime_type = record_map["_mimetype"]

    # Parse inline tags (tag:freq:key=value format)
    for key, value in record_map.items():
        if key.startswith("tag:"):
            parts = key.split(":")
            if len(parts) == 3:
                try:
                    freq = int(parts[1])
                except ValueError:
                    freq = 1
                event.tags.append(TagOutput(
                    frequency=freq,
                    key=parts[2],
                    value=value,
                ))

        # Handle _event_tag format
        if key.startswith("_event_tag"):
            tag = _parse_event_tag_payload_field(record_map)
            if tag:
                event.tags.append(tag)

    # Extract unique_id from tags if present
    for tag in event.tags:
        if tag.key in ("_unique_id", "unique_id"):
            event.unique_id = tag.value
            break

    return event_id, event


def _parse_brief_hit_line(line: str, msg: Message) -> None:
    """Parse a _brief_hit line and add it to msg.response.brief_hits."""
    if not msg.response:
        return

    record_map = _parse_tab_delimited_line(line)

    brief_hit = record_map.get("_brief_hit", "")
    if not brief_hit:
        return

    hits = 0
    if "_hits" in record_map:
        try:
            hits = int(record_map["_hits"])
        except ValueError:
            pass

    msg.response.brief_hits.append(BriefHitRecord(
        event_id=brief_hit,
        total_hits=hits,
    ))


def _parse_link_line(line: str) -> tuple[str, LinkFields | None]:
    """Parse a _link line."""
    record_map = _parse_tab_delimited_line(line)

    link_id = record_map.get("_link", "")
    if not link_id:
        return "", None

    link = LinkFields(id=link_id)

    link.event_a = record_map.get("source", "")
    link.event_b = record_map.get("target", "")
    link.unique_id = record_map.get("unique_id", "")
    link.unique_id_a = record_map.get("source_unique_id", "")
    link.unique_id_b = record_map.get("target_unique_id", "")

    if "strength" in record_map:
        try:
            link.strength_b = float(record_map["strength"])
        except ValueError:
            pass

    link.category = record_map.get("category", "")

    return link_id, link


def _parse_link_tag_line(line: str) -> tuple[str, TagOutput | None]:
    """Parse a _linktag line."""
    record_map = _parse_tab_delimited_line(line)

    link_id = record_map.get("_linktag", "")
    if not link_id:
        return "", None

    tag = TagOutput()

    if "freq" in record_map:
        try:
            tag.frequency = int(record_map["freq"])
        except ValueError:
            pass

    if "value" in record_map:
        value = record_map["value"]
        eq_idx = value.find("=")
        if eq_idx > 0:
            tag.key = value[:eq_idx]
            tag.value = value[eq_idx + 1:]
        else:
            tag.value = value

    return link_id, tag


def _parse_target_tag_line(line: str) -> tuple[str, TagOutput | None]:
    """Parse a _targettag line."""
    record_map = _parse_tab_delimited_line(line)

    target_id = record_map.get("_targettag", "")
    if not target_id:
        return "", None

    tag = TagOutput()

    if "freq" in record_map:
        try:
            tag.frequency = int(record_map["freq"])
        except ValueError:
            pass

    if "value" in record_map:
        value = record_map["value"]
        eq_idx = value.find("=")
        if eq_idx > 0:
            tag.key = value[:eq_idx]
            tag.value = value[eq_idx + 1:]
        else:
            tag.value = value

    return target_id, tag


def _parse_event_tag_payload_field(record_map: dict[str, str]) -> TagOutput | None:
    """Parse tag fields from GetEventsForTags payload record."""
    tag = TagOutput()

    if "tag_freq" in record_map:
        try:
            tag.frequency = int(record_map["tag_freq"])
        except ValueError:
            pass

    if "tag_value" in record_map:
        tag_value = record_map["tag_value"]
        eq_idx = tag_value.find("=")
        if eq_idx > 0:
            tag.key = tag_value[:eq_idx]
            tag.value = tag_value[eq_idx + 1:]
        else:
            tag.value = tag_value

    return tag


def parse_get_event_response(
    msg: Message, header_map: dict[str, str]
) -> tuple[list[TagOutput], list[LinkFields], bool]:
    """Parse the payload for GetEvent response.

    Compiles a complete Event object with Tags and Links. The GetEvent Response
    Header contains the Tags for the Events. The Payload contains the Links data.

    Args:
        msg: Message with payload to parse
        header_map: Header fields dictionary

    Returns:
        Tuple of (tags list, links list, success bool)
    """
    tags: list[TagOutput] = []
    links: list[LinkFields] = []

    if not msg.response:
        return [], [], False

    # Parse event_tag headers (format: event_tag:<freq>:<timestamp>=tag_value)
    tags = _parse_event_tag_headers(msg, header_map)

    if not msg.payload or not isinstance(msg.payload.data, str):
        return tags, links, True

    payload_str: str = msg.payload.data

    # Line-based parsing: GetEvent payload uses newline-separated records
    link_map: dict[str, LinkFields] = {}
    link_tags_map: dict[str, list[TagOutput]] = {}
    target_tags_map: dict[str, list[TagOutput]] = {}

    lines = payload_str.split("\n")
    for line in lines:
        line = line.rstrip("\x00").strip()
        if not line or line == "\x0F" or line == "\x00":
            continue

        # Parse _link= lines (link records with inline fields)
        if line.startswith("_link="):
            link = _parse_get_event_link_line(line, header_map)
            if link:
                link_map[link.id] = link
            continue

        # Parse _linktag lines
        if line.startswith("_linktag\t") or line == "_linktag":
            link_id, tag = _parse_get_event_link_tag_line(line)
            if link_id and tag:
                if link_id not in link_tags_map:
                    link_tags_map[link_id] = []
                link_tags_map[link_id].append(tag)
            continue

        # Parse _target_event_tag lines
        if line.startswith("_target_event_tag\t") or line == "_target_event_tag":
            target_event_id, tag = _parse_get_event_target_tag_line(line)
            if target_event_id and tag:
                if target_event_id not in target_tags_map:
                    target_tags_map[target_event_id] = []
                target_tags_map[target_event_id].append(tag)
            continue

        # Mixed first line: may contain event_tags and _link= on same line
        record_map = _parse_tab_delimited_line(line)
        if "_link" in record_map and record_map["_link"]:
            link = _parse_get_event_link_line(line, header_map)
            if link:
                link_map[link.id] = link

    # Consolidate links with their tags
    for link in link_map.values():
        if link.id in link_tags_map:
            link.tags = link_tags_map[link.id]
        if link.event_b and link.event_b in target_tags_map:
            link.target_tags = target_tags_map[link.event_b]
        links.append(link)

    return tags, links, True


def _parse_event_tag_headers(msg: Message, header_map: dict[str, str]) -> list[TagOutput]:
    """Parse event_tag headers from GetEvent response.

    Format: event_tag:<freq>:<timestamp>=tag_value

    Args:
        msg: Message object
        header_map: Header fields dictionary

    Returns:
        List of TagOutput parsed from headers
    """
    results: list[TagOutput] = []

    for key, value in header_map.items():
        if not key.startswith("event_tag:"):
            continue

        # Parse key format: event_tag:<freq>:<timestamp>
        parts = key.split(":")
        if len(parts) < 2:
            continue

        tag = TagOutput(value=value)

        # Parse frequency (second part after event_tag:)
        if len(parts) >= 2:
            try:
                tag.frequency = int(parts[1])
            except ValueError:
                tag.frequency = 1

        # Parse the value to extract key=value if present
        eq_idx = value.find("=")
        if eq_idx > 0:
            tag.key = value[:eq_idx]
            tag.value = value[eq_idx + 1:]

        results.append(tag)

    return results


def _parse_get_event_link_line(line: str, header_map: dict[str, str]) -> LinkFields | None:
    """Parse a _link= line from GetEvent payload.

    Format: _link={linkId}	unique_id=	target_event=	target_unique_id=	strength=	link_time=	category=
    """
    record_map = _parse_tab_delimited_line(line)
    link_id = record_map.get("_link", "")
    if not link_id:
        return None

    link = LinkFields(id=link_id)

    link.event_b = record_map.get("target_event", "")
    link.unique_id_b = record_map.get("target_unique_id", "")
    link.unique_id = record_map.get("unique_id", "")

    if "strength" in record_map:
        try:
            link.strength_b = float(record_map["strength"])
        except ValueError:
            pass

    link.category = record_map.get("category", "")

    # EventA is the main event (source); get from header when available
    if header_map:
        link.event_a = (
            header_map.get("event_id")
            or header_map.get("_event_id")
            or ""
        )

    return link


def _parse_get_event_link_tag_line(line: str) -> tuple[str, TagOutput | None]:
    """Parse a _linktag line from GetEvent payload.

    Format: _linktag	event_id={linkId}	unique=	freq=	timestamp=	value=
    The link ID comes from event_id, not _linktag.
    """
    record_map = _parse_tab_delimited_line(line)
    link_id = record_map.get("event_id", "")
    if not link_id:
        return "", None

    tag = TagOutput()

    if "freq" in record_map:
        try:
            tag.frequency = int(record_map["freq"])
        except ValueError:
            pass

    if "value" in record_map:
        value = record_map["value"]
        eq_idx = value.find("=")
        if eq_idx > 0:
            tag.key = value[:eq_idx]
            tag.value = value[eq_idx + 1:]
        else:
            tag.value = value

    return link_id, tag


def _parse_get_event_target_tag_line(line: str) -> tuple[str, TagOutput | None]:
    """Parse a _target_event_tag line from GetEvent payload.

    Format: _target_event_tag	event_id={targetEventId}	unique=	freq=	timestamp=	value=
    The target event ID comes from event_id.
    """
    record_map = _parse_tab_delimited_line(line)
    target_event_id = record_map.get("event_id", "")
    if not target_event_id:
        return "", None

    tag = TagOutput()

    if "freq" in record_map:
        try:
            tag.frequency = int(record_map["freq"])
        except ValueError:
            pass

    if "value" in record_map:
        value = record_map["value"]
        eq_idx = value.find("=")
        if eq_idx > 0:
            tag.key = value[:eq_idx]
            tag.value = value[eq_idx + 1:]
        else:
            tag.value = value

    return target_event_id, tag


def parse_store_batch_events_payload(msg: Message) -> tuple[list[StoreBatchEventRecord], bool]:
    """Parse the payload for StoreBatchEvents response.

    Args:
        msg: Message with payload to parse

    Returns:
        Tuple of (storage results list, success bool)
    """
    if not msg.payload or not isinstance(msg.payload.data, str):
        return [], False

    results: list[StoreBatchEventRecord] = []
    lines = msg.payload.data.split("\n")

    for line in lines:
        line = line.rstrip("\x00")
        if not line or line == "\x0F" or line == "\x00":
            continue

        # Parse each line as tab-separated key=value pairs
        record_map = _parse_tab_delimited_line(line)

        # Create storage record
        record = StoreBatchEventRecord(
            status=record_map.get("_status", ""),
            message=record_map.get("_msg", ""),
        )

        # Extract Event fields
        event = _decode_event_fields(record_map)
        record.event_fields = event

        results.append(record)

    return results, True


def parse_link_event_batch_payload(msg: Message) -> tuple[list[StoreLinkBatchEventRecord], bool]:
    """Parse the payload for StoreBatchLinks response.

    Payload format: newline-terminated records of tab-delimited fields.

    Args:
        msg: Message with payload to parse

    Returns:
        Tuple of (link storage results list, success bool)
    """
    if not msg.payload or not isinstance(msg.payload.data, str):
        return [], False

    results: list[StoreLinkBatchEventRecord] = []
    lines = msg.payload.data.split("\n")

    for line in lines:
        line = line.rstrip("\x00")
        if not line or line == "\x0F" or line == "\x00":
            continue

        # Parse each line as tab-separated key=value pairs
        record_map = _parse_tab_delimited_line(line)

        # Create link record
        link_error_code: int | None = None
        if "_link_error_code" in record_map:
            try:
                link_error_code = int(record_map["_link_error_code"])
            except ValueError:
                pass

        record = StoreLinkBatchEventRecord(
            status=record_map.get("_status", ""),
            message=record_map.get("_status_info") or record_map.get("_msg", ""),
            link_error_code=link_error_code,
        )

        # Parse all LinkFields
        link = LinkFields()

        # Link IDs
        link.unique_id = record_map.get("unique_id", "")
        link.id = record_map.get("event_id", "")

        # Owner fields
        link.owner_unique_id = record_map.get("owner_unique_id", "")
        link.owner_event_id = (
            record_map.get("owner_id")
            or record_map.get("owner_event_id")
            or ""
        )
        link.owner = record_map.get("owner", "")

        # Timestamp
        link.timestamp = record_map.get("timestamp", "")

        # Location fields
        link.location = record_map.get("loc", "")
        link.location_separator = record_map.get("loc_delim", "")

        # Type
        link.type = record_map.get("type", "")

        # Event A/B fields
        link.event_a = record_map.get("event_id_a", "")
        link.event_b = record_map.get("event_id_b", "")
        link.unique_id_a = record_map.get("unique_id_a", "")
        link.unique_id_b = record_map.get("unique_id_b", "")

        # Strength fields
        if "strength_a" in record_map:
            try:
                link.strength_a = float(record_map["strength_a"])
            except ValueError:
                pass

        if "strength_b" in record_map:
            try:
                link.strength_b = float(record_map["strength_b"])
            except ValueError:
                pass

        # Category
        link.category = record_map.get("category", "")

        record.link_fields = link
        results.append(record)

    return results, True
