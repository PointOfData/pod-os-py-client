"""Pod-OS message header construction."""

from typing import TYPE_CHECKING

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
    
    return "\t".join(parts) if parts else ""


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
        if msg.event.location:
            parts.append(f"loc={msg.event.location}")
        if msg.event.location_separator:
            parts.append(f"loc_delim={msg.event.location_separator}")
        if msg.event.type:
            parts.append(f"type={msg.event.type}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _link_events_message_header(msg: "Message") -> str:
    """Construct Link Events message header."""
    parts = ["_db_cmd=link"]

    if msg.neural_memory and msg.neural_memory.link:
        link = msg.neural_memory.link
        if link.unique_id_a:
            parts.append(f"unique_id_a={link.unique_id_a}")
        if link.unique_id_b:
            parts.append(f"unique_id_b={link.unique_id_b}")
        if link.event_a:
            parts.append(f"event_id_a={_force_ascii(link.event_a)}")
        if link.event_b:
            parts.append(f"event_id_b={_force_ascii(link.event_b)}")
        if link.strength_a:
            parts.append(f"strength_a={link.strength_a}")
        if link.strength_b:
            parts.append(f"strength_b={link.strength_b}")
        if link.category:
            parts.append(f"category={link.category}")
        if link.owner:
            parts.append(f"owner={link.owner}")
        if link.timestamp:
            parts.append(f"timestamp={link.timestamp}")
        if link.location:
            parts.append(f"loc={link.location}")
        if link.type:
            parts.append(f"type={link.type}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _unlink_events_message_header(msg: "Message") -> str:
    """Construct Unlink Events message header."""
    parts = ["_db_cmd=unlink"]

    if msg.neural_memory and msg.neural_memory.link:
        link = msg.neural_memory.link
        if link.unique_id_a:
            parts.append(f"unique_id_a={link.unique_id_a}")
        if link.unique_id_b:
            parts.append(f"unique_id_b={link.unique_id_b}")
        if link.event_a:
            parts.append(f"event_id_a={_force_ascii(link.event_a)}")
        if link.event_b:
            parts.append(f"event_id_b={_force_ascii(link.event_b)}")

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

    if msg.neural_memory and msg.neural_memory.get_events_for_tags:
        opts = msg.neural_memory.get_events_for_tags
        if opts.event_pattern:
            parts.append(f"event={opts.event_pattern}")
        if opts.event_pattern_high:
            parts.append(f"event_high={opts.event_pattern_high}")
        if opts.include_brief_hits:
            parts.append("include_brief_hits=Y")
        if opts.get_all_data:
            parts.append("get_all_data=Y")
        if opts.first_link:
            parts.append(f"first_link={opts.first_link}")
        if opts.link_count:
            parts.append(f"link_count={opts.link_count}")
        if opts.events_per_message:
            parts.append(f"events_per_message={opts.events_per_message}")
        if opts.start_result:
            parts.append(f"start_result={opts.start_result}")
        if opts.end_result:
            parts.append(f"end_result={opts.end_result}")
        if opts.min_event_hits:
            parts.append(f"min_event_hits={opts.min_event_hits}")
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
        if opts.link_category:
            parts.append(f"link_category={opts.link_category}")
        if opts.owner:
            parts.append(f"owner={opts.owner}")
        if opts.owner_unique_id:
            parts.append(f"owner_unique_id={opts.owner_unique_id}")
        if opts.buffer_results:
            parts.append("buffer_results=Y")
        if opts.include_tag_stats:
            parts.append("include_tag_stats=Y")

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
        if msg.event.id:
            parts.append(f"event_id={_force_ascii(msg.event.id)}")
        elif msg.event.unique_id:
            parts.append(f"unique_id={msg.event.unique_id}")

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)


def _batch_link_events_message_header(msg: "Message") -> str:
    """Construct Batch Link Events message header."""
    parts = ["_db_cmd=link_batch"]

    if msg.message_id:
        parts.append(f"_msg_id={msg.message_id}")

    return "\t".join(parts)
