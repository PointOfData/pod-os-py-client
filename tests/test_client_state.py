"""Tests for ConnectionState, state observer, and reconnect primitives."""

import asyncio

import pytest

from pod_os_client.client import Client, ConnectionState
from pod_os_client.config import Config, ReconnectConfig


class TestConnectionState:
    def test_string_values(self):
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.RECONNECT_FAILED.value == "reconnect_failed"

    def test_all_states_exist(self):
        assert len(ConnectionState) == 4


class TestReconnectConfig:
    def test_defaults(self):
        rc = ReconnectConfig()
        assert rc.enabled is True
        assert rc.max_retries == 10
        assert rc.initial_backoff == 1.0
        assert rc.backoff_multiplier == 2.0
        assert rc.max_backoff == 60.0

    def test_config_builds_reconnect_config_from_flat_fields(self):
        cfg = Config(host="localhost", port=62312, enable_reconnection=False, max_retries=5)
        assert cfg.reconnect_config is not None
        assert cfg.reconnect_config.enabled is False
        assert cfg.reconnect_config.max_retries == 5

    def test_explicit_reconnect_config_takes_precedence(self):
        rc = ReconnectConfig(enabled=False, max_retries=99)
        cfg = Config(host="localhost", port=62312, reconnect_config=rc)
        assert cfg.reconnect_config.max_retries == 99

    def test_validation_max_retries(self):
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            ReconnectConfig(max_retries=-1)

    def test_validation_initial_backoff(self):
        with pytest.raises(ValueError, match="initial_backoff must be positive"):
            ReconnectConfig(initial_backoff=0)

    def test_validation_backoff_multiplier(self):
        with pytest.raises(ValueError, match="backoff_multiplier must be >= 1"):
            ReconnectConfig(backoff_multiplier=0.5)

    def test_validation_max_backoff(self):
        with pytest.raises(ValueError, match="max_backoff must be positive"):
            ReconnectConfig(max_backoff=0)


class TestStateObserver:
    def test_emit_state_no_handler(self):
        """Emitting state with no handler should not raise."""
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._emit_state(ConnectionState.DISCONNECTED, Exception("test"))

    def test_on_connection_state_change(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        transitions: list[tuple[ConnectionState, Exception | None]] = []

        def handler(state, err):
            transitions.append((state, err))

        client.on_connection_state_change(handler)
        trigger = Exception("EOF")
        client._emit_state(ConnectionState.DISCONNECTED, trigger)
        client._emit_state(ConnectionState.RECONNECTING, trigger)
        client._emit_state(ConnectionState.CONNECTED, None)

        assert len(transitions) == 3
        assert transitions[0] == (ConnectionState.DISCONNECTED, trigger)
        assert transitions[1] == (ConnectionState.RECONNECTING, trigger)
        assert transitions[2] == (ConnectionState.CONNECTED, None)

    def test_handler_replacement(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        called1: list[ConnectionState] = []
        called2: list[ConnectionState] = []
        client.on_connection_state_change(lambda s, e: called1.append(s))
        client.on_connection_state_change(lambda s, e: called2.append(s))
        client._emit_state(ConnectionState.DISCONNECTED, None)
        assert len(called1) == 0
        assert len(called2) == 1

    def test_unregister_handler(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        called: list[ConnectionState] = []
        client.on_connection_state_change(lambda s, e: called.append(s))
        client.on_connection_state_change(None)
        client._emit_state(ConnectionState.DISCONNECTED, None)
        assert len(called) == 0


class TestWaitForReconnect:
    @pytest.mark.asyncio
    async def test_returns_true_when_already_connected(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._connected = True
        client._connection = object()  # type: ignore[assignment]
        result = await client._wait_for_reconnect(timeout=0.1)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_reconnecting(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._connected = False
        result = await client._wait_for_reconnect(timeout=0.1)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._connected = False
        client._reconnecting = True
        client._reconnect_event.clear()
        result = await client._wait_for_reconnect(timeout=0.05)
        assert result is False

    @pytest.mark.asyncio
    async def test_unblocks_when_event_set(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._connected = False
        client._reconnecting = True
        client._reconnect_event.clear()

        async def set_connected():
            await asyncio.sleep(0.02)
            client._connected = True
            client._connection = object()  # type: ignore[assignment]
            client._reconnect_event.set()

        task = asyncio.create_task(set_connected())
        result = await client._wait_for_reconnect(timeout=2.0)
        assert result is True
        await task


class TestClosedGuard:
    def test_close_sets_closed(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        assert client._closed is False

    @pytest.mark.asyncio
    async def test_close_marks_closed(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        await client.close()
        assert client._closed is True

    @pytest.mark.asyncio
    async def test_close_unblocks_waiters(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._connected = False
        client._reconnecting = True
        client._reconnect_event.clear()

        async def close_after_delay():
            await asyncio.sleep(0.02)
            await client.close()

        task = asyncio.create_task(close_after_delay())
        result = await client._wait_for_reconnect(timeout=2.0)
        assert result is False
        await task

    @pytest.mark.asyncio
    async def test_reconnect_aborts_when_closed(self):
        cfg = Config(host="localhost", port=62312)
        client = Client(cfg)
        client._closed = True
        await client._reconnect(trigger_err=Exception("test"))
        assert client._reconnecting is False
