"""Tests for Config.external_receiver / send_no_wait (app-owned receive loop)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.config_env import config_from_env
from pod_os_client.config_ini import config_from_ini
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message


def test_config_external_receiver_default_false() -> None:
    cfg = Config(host="localhost", port=62312)
    assert cfg.external_receiver is False


def test_config_external_receiver_true() -> None:
    cfg = Config(host="localhost", port=62312, external_receiver=True)
    assert cfg.external_receiver is True


def test_config_from_ini_external_receiver(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = config_from_ini({"host": "h", "port": "1", "external_receiver": "true"})
    assert cfg.external_receiver is True


def test_config_from_env_external_receiver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PODOS_GATEWAY_HOST", "localhost")
    monkeypatch.setenv("PODOS_GATEWAY_PORT", "62312")
    monkeypatch.setenv("PODOS_EXTERNAL_RECEIVER", "1")
    cfg = config_from_env()
    assert cfg.external_receiver is True


@pytest.mark.asyncio
async def test_send_message_rejected_when_external_receiver() -> None:
    client = Client(Config(host="localhost", port=62312, external_receiver=True))
    client._connected = True
    client._connection = MagicMock()
    msg = Message(
        to="a@gw",
        from_="b@gw",
        intent=IntentType.ActorRequest.name,
        client_name="b",
        message_id="m1",
    )
    with pytest.raises(RuntimeError, match="external_receiver"):
        await client.send_message(msg)


@pytest.mark.asyncio
async def test_start_receiver_rejected_when_external_receiver() -> None:
    client = Client(Config(host="localhost", port=62312, external_receiver=True))
    with pytest.raises(RuntimeError, match="external_receiver"):
        client.start_receiver()


@pytest.mark.asyncio
async def test_send_no_wait_encodes_and_sends() -> None:
    client = Client(Config(host="localhost", port=62312, external_receiver=True))
    client._connected = True
    conn = MagicMock()
    conn.send = AsyncMock()
    client._connection = conn

    msg = Message(
        to="mention-detector@gw",
        from_="ingest-worker@gw",
        intent=IntentType.ActorRequest.name,
        client_name="ingest-worker",
        message_id="req-1",
    )
    await client.send_no_wait(msg)
    conn.send.assert_awaited_once()
    assert isinstance(conn.send.await_args.args[0], (bytes, bytearray))


@pytest.mark.asyncio
async def test_deliver_response_completes_pending() -> None:
    client = Client(Config(host="localhost", port=62312, external_receiver=True))
    fut = __import__("asyncio").get_running_loop().create_future()
    client._pending_responses["req-1"] = fut
    resp = Message(
        to="ingest-worker@gw",
        from_="mention-detector@gw",
        intent=IntentType.ActorResponse.name,
        client_name="mention-detector",
        message_id="req-1",
    )
    assert client.deliver_response(resp) is True
    assert fut.done()
    assert fut.result() is resp
    assert client.deliver_response(resp) is False


@pytest.mark.asyncio
async def test_reconnect_once_refuses_external_receiver() -> None:
    from pod_os_client.errors import ConnectionLostError

    client = Client(Config(host="localhost", port=62312, external_receiver=True))
    client._connected = True
    client._connection = MagicMock()
    with pytest.raises(ConnectionLostError, match="external_receiver"):
        await client._reconnect_once()
    assert client._connected is False
