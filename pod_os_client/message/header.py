"""Pod-OS message header construction."""

from typing import TYPE_CHECKING

from pod_os_client.message.utils import get_timestamp

if TYPE_CHECKING:
    from pod_os_client.message.intents import Intent
    from pod_os_client.message.types import Message

__all__ = ["construct_header"]


def construct_header(msg: "Message", intent: "Intent", connection_id_uuid: str) -> str:
    """Construct the header for a message.

    Args:
        msg: The message to construct header for
        intent: The intent type
        connection_id_uuid: The connection/conversation UUID

    Returns:
        The constructed header string
    """
    intent_name = intent.name

    if intent_name == "GatewayId":
        return _gateway_identify_connection_header(msg)
    elif intent_name == "GatewayStreamOn":
        return _gateway_stream_on_header(msg)
    elif intent_name == "GatewayStreamOff":
        return _gateway_stream_off_header(msg)
    elif intent_name == "ActorEcho":
        return _actor_echo_header(msg)
    elif intent_name == "StoreEvent":
        return _store_event_message_header(msg)
    elif intent_name == "StoreData":
        return _store_data_message_header(msg)
    elif intent_name == "LinkEvent":
        return _link_events_message_header(msg)
    elif intent_name == "UnlinkEvent":
        return _unlink_events_message_header(msg)
    elif intent_name == "GetEvent":
        return _get_event_message_header(msg)
    elif intent_name == "GetEventsForTags":
        return _get_events_for_tag_message_header(msg)
    elif intent_name == "StoreBatchEvents":
        return _store_batch_events_message_header(msg)
    elif intent_name in ("StoreBatchTags", "BatchStoreTags"):
        return _store_batch_tags_message_header(msg)
    elif intent_name == "StoreBatchLinks":
        return _batch_link_events_message_header(msg)
    elif intent_name == "ActorRequest":
        return _actor_request_header(msg)
    elif intent_name == "ActorResponse":
        return _actor_response_header(msg)
    elif intent_name == "Status":
        return _status_header(msg)
    else:
        return ""


def _force_ascii(s: str) -> str:
    """Force string to ASCII by removing invalid characters."""
    return "".join(c for c in s if ord(c) <= 127)


def _gateway_identify_connection_header(msg: "Message") -> str:
    """Construct Gateway ID connection header."""
    parts = []
    if msg.passcode and msg.user_name:
        parts.append(f"id:passcode={msg.passcode}")
        parts.append(f"id:user={msg.user_name}")
    parts.append(f"id:name={msg.client_name}")
    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")
    return "\t".join(parts)


def _gateway_stream_on_header(msg: "Message") -> str:
    """Construct Gateway Stream On header."""
    if msg.message_id:
        return f"_msg_id={msg.message_id}"
    return ""


def _gateway_stream_off_header(msg: "Message") -> str:
    """Construct Gateway Stream Off header."""
    if msg.message_id:
        return f"_msg_id={msg.message_id}"
    return ""


def _actor_echo_header(msg: "Message") -> str:
    """Construct Actor Echo header."""
    return f"_msg_id={msg.message_id}"


def _actor_request_header(msg: "Message") -> str:
    """Construct Actor Request header."""
    parts = ["_type=status"]

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _actor_response_header(msg: "Message") -> str:
    """Construct Actor Response header."""
    parts = []
    
    # Envelope fields
    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")
    
    # Event fields
    if msg.event:
        if msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")
        if msg.event.type:
            parts.append(f"type={msg.event.type}")
        if msg.event.owner:
            parts.append(f"owner={msg.event.owner}")
        if msg.event.timestamp:
            parts.append(f"timestamp={msg.event.timestamp}")
        if msg.event.location:
            parts.append(f"loc={msg.event.location}")
        if msg.event.location_separator:
            parts.append(f"loc_delim={msg.event.location_separator}")
    
    # Response fields
    if msg.response:
        if msg.response.status:
            parts.append(f"_status={msg.response.status}")
        if msg.response.message:
            parts.append(f"_msg={msg.response.message}")
        if msg.response.type:
            parts.append(f"_type={msg.response.type}")
    
    return "\t".join(parts) if parts else ""


def _status_header(msg: "Message") -> str:
    """Construct Status header."""
    parts = []
    
    # Envelope fields
    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")
    
    # Event fields
    if msg.event:
        if msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")
        if msg.event.type:
            parts.append(f"type={msg.event.type}")
        if msg.event.owner:
            parts.append(f"owner={msg.event.owner}")
        if msg.event.timestamp:
            parts.append(f"timestamp={msg.event.timestamp}")
        if msg.event.location:
            parts.append(f"loc={msg.event.location}")
        if msg.event.location_separator:
            parts.append(f"loc_delim={msg.event.location_separator}")
    
    # Response fields
    if msg.response:
        if msg.response.status:
            parts.append(f"_status={msg.response.status}")
        if msg.response.message:
            parts.append(f"_msg={msg.response.message}")
        if msg.response.type:
            parts.append(f"_type={msg.response.type}")
    
    return "\t".join(parts) if parts else ""


def _store_event_message_header(msg: "Message") -> str:
    """Construct Store Event message header."""
    parts = ["_db_cmd=store"]

    if msg.event:
        if msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")
        if msg.event.id:
            parts.append(f"event_id={_force_ascii(msg.event.id)}")
        if msg.event.owner:
            parts.append(f"owner={msg.event.owner}")
        if msg.event.timestamp:
            parts.append(f"timestamp={msg.event.timestamp}")
        else:
            parts.append(f"timestamp={get_timestamp()}")

        parts.append(f"loc_delim={msg.event.location_separator}")
        parts.append(f"loc={msg.event.location}")

        if msg.event.type:
            parts.append(f"type={msg.event.type}")
        else:
            parts.append("type=store event")

        mime = msg.payload.mime_type if msg.payload else ""
        parts.append(f"mime={mime}")

        # Tags from neural_memory.tags
        if msg.neural_memory and msg.neural_memory.tags:
            from pod_os_client.message.encoder import serialize_tag_value
            for i, tag in enumerate(msg.neural_memory.tags):
                tag_name = f"tag_{i + 1:04d}"
                tag_value = f"{tag.frequency}:{tag.key}={serialize_tag_value(tag.value)}"
                parts.append(f"{tag_name}={tag_value}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _store_data_message_header(msg: "Message") -> str:
    """Construct Store Data message header.

    Stores data directly in the Evolutionary Neural Memory database. Unlike StoreEvent,
    this intent does not include tags. Required fields: Event.unique_id OR
    Event.id, Event.timestamp, Event.location, Event.location_separator,
    Payload.data, Payload.mime_type.
    """
    parts = ["_db_cmd=store_data"]

    if msg.event:
        if msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")
        elif msg.event.id:
            parts.append(f"event_id={_force_ascii(msg.event.id)}")
        if msg.event.timestamp:
            parts.append(f"timestamp={msg.event.timestamp}")
        else:
            parts.append(f"timestamp={get_timestamp()}")
        parts.append(f"loc_delim={msg.event.location_separator}")
        parts.append(f"loc={msg.event.location}")
    else:
        parts.append(f"timestamp={get_timestamp()}")
        parts.append("loc_delim=|")
        parts.append("loc=")

    mime = msg.payload.mime_type if msg.payload else ""
    parts.append(f"mime={mime}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _link_events_message_header(msg: "Message") -> str:
    """Construct Link Events message header."""
    parts = ["_db_cmd=link"]

    # Link creation event identifiers (from msg.event)
    if msg.event:
        if msg.event.id:
            parts.append(f"event_id={_force_ascii(msg.event.id)}")
        elif msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")
        if msg.event.owner:
            parts.append(f"owner={msg.event.owner}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    if msg.neural_memory and msg.neural_memory.link:
        link = msg.neural_memory.link

        # Prefer UniqueIdA/B; otherwise use EventA/B
        if link.unique_id_a and link.unique_id_b:
            parts.append(f"unique_id_a={link.unique_id_a}")
            parts.append(f"unique_id_b={link.unique_id_b}")
        elif link.event_a and link.event_b:
            parts.append(f"event_id_a={_force_ascii(link.event_a)}")
            parts.append(f"event_id_b={_force_ascii(link.event_b)}")

        # Always write strength, category, loc_delim, loc, type, mime, timestamp
        parts.append(f"strength_a={link.strength_a}")
        parts.append(f"strength_b={link.strength_b}")
        parts.append(f"category={link.category}")
        parts.append(f"loc_delim={link.location_separator}")
        parts.append(f"loc={link.location}")
        parts.append(f"type={link.type}")

        mime = msg.payload.mime_type if msg.payload else ""
        parts.append(f"mime={mime}")

        parts.append(f"timestamp={link.timestamp}")

        if link.owner_event_id:
            parts.append(f"owner_event_id={link.owner_event_id}")
        elif link.owner_unique_id:
            parts.append(f"owner_unique_id={link.owner_unique_id}")

    return "\t".join(parts)


def _unlink_events_message_header(msg: "Message") -> str:
    """Construct Unlink Events message header."""
    parts = ["_db_cmd=unlink"]

    if msg.neural_memory and msg.neural_memory.link:
        link = msg.neural_memory.link
        if link.owner:
            parts.append(f"owner={link.owner}")
        if link.id:
            parts.append(f"event_id={_force_ascii(link.id)}")
        elif link.unique_id:
            parts.append(f"unique_id={link.unique_id}")
        if link.location_separator:
            parts.append(f"loc_delim={link.location_separator}")
        if link.location:
            parts.append(f"loc={link.location}")
        if link.timestamp:
            parts.append(f"timestamp={link.timestamp}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _get_event_message_header(msg: "Message") -> str:
    """Construct Get Event message header."""
    parts = ["_db_cmd=get"]

    if msg.event:
        if msg.event.id:
            parts.append(f"event_id={_force_ascii(msg.event.id)}")
        elif msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")

    if msg.neural_memory and msg.neural_memory.get_event:
        opts = msg.neural_memory.get_event
        if opts.send_data:
            parts.append("send_data=Y")
        if opts.get_tags:
            parts.append("get_tags=Y")
        if opts.get_links:
            parts.append("get_links=Y")
        if opts.get_link_tags:
            parts.append("get_link_tags=Y")
        if opts.get_target_tags:
            parts.append("get_target_tags=Y")
        if opts.tag_format is not None:
            parts.append(f"tag_format={opts.tag_format}")
        if opts.first_link:
            parts.append(f"first_link={opts.first_link}")
        if opts.link_count:
            parts.append(f"link_count={opts.link_count}")
        if opts.event_facet_filter:
            parts.append(f"event_facet_filter={opts.event_facet_filter}")
        if opts.link_facet_filter:
            parts.append(f"link_facet_filter={opts.link_facet_filter}")
        if opts.target_facet_filter:
            parts.append(f"target_facet_filter={opts.target_facet_filter}")
        if opts.category_filter:
            parts.append(f"category_filter={opts.category_filter}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _get_events_for_tag_message_header(msg: "Message") -> str:
    """Construct Get Events For Tag message header."""
    parts = ["_db_cmd=events_for_tag"]

    buffer_results = False
    include_tag_stats = False
    invert_hit_tag_filter = False
    hit_tag_filter = ""
    buffer_format = "0"

    opts = msg.neural_memory.get_events_for_tags if msg.neural_memory else None

    if opts:
        buffer_results = opts.buffer_results
        include_tag_stats = opts.include_tag_stats
        invert_hit_tag_filter = opts.invert_hit_tag_filter
        hit_tag_filter = opts.hit_tag_filter
        if opts.buffer_format:
            buffer_format = opts.buffer_format

    # Always write buffer_results (Y or N)
    parts.append("buffer_results=Y" if buffer_results else "buffer_results=N")

    if include_tag_stats:
        parts.append("include_tag_stats=Y")

    if opts:
        if opts.include_brief_hits:
            parts.append("include_brief_hits=Y")
        if opts.get_all_data:
            parts.append("get_all_data=Y")
        if opts.count_only:
            parts.append("count_only=Y")
        if opts.get_match_links:
            parts.append("get_match_links=Y")
        if opts.count_match_links:
            parts.append("count_match_links=Y")
        if opts.get_link_tags:
            parts.append("get_link_tags=Y")
        if opts.get_target_tags:
            parts.append("get_target_tags=Y")
        if invert_hit_tag_filter:
            parts.append("invert_hit_tag_filter=Y")

        if opts.event_pattern:
            parts.append(f"event={_force_ascii(opts.event_pattern)}")
        if opts.event_pattern_high:
            parts.append(f"event_high={_force_ascii(opts.event_pattern_high)}")
        if opts.link_tag_filter:
            parts.append(f"link_tag_filter={_force_ascii(opts.link_tag_filter)}")
        if opts.linked_events_filter:
            parts.append(f"linked_events_tag_filter={_force_ascii(opts.linked_events_filter)}")
        if opts.link_category:
            parts.append(f"link_category={opts.link_category}")
        if opts.owner:
            parts.append(f"owner={_force_ascii(opts.owner)}")
        elif opts.owner_unique_id:
            parts.append(f"owner_unique_id={opts.owner_unique_id}")
        if hit_tag_filter:
            parts.append(f"hit_tag_filter={_force_ascii(hit_tag_filter)}")

        if opts.first_link > 0:
            parts.append(f"first_link={opts.first_link}")
        if opts.link_count > 0:
            parts.append(f"link_count={opts.link_count}")
        if opts.events_per_message != 0:
            parts.append(f"events_per_message={opts.events_per_message}")
        if opts.start_result > 0:
            parts.append(f"start_result={opts.start_result}")
        if opts.end_result > 0:
            parts.append(f"end_result={opts.end_result}")
        if opts.min_event_hits > 0:
            parts.append(f"min_event_hits={opts.min_event_hits}")

    # Always write buffer_format (defaults to "0")
    parts.append(f"buffer_format={buffer_format}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _store_batch_events_message_header(msg: "Message") -> str:
    """Construct Store Batch Events message header."""
    parts = ["_db_cmd=store_batch"]

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _store_batch_tags_message_header(msg: "Message") -> str:
    """Construct Store Batch Tags message header."""
    parts = ["_db_cmd=tag_store_batch"]

    if msg.event:
        if msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")
        elif msg.event.id:
            parts.append(f"event_id={_force_ascii(msg.event.id)}")

        if msg.event.owner:
            parts.append(f"owner={msg.event.owner}")
        elif msg.event.owner_unique_id:
            parts.append(f"owner_unique_id={msg.event.owner_unique_id}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _batch_link_events_message_header(msg: "Message") -> str:
    """Construct Batch Link Events message header."""
    parts = ["_db_cmd=link_batch"]

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)
