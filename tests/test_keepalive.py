"""Tests for app-level keepalive support."""

from __future__ import annotations

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.message.intents import IntentType
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.types import Message


def test_config_default_keepalive_interval() -> None:
    cfg = Config(host="127.0.0.1", port=62312, client_name="test")
    assert cfg.get_keepalive_interval() == 30.0


def test_config_disabled_keepalive_interval() -> None:
    cfg = Config(host="127.0.0.1", port=62312, client_name="test", keepalive_interval=0)
    assert cfg.get_keepalive_interval() == 0.0


def test_keepalive_message_shape() -> None:
    cfg = Config(
        host="127.0.0.1",
        port=62312,
        client_name="my-client",
        gateway_actor_name="zeroth.pod-os.com",
    )
    client = Client(cfg)
    msg = Message(
        to=f"$system@{cfg.gateway_actor_name}",
        from_=f"{cfg.client_name}@{cfg.gateway_actor_name}",
        intent=IntentType.Keepalive.name,
        client_name=cfg.client_name,
        message_id="keepalive-1",
    )
    wire = encode_message(msg, IntentType.Keepalive, client._conversation_id)
    assert b"000000018" in wire
