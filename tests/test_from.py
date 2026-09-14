"""Tests for envelope from-address normalization (connection gateway identity)."""

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message


def _client(gateway: str = "zeroth.pod-os.com", client_name: str = "my-client") -> Client:
    return Client(
        Config(
            host="127.0.0.1",
            port=62312,
            gateway_actor_name=gateway,
            client_name=client_name,
        )
    )


def test_from_address() -> None:
    assert _client().from_address() == "my-client@zeroth.pod-os.com"


def test_normalize_message_from_rejects_disagreeing_from() -> None:
    import pytest

    client = _client()
    msg = Message(
        to="kb@skills.pod-os.com",
        from_="other@skills.pod-os.com",
        intent=IntentType.GetEvent.name,
        client_name="other",
    )
    with pytest.raises(ValueError, match="disagrees with connection identity"):
        client._normalize_message_from(msg)


def test_normalize_message_from_fills_empty_from() -> None:
    client = _client(gateway="skills.pod-os.com")
    msg = Message(
        to="kb@skills.pod-os.com",
        from_="",
        intent=IntentType.GetEvent.name,
    )
    client._normalize_message_from(msg)
    assert msg.from_ == "my-client@skills.pod-os.com"
