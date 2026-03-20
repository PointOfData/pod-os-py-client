"""Tests for batch payload encoding functionality."""

import base64
import json

import pytest

from pod_os_client.errors import EncodeError
from pod_os_client.message.encoder import (
    encode_message,
    format_batch_events_payload,
    format_batch_link_events_payload,
    format_batch_tags_payload,
    serialize_tag_value,
)
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    BatchEventSpec,
    BatchLinkEventSpec,
    EventFields,
    LinkFields,
    Message,
    NeuralMemoryFields,
    PayloadFields,
    Tag,
)


def test_serialize_tag_value_string():
    """Test serializing string values."""
    assert serialize_tag_value("hello") == "hello"
    assert serialize_tag_value("") == ""


def test_serialize_tag_value_int():
    """Test serializing integer values."""
    assert serialize_tag_value(42) == "42"
    assert serialize_tag_value(0) == "0"
    assert serialize_tag_value(-10) == "-10"


def test_serialize_tag_value_float():
    """Test serializing float values."""
    assert serialize_tag_value(3.14) == "3.14"
    assert serialize_tag_value(0.0) == "0.0"


def test_serialize_tag_value_bool():
    """Test serializing boolean values."""
    assert serialize_tag_value(True) == "true"
    assert serialize_tag_value(False) == "false"


def test_serialize_tag_value_bytes():
    """Test serializing bytes values with base64 encoding."""
    data = b"hello world"
    result = serialize_tag_value(data)
    expected = base64.standard_b64encode(data).decode("ascii")
    assert result == expected


def test_serialize_tag_value_dict():
    """Test serializing dict values as JSON."""
    data = {"key": "value", "number": 42}
    result = serialize_tag_value(data)
    parsed = json.loads(result)
    assert parsed == data


def test_serialize_tag_value_list():
    """Test serializing list values as JSON."""
    data = ["item1", "item2", 42]
    result = serialize_tag_value(data)
    parsed = json.loads(result)
    assert parsed == data


def test_serialize_tag_value_none():
    """Test serializing None returns empty string."""
    assert serialize_tag_value(None) == ""


def test_format_batch_events_payload_empty():
    """Test formatting empty events list."""
    result = format_batch_events_payload([])
    assert result == ""


def test_format_batch_events_payload_single():
    """Test formatting single event."""
    event = EventFields(
        unique_id="uuid1",
        type="test_event",
        owner="$sys",
        timestamp="+1234567890.123456",
    )
    spec = BatchEventSpec(event=event, tags=[])
    
    result = format_batch_events_payload([spec])
    
    assert "unique_id=uuid1" in result
    assert "type=test_event" in result
    assert "owner=$sys" in result
    assert "timestamp=+1234567890.123456" in result
    # Fields should be tab-separated
    assert "\t" in result


def test_format_batch_events_payload_with_tags():
    """Test formatting event with tags."""
    event = EventFields(unique_id="uuid1", type="test")
    tags = [
        Tag(key="category", value="important", frequency=1),
        Tag(key="status", value="active", frequency=2),
    ]
    spec = BatchEventSpec(event=event, tags=tags)
    
    result = format_batch_events_payload([spec])
    
    assert "unique_id=uuid1" in result
    assert "tag_0=1:category=important" in result
    assert "tag_1=2:status=active" in result


def test_format_batch_events_payload_multiple():
    """Test formatting multiple events."""
    event1 = EventFields(unique_id="uuid1", type="type1")
    event2 = EventFields(unique_id="uuid2", type="type2")
    
    specs = [
        BatchEventSpec(event=event1, tags=[]),
        BatchEventSpec(event=event2, tags=[]),
    ]
    
    result = format_batch_events_payload(specs)
    
    lines = result.split("\n")
    assert len(lines) == 2
    assert "uuid1" in lines[0]
    assert "uuid2" in lines[1]


def test_format_batch_events_payload_with_location():
    """Test formatting event with location."""
    event = EventFields(
        unique_id="uuid1",
        location="TERRA|47.6|-122.5",
        location_separator="|",
    )
    spec = BatchEventSpec(event=event, tags=[])
    
    result = format_batch_events_payload([spec])
    
    assert "loc=TERRA|47.6|-122.5" in result
    # Default separator is always emitted (matches Go wire format)
    assert "loc_delim=|" in result


def test_format_batch_link_events_payload_empty():
    """Test formatting empty link events list."""
    result = format_batch_link_events_payload([])
    assert result == ""


def test_format_batch_link_events_payload_single():
    """Test formatting single link event."""
    event = EventFields(unique_id="uuid1", type="test")
    link = LinkFields(
        event_a="evt1",
        event_b="evt2",
        strength_a=1.0,
        strength_b=0.5,
        category="related",
    )
    spec = BatchLinkEventSpec(event=event, link=link)
    
    result = format_batch_link_events_payload([spec])
    
    assert "unique_id=uuid1" in result
    assert "event_id_a=evt1" in result
    assert "event_id_b=evt2" in result
    assert "strength_a=1.0" in result
    assert "strength_b=0.5" in result
    assert "category=related" in result


def test_format_batch_link_events_payload_multiple():
    """Test formatting multiple link events."""
    event1 = EventFields(unique_id="uuid1")
    link1 = LinkFields(event_a="e1", event_b="e2", strength_a=1.0, strength_b=1.0)
    
    event2 = EventFields(unique_id="uuid2")
    link2 = LinkFields(event_a="e3", event_b="e4", strength_a=0.5, strength_b=0.5)
    
    specs = [
        BatchLinkEventSpec(event=event1, link=link1),
        BatchLinkEventSpec(event=event2, link=link2),
    ]
    
    result = format_batch_link_events_payload(specs)
    
    lines = result.split("\n")
    assert len(lines) == 2
    assert "uuid1" in lines[0]
    assert "uuid2" in lines[1]


def test_format_batch_link_events_payload_with_owner():
    """Test formatting link with owner fields."""
    event = EventFields(unique_id="uuid1")
    link = LinkFields(
        event_a="evt1",
        event_b="evt2",
        strength_a=1.0,
        strength_b=1.0,
        owner_unique_id="owner_uuid",
        owner_event_id="owner_event_id_val",
    )
    spec = BatchLinkEventSpec(event=event, link=link)
    
    result = format_batch_link_events_payload([spec])
    
    assert "owner_unique_id=owner_uuid" in result
    assert "owner_event_id=owner_event_id_val" in result


def test_format_batch_events_payload_tag_without_key():
    """Test formatting tag with only value (no key)."""
    event = EventFields(unique_id="uuid1")
    tags = [Tag(value="simple_value", frequency=1)]
    spec = BatchEventSpec(event=event, tags=tags)
    
    result = format_batch_events_payload([spec])
    
    assert "tag_0=1:simple_value" in result


def test_format_batch_events_payload_complex_tag_value():
    """Test formatting tag with complex value types."""
    event = EventFields(unique_id="uuid1")
    tags = [
        Tag(key="dict_tag", value={"nested": "data"}, frequency=1),
        Tag(key="list_tag", value=[1, 2, 3], frequency=1),
        Tag(key="bool_tag", value=True, frequency=1),
    ]
    spec = BatchEventSpec(event=event, tags=tags)
    
    result = format_batch_events_payload([spec])
    
    # Dict and list should be JSON serialized
    assert "dict_tag=" in result
    assert "list_tag=" in result
    assert "bool_tag=true" in result


def test_format_batch_tags_payload_empty():
    """Test formatting empty tags list returns empty string."""
    assert format_batch_tags_payload([]) == ""


def test_format_batch_tags_payload_single():
    """Test formatting single tag (frequency=key=value)."""
    tags = [Tag(frequency=1, key="key1", value="value1")]
    result = format_batch_tags_payload(tags)
    assert result == "1=key1=value1"


def test_format_batch_tags_payload_multiple():
    """Test formatting multiple tags, newline-separated; match Go test expectations."""
    tags = [
        Tag(frequency=1, key="key1", value="value1"),
        Tag(frequency=5, key="key2", value="value2"),
        Tag(frequency=10, key="key3", value=123),
    ]
    result = format_batch_tags_payload(tags)
    lines = result.split("\n")
    assert len(lines) == 3
    assert lines[0] == "1=key1=value1"
    assert lines[1] == "5=key2=value2"
    assert lines[2] == "10=key3=123"


def test_format_batch_tags_payload_no_trailing_newline():
    """Test no trailing newline after last line."""
    tags = [Tag(frequency=1, key="k", value="v")]
    result = format_batch_tags_payload(tags)
    assert result == "1=k=v"
    assert not result.endswith("\n")


# ---- encode_message intent-aware tests ----


def _minimal_message(to: str = "mem@gateway", from_: str = "client@gateway", **kwargs) -> Message:
    intent = kwargs.pop("intent", "StoreBatchEvents")
    return Message(
        to=to,
        from_=from_,
        intent=intent,
        client_name="client",
        message_id="msg-1",
        **kwargs,
    )


def test_encode_store_batch_events_structured_payload():
    """StoreBatchEvents with list[BatchEventSpec] produces formatted payload body."""
    event = EventFields(unique_id="ev1", type="t", owner="$sys")
    spec = BatchEventSpec(event=event, tags=[])
    msg = _minimal_message(
        intent=IntentType.StoreBatchEvents.name,
        payload=PayloadFields(data=[spec]),
    )
    encoded = encode_message(msg, IntentType.StoreBatchEvents, "conv-1")
    expected_body = format_batch_events_payload([spec]).encode("utf-8")
    assert encoded.endswith(expected_body)


def test_encode_store_batch_events_string_payload():
    """StoreBatchEvents with str payload (backward compat) encodes as UTF-8."""
    msg = _minimal_message(
        intent=IntentType.StoreBatchEvents.name,
        payload=PayloadFields(data="already\tformatted\nline2"),
    )
    encoded = encode_message(msg, IntentType.StoreBatchEvents, "conv-1")
    assert encoded.endswith("already\tformatted\nline2".encode("utf-8"))


def test_encode_store_batch_events_list_str_payload():
    """StoreBatchEvents with list[str] payload (backward compat) joins and encodes as UTF-8."""
    msg = _minimal_message(
        intent=IntentType.StoreBatchEvents.name,
        payload=PayloadFields(data=["part1", "part2", "part3"]),
    )
    encoded = encode_message(msg, IntentType.StoreBatchEvents, "conv-1")
    assert encoded.endswith("part1part2part3".encode("utf-8"))


def test_encode_store_batch_events_wrong_type_raises():
    """StoreBatchEvents with invalid payload type raises EncodeError."""
    msg_int = _minimal_message(
        intent=IntentType.StoreBatchEvents.name,
        payload=PayloadFields(data=42),
    )
    with pytest.raises(EncodeError, match="StoreBatchEvents requires payload.data"):
        encode_message(msg_int, IntentType.StoreBatchEvents, "conv-1")

    msg_list_mixed = _minimal_message(
        intent=IntentType.StoreBatchEvents.name,
        payload=PayloadFields(data=[BatchEventSpec(event=EventFields(unique_id="x"), tags=[]), "string"]),
    )
    with pytest.raises(EncodeError, match="StoreBatchEvents requires payload.data"):
        encode_message(msg_list_mixed, IntentType.StoreBatchEvents, "conv-1")


def test_encode_store_batch_links_structured_payload():
    """StoreBatchLinks with list[BatchLinkEventSpec] produces formatted payload body."""
    event = EventFields(unique_id="ev1")
    link = LinkFields(event_a="a", event_b="b", strength_a=1.0, strength_b=1.0)
    spec = BatchLinkEventSpec(event=event, link=link)
    msg = _minimal_message(
        intent=IntentType.StoreBatchLinks.name,
        payload=PayloadFields(data=[spec]),
    )
    encoded = encode_message(msg, IntentType.StoreBatchLinks, "conv-1")
    expected_body = format_batch_link_events_payload([spec]).encode("utf-8")
    assert encoded.endswith(expected_body)


def test_encode_store_batch_links_string_payload():
    """StoreBatchLinks with str payload (backward compat) encodes as UTF-8."""
    msg = _minimal_message(
        intent=IntentType.StoreBatchLinks.name,
        payload=PayloadFields(data="manual\tlink\nline2"),
    )
    encoded = encode_message(msg, IntentType.StoreBatchLinks, "conv-1")
    assert encoded.endswith("manual\tlink\nline2".encode("utf-8"))


def test_encode_store_batch_links_wrong_type_raises():
    """StoreBatchLinks with invalid payload type raises EncodeError."""
    msg = _minimal_message(
        intent=IntentType.StoreBatchLinks.name,
        payload=PayloadFields(data=42),
    )
    with pytest.raises(EncodeError, match="StoreBatchLinks requires payload.data"):
        encode_message(msg, IntentType.StoreBatchLinks, "conv-1")


def test_encode_store_batch_tags_from_payload_data():
    """StoreBatchTags with payload.data = list[Tag] produces formatted payload body."""
    tags = [
        Tag(frequency=1, key="k1", value="v1"),
        Tag(frequency=2, key="k2", value=42),
    ]
    msg = _minimal_message(
        intent=IntentType.StoreBatchTags.name,
        payload=PayloadFields(data=tags),
    )
    encoded = encode_message(msg, IntentType.StoreBatchTags, "conv-1")
    expected_body = format_batch_tags_payload(tags).encode("utf-8")
    assert encoded.endswith(expected_body)


def test_encode_store_batch_tags_string_payload():
    """StoreBatchTags with str payload (backward compat) encodes as UTF-8."""
    msg = _minimal_message(
        intent=IntentType.StoreBatchTags.name,
        payload=PayloadFields(data="1=k1=v1\n2=k2=v2"),
    )
    encoded = encode_message(msg, IntentType.StoreBatchTags, "conv-1")
    assert encoded.endswith("1=k1=v1\n2=k2=v2".encode("utf-8"))


def test_encode_store_batch_tags_wrong_payload_type_raises():
    """StoreBatchTags with payload that is not list[Tag] or str raises EncodeError."""
    msg = _minimal_message(
        intent=IntentType.StoreBatchTags.name,
        payload=PayloadFields(data=42),
    )
    with pytest.raises(EncodeError, match="StoreBatchTags requires"):
        encode_message(msg, IntentType.StoreBatchTags, "conv-1")


def test_encode_gateway_id_payload_ignored():
    """GatewayId ignores payload; encoded message has empty payload body."""
    msg = Message(
        to="$system@gateway",
        from_="client@gateway",
        intent="GatewayId",
        client_name="client",
        message_id="test-123",
        payload=PayloadFields(data="ignored"),
    )
    encoded = encode_message(msg, IntentType.GatewayId, "conv-123")
    # Payload is last in wire format; GatewayId uses empty data_bytes
    # So encoded should end with header part only (no extra payload bytes after header)
    # Wire: ... header_length_encoded, message_type, data_type, payload_len, to, from_, header, [data_bytes]
    # payload_data_length_encoded for 0 bytes is x00000000, so 9 chars. So after header we have 0 data bytes.
    assert encoded.endswith(b"x00000000") is False  # that's payload length, not the end
    # Decode and check: total length - payload length = header part length. Simpler: encoded should not contain b"ignored"
    assert b"ignored" not in encoded


def test_encode_actor_echo_string_payload():
    """Other intents (e.g. ActorEcho) accept string payload as UTF-8 body."""
    msg = _minimal_message(
        intent=IntentType.ActorEcho.name,
        payload=PayloadFields(data="Hello, Pod-OS!"),
    )
    encoded = encode_message(msg, IntentType.ActorEcho, "conv-1")
    assert b"Hello, Pod-OS!" in encoded
