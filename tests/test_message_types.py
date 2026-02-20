"""Tests for message types."""

from pod_os_client.message.types import (
    EventFields,
    Message,
    PayloadFields,
    Tag,
)


def test_message_creation() -> None:
    """Test creating a basic message."""
    msg = Message(
        to="actor@gateway",
        from_="client@gateway",
        intent="GatewayId",
        message_id="test-123",
    )

    assert msg.to == "actor@gateway"
    assert msg.from_ == "client@gateway"
    assert msg.intent == "GatewayId"
    assert msg.message_id == "test-123"


def test_message_with_event() -> None:
    """Test message with event fields."""
    event = EventFields(
        id="2024.01.15.12.30.45.123456@actor",
        unique_id="unique-123",
        type="test_event",
    )

    msg = Message(
        to="actor@gateway",
        from_="client@gateway",
        intent="StoreEvent",
        message_id="test-123",
        event=event,
    )

    assert msg.event is not None
    assert msg.event.id == "2024.01.15.12.30.45.123456@actor"
    assert msg.event.unique_id == "unique-123"
    assert msg.event_id() == "2024.01.15.12.30.45.123456@actor"


def test_message_with_payload() -> None:
    """Test message with payload."""
    payload = PayloadFields(
        data="test data",
        mime_type="text/plain",
        data_size=9,
    )

    msg = Message(
        to="actor@gateway",
        from_="client@gateway",
        intent="ActorRequest",
        message_id="test-123",
        payload=payload,
    )

    assert msg.payload is not None
    assert msg.payload.data == "test data"
    assert msg.payload_data() == "test data"


def test_tag_value_conversion() -> None:
    """Test tag value conversion methods."""
    # String tag
    tag_str = Tag(key="name", value="test", frequency=1)
    str_val, is_str = tag_str.string_value()
    assert is_str
    assert str_val == "test"

    # Int tag
    tag_int = Tag(key="count", value=42, frequency=1)
    int_val, is_int = tag_int.int_value()
    assert is_int
    assert int_val == 42

    # Float tag
    tag_float = Tag(key="score", value=3.14, frequency=1)
    float_val, is_float = tag_float.float_value()
    assert is_float
    assert float_val == 3.14

    # Bool tag
    tag_bool = Tag(key="active", value=True, frequency=1)
    bool_val, is_bool = tag_bool.bool_value()
    assert is_bool
    assert bool_val is True
