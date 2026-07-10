"""Tests for actor health-check helpers."""

from __future__ import annotations

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.health import build_status_health_reply
from pod_os_client.message.decoder import decode_message
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message


def test_build_status_health_reply() -> None:
    cfg = Config(
        host="127.0.0.1",
        port=62312,
        client_name="socket-actor",
        gateway_actor_name="zeroth.pod-os.com",
    )
    client = Client(cfg)
    inbound = Message(
        from_="probe-client@zeroth.pod-os.com",
        message_id="probe-msg-1",
        intent=IntentType.StatusRequest.name,
    )

    reply = build_status_health_reply(client, inbound)
    assert reply.intent == IntentType.Status.name
    assert reply.message_id == "probe-msg-1"
    assert reply.to == "probe-client@zeroth.pod-os.com"
    assert reply.from_ == "socket-actor@zeroth.pod-os.com"
    assert reply.response is not None
    assert reply.response.status == "OK"
    assert reply.response.message == "actor is healthy"

    wire = encode_message(reply, IntentType.Status, client._conversation_id)
    assert b"000000003" in wire
    decoded = decode_message(wire)
    assert decoded.intent == IntentType.Status.name
    assert decoded.message_id == "probe-msg-1"
    assert decoded.response is not None
    assert decoded.response.status == "OK"


def test_build_status_health_probe_request() -> None:
    cfg = Config(
        host="127.0.0.1",
        port=62312,
        client_name="dashboard",
        gateway_actor_name="zeroth.pod-os.com",
    )
    client = Client(cfg)
    msg = Message(
        to="socket-actor@gateway.pod-os.com",
        from_="dashboard@zeroth.pod-os.com",
        intent=IntentType.StatusRequest.name,
        client_name="dashboard",
        message_id="health-1",
    )
    wire = encode_message(msg, IntentType.StatusRequest, client._conversation_id)
    assert b"000000110" in wire
    decoded = decode_message(wire)
    assert decoded.intent == IntentType.StatusRequest.name
    assert decoded.message_id == "health-1"
