"""Tests for message encoder and decoder."""

import pytest

from pod_os_client.errors import EncodeError
from pod_os_client.message.decoder import decode_message
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, PayloadFields


def test_encode_gateway_id() -> None:
    """Test encoding GatewayId message."""
    msg = Message(
        to="$system@gateway",
        from_="client@gateway",
        intent="GatewayId",
        client_name="client",
        message_id="test-123",
    )

    encoded = encode_message(msg, IntentType.GatewayId, "conv-123")

    # Check that encoded data starts with length prefix
    assert len(encoded) > 63  # Minimum header size
    assert encoded[:1] == b"x"  # Length prefix starts with 'x'


def test_encode_with_payload() -> None:
    """Test encoding message with payload."""
    msg = Message(
        to="actor@gateway",
        from_="client@gateway",
        intent="ActorEcho",
        message_id="test-123",
        payload=PayloadFields(data="Hello, Pod-OS!"),
    )

    encoded = encode_message(msg, IntentType.ActorEcho, "conv-123")
    assert len(encoded) > 63
    assert b"Hello, Pod-OS!" in encoded


def test_encode_invalid_to_address() -> None:
    """Test encoding with invalid To address raises error."""
    msg = Message(
        to="invalid",  # Missing '@'
        from_="client@gateway",
        intent="GatewayId",
        message_id="test-123",
    )

    with pytest.raises(EncodeError, match="To address must be in format"):
        encode_message(msg, IntentType.GatewayId, "conv-123")


def test_decode_basic_message() -> None:
    """Test decoding a basic message."""
    # Create a simple encoded message
    msg = Message(
        to="$system@gateway",
        from_="client@gateway",
        intent="GatewayId",
        client_name="client",
        message_id="test-123",
    )

    encoded = encode_message(msg, IntentType.GatewayId, "conv-123")
    decoded = decode_message(encoded)

    assert decoded.to == "$system@gateway"
    assert decoded.from_ == "client@gateway"
    assert decoded.message_id == "test-123"


def test_encode_decode_roundtrip() -> None:
    """Test encode/decode roundtrip preserves data."""
    original = Message(
        to="actor@gateway",
        from_="client@gateway",
        intent="ActorEcho",
        message_id="test-456",
        payload=PayloadFields(data="roundtrip test"),
    )

    encoded = encode_message(original, IntentType.ActorEcho, "conv-123")
    decoded = decode_message(encoded)

    assert decoded.to == original.to
    assert decoded.from_ == original.from_
    assert decoded.message_id == original.message_id
    assert decoded.payload is not None
    assert decoded.payload.data == "roundtrip test"
