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


def _build_raw_message(
    to: str = "actor@gw",
    from_: str = "client@gw",
    header: str = "",
    message_type: int = 1001,
    data_type: int = 0,
    payload: bytes = b"",
) -> bytes:
    to_b = to.encode("ascii")
    from_b = from_.encode("ascii")
    header_b = header.encode("ascii")

    payload_len = f"x{len(payload):08x}"
    to_len = f"x{len(to_b):08x}"
    from_len = f"x{len(from_b):08x}"
    header_len = f"x{len(header_b):08x}"
    msg_type = f"{message_type:09d}"
    dt = f"{data_type:09d}"

    total = (
        len(to_b) + 9
        + len(from_b) + 9
        + len(header_b) + 9
        + len(msg_type)
        + len(dt)
        + len(payload) + 9
        + 9
    )
    total_enc = f"x{total:08x}"

    prefix = (
        total_enc + to_len + from_len + header_len
        + msg_type + dt + payload_len
    )
    return prefix.encode("ascii") + to_b + from_b + header_b + payload


def test_decode_store_batch_events_response_ignores_total_event_hits() -> None:
    """store_batch must use _count, not global _total_event_hits."""
    payload = (
        "_status=OK\t_event_id=evt1\tunique_id=hf_eo_1\n"
        "_status=OK\t_event_id=evt2\tunique_id=hf_eo_2\n"
        "_status=OK\t_event_id=evt3\tunique_id=hf_eo_3"
    ).encode("ascii")
    header = (
        "_type=store_batch\t_status=OK\t_count=3\t"
        "_total_event_hits=1842490433\t_msg_id=msg-456"
    )
    raw = _build_raw_message(header=header, payload=payload)

    decoded = decode_message(raw)

    assert decoded.intent == "StoreBatchEventsResponse"
    assert decoded.response is not None
    assert decoded.response.total_events == 3
    assert decoded.response.storage_success_count == 3
    assert decoded.response.storage_error_count == 0
    assert decoded.response.store_batch_event_record is not None
    assert decoded.response.store_batch_event_record.event_count == 3
    assert len(decoded.response.store_batch_event_record.event_results) == 3


def test_decode_store_batch_links_response_uses_links_ok() -> None:
    header = (
        "_type=link_batch\t_status=OK\t_total_link_requests_found=2\t"
        "_links_ok=2\t_links_with_errors=0\t_total_event_hits=999999"
    )
    payload = (
        "_status=OK\tevent_id=link1\tevent_id_a=evt1\tevent_id_b=evt2"
    ).encode("ascii")
    raw = _build_raw_message(header=header, payload=payload)

    decoded = decode_message(raw)

    assert decoded.intent == "StoreBatchLinksResponse"
    assert decoded.response is not None
    assert decoded.response.total_events == 2
    assert decoded.response.storage_success_count == 2
    assert decoded.response.storage_error_count == 0
