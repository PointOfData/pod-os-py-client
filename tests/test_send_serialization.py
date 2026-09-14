"""Tests for serialized sends and ASCII-safe wire encoding."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import EventFields, Message
from pod_os_client.message.validate import validate_raw_message


def _minimal_get_event(to: str, from_: str) -> Message:
    return Message(
        to=to,
        from_=from_,
        intent=IntentType.GetEvent.name,
        message_id="msg-ascii-1",
        event=EventFields(unique_id="page:test:1"),
    )


def test_encode_non_ascii_to_passes_wire_validation(monkeypatch):
    """Length prefixes must match post-force_ascii wire bytes."""
    monkeypatch.setenv("PODOS_VALIDATE", "1")
    # Reload validation flag if module was already imported
    import pod_os_client.message.validate as validate_mod

    monkeypatch.setattr(validate_mod, "_validation_enabled", True)

    msg = _minimal_get_event("actor@gw\u2603", "client@gw")
    encoded = encode_message(msg, IntentType.GetEvent, "conv-1")

    to_len = int(encoded[10:18], 16)
    from_len = int(encoded[19:27], 16)
    header_len = int(encoded[28:36], 16)
    assert to_len == len("actor@gw")
    assert from_len == len("client@gw")
    assert header_len > 0
    assert len(encoded) == 63 + to_len + from_len + header_len + int(encoded[55:63], 16)

    wire_errs = validate_raw_message(encoded)
    assert wire_errs == []


@pytest.mark.asyncio
async def test_concurrent_send_no_wait_serializes_writes():
    """Two send_no_wait calls must not overlap on the primary socket."""
    config = Config(host="127.0.0.1", port=62312, client_name="test", gateway_actor_name="gw")
    client = Client(config)
    client._connected = True
    client._connection = MagicMock()

    order: list[str] = []
    gate = asyncio.Event()
    release = asyncio.Event()

    async def slow_send(data: bytes) -> int:
        order.append("start")
        gate.set()
        await release.wait()
        order.append("end")
        return len(data)

    client._connection.send = AsyncMock(side_effect=slow_send)

    msg = Message(
        to="mem@gw",
        from_="test@gw",
        intent=IntentType.Keepalive.name,
        message_id="a",
    )

    async def first_send():
        await client.send_no_wait(msg)

    task = asyncio.create_task(first_send())
    await gate.wait()

    second_started = asyncio.Event()

    async def second_send():
        await client.send_no_wait(
            Message(
                to="mem@gw",
                from_="test@gw",
                intent=IntentType.Keepalive.name,
                message_id="b",
            )
        )
        second_started.set()

    task2 = asyncio.create_task(second_send())
    await asyncio.sleep(0.05)
    assert order == ["start"]
    assert not second_started.is_set()

    release.set()
    await asyncio.gather(task, task2)
    assert order == ["start", "end", "start", "end"]
