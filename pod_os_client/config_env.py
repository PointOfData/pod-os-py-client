"""Build a Config from PODOS_* environment variables.

Intended for Category 1 (self-registering) containers that receive
gateway connection details via environment rather than INI files.

Recognized variables:

    PODOS_GATEWAY_HOST, PODOS_GATEWAY_PORT, PODOS_GATEWAY_FQN,
    PODOS_ACTOR_NAME, PODOS_PASSCODE,
    PODOS_RECONNECT_ENABLED, PODOS_RECONNECT_MAX_RETRIES,
    PODOS_RECONNECT_INITIAL_BACKOFF, PODOS_RECONNECT_MAX_BACKOFF,
    PODOS_RECONNECT_BACKOFF_MULTIPLIER,
    PODOS_CONCURRENT_MODE, PODOS_EXTERNAL_RECEIVER,
    PODOS_DIAL_TIMEOUT, PODOS_SEND_TIMEOUT, PODOS_RECEIVE_TIMEOUT,
    PODOS_LOG_LEVEL

Unset variables are left at their default value. Numeric durations are in seconds.
"""

import os

from pod_os_client.config import Config

__all__ = ["config_from_env"]


def config_from_env() -> Config:
    """Read PODOS_* environment variables and return a populated Config."""
    host = os.getenv("PODOS_GATEWAY_HOST", "")
    port_str = os.getenv("PODOS_GATEWAY_PORT", "0")
    port = _parse_int(port_str) or 62312

    kwargs: dict = {
        "host": host or "localhost",
        "port": port,
        "network": "tcp",
    }

    fqn = os.getenv("PODOS_GATEWAY_FQN")
    if fqn:
        kwargs["gateway_actor_name"] = fqn

    actor_name = os.getenv("PODOS_ACTOR_NAME")
    if actor_name:
        kwargs["client_name"] = actor_name

    passcode = os.getenv("PODOS_PASSCODE")
    if passcode:
        kwargs["passcode"] = passcode

    concurrent = os.getenv("PODOS_CONCURRENT_MODE")
    if concurrent:
        kwargs["enable_concurrent_mode"] = _parse_bool(concurrent)

    external_receiver = os.getenv("PODOS_EXTERNAL_RECEIVER")
    if external_receiver:
        kwargs["external_receiver"] = _parse_bool(external_receiver)

    dial_timeout = os.getenv("PODOS_DIAL_TIMEOUT")
    if dial_timeout:
        secs = _parse_float(dial_timeout)
        if secs > 0:
            kwargs["dial_timeout"] = secs

    send_timeout = os.getenv("PODOS_SEND_TIMEOUT")
    if send_timeout:
        secs = _parse_float(send_timeout)
        if secs > 0:
            kwargs["send_timeout"] = secs

    receive_timeout = os.getenv("PODOS_RECEIVE_TIMEOUT")
    if receive_timeout:
        secs = _parse_float(receive_timeout)
        if secs > 0:
            kwargs["receive_timeout"] = secs

    log_level = os.getenv("PODOS_LOG_LEVEL")
    if log_level:
        kwargs["log_level"] = _parse_int(log_level)

    # Reconnection settings
    reconnect_enabled = os.getenv("PODOS_RECONNECT_ENABLED")
    if reconnect_enabled:
        kwargs["enable_reconnection"] = _parse_bool(reconnect_enabled)

    reconnect_max_retries = os.getenv("PODOS_RECONNECT_MAX_RETRIES")
    if reconnect_max_retries:
        kwargs["max_retries"] = _parse_int(reconnect_max_retries)

    reconnect_initial_backoff = os.getenv("PODOS_RECONNECT_INITIAL_BACKOFF")
    if reconnect_initial_backoff:
        secs = _parse_float(reconnect_initial_backoff)
        if secs > 0:
            kwargs["initial_backoff"] = secs

    reconnect_multiplier = os.getenv("PODOS_RECONNECT_BACKOFF_MULTIPLIER")
    if reconnect_multiplier:
        f = _parse_float(reconnect_multiplier)
        if f > 0:
            kwargs["backoff_multiplier"] = f

    reconnect_max_backoff = os.getenv("PODOS_RECONNECT_MAX_BACKOFF")
    if reconnect_max_backoff:
        secs = _parse_float(reconnect_max_backoff)
        if secs > 0:
            kwargs["max_backoff"] = secs

    return Config(**kwargs)


def _parse_bool(v: str) -> bool:
    return v.strip().lower() in ("true", "1", "yes", "y")


def _parse_int(v: str) -> int:
    try:
        return int(v.strip())
    except (ValueError, TypeError):
        return 0


def _parse_float(v: str) -> float:
    try:
        return float(v.strip())
    except (ValueError, TypeError):
        return 0.0
