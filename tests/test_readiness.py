"""Tests for readiness gate and health probe helpers."""

from __future__ import annotations

import asyncio

import pytest

from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, ResponseFields
from pod_os_client.readiness.gate import (
    ActorAIPReadinessConfig,
    GatewayReadinessProbe,
    wait_for_actor_aip_ready,
    wait_for_gateway_aip_ready,
)
from pod_os_client.readiness.health_probe import (
    actor_health_probe_succeeded,
    build_actor_health_probe_message,
    is_neural_memory_backed_for_health_probe,
)


def test_neural_memory_types() -> None:
    for typ in ("neural_memory", "pod_db", "evolutionary-neural-memory", "Neural_Memory", "neural-memory"):
        assert is_neural_memory_backed_for_health_probe(typ)
    for typ in ("socket", "router", "shell", "", "gateway"):
        assert not is_neural_memory_backed_for_health_probe(typ)


def test_probe_intent_by_type() -> None:
    socket_msg = build_actor_health_probe_message(
        "mysocket@gateway.pod-os.com", "client@zeroth.pod-os.com", "client", "socket"
    )
    assert socket_msg.intent == IntentType.StatusRequest.name
    assert socket_msg.message_id

    nm_msg = build_actor_health_probe_message(
        "account@zeroth.pod-os.com", "client@zeroth.pod-os.com", "client", "neural_memory"
    )
    assert nm_msg.intent == IntentType.GetEventsForTags.name
    assert nm_msg.neural_memory is not None
    assert nm_msg.neural_memory.get_events_for_tags is not None
    assert nm_msg.neural_memory.get_events_for_tags.count_only is True


def test_probe_succeeded() -> None:
    assert actor_health_probe_succeeded(None, None)
    assert actor_health_probe_succeeded(None, Message())
    err_resp = Message(response=ResponseFields(status="ERROR", message="fail"))
    assert not actor_health_probe_succeeded(None, err_resp)
    assert not actor_health_probe_succeeded(RuntimeError("transport"), None)


def _fast_config() -> ActorAIPReadinessConfig:
    return ActorAIPReadinessConfig(timeout=0.2, initial_backoff=0.001, max_backoff=0.002)


def test_wait_succeeds_immediately() -> None:
    calls = 0

    async def send(_msg: Message, _label: str) -> Message:
        nonlocal calls
        calls += 1
        return Message()

    asyncio.run(
        wait_for_actor_aip_ready(
            send, "a@zeroth.pod-os.com", "c@zeroth.pod-os.com", "c", "socket", _fast_config()
        )
    )
    assert calls == 1


def test_gateway_uses_probe_actor() -> None:
    captured: dict[str, str] = {}

    async def send(msg: Message, _label: str) -> Message:
        captured["to"] = msg.to
        return Message()

    asyncio.run(
        wait_for_gateway_aip_ready(
            send,
            GatewayReadinessProbe(probe_actor="test@zeroth.pod-os.com", probe_actor_type="neural_memory"),
            "c@zeroth.pod-os.com",
            "c",
            _fast_config(),
        )
    )
    assert captured["to"] == "test@zeroth.pod-os.com"


def test_retries_then_succeeds() -> None:
    calls = 0

    async def send(_msg: Message, _label: str) -> Message:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("connection to gateway was lost during request")
        return Message()

    asyncio.run(
        wait_for_actor_aip_ready(
            send,
            "a@zeroth.pod-os.com",
            "c@zeroth.pod-os.com",
            "c",
            "evolutionary-neural-memory",
            _fast_config(),
        )
    )
    assert calls == 3


def test_deadline_exceeded() -> None:
    async def send(_msg: Message, _label: str) -> Message:
        raise ConnectionError("connection to gateway was lost during request")

    with pytest.raises(TimeoutError):
        asyncio.run(
            wait_for_actor_aip_ready(
                send, "a@zeroth.pod-os.com", "c@zeroth.pod-os.com", "c", "socket", _fast_config()
            )
        )


def test_message_validate_method() -> None:
    from pod_os_client.message.types import EventFields

    msg = Message(
        to="mem@zeroth.pod-os.com",
        from_="test@zeroth.pod-os.com",
        intent=IntentType.StoreData.name,
        event=EventFields(unique_id="target-uid", owner="$sys"),
    )
    errs = msg.validate()
    if errs:
        assert any(e.rule == "semantic" for e in errs)
