"""Build a Config from INI key-value pairs.

Populates a Config from INI key-value pairs as parsed by Pod-OS actor binaries
(flat key=value format, no section headers).

Recognized keys:

    host, port, agent (gateway_actor_name), client (client_name),
    stream_messages, concurrent_mode, external_receiver,
    reconnect_enabled, reconnect_max_retries, reconnect_initial_backoff,
    reconnect_backoff_multiplier, reconnect_max_backoff,
    dial_timeout, send_timeout, receive_timeout,
    retry_count, retry_backoff, retry_backoff_multiplier,
    passcode, log_level

Unrecognized keys are silently ignored. Numeric durations are in seconds.
"""

from pod_os_client.config import Config

__all__ = ["config_from_ini"]


def config_from_ini(kvs: dict[str, str]) -> Config:
    """Read key-value pairs and return a populated Config.

    Args:
        kvs: flat dictionary of INI key=value pairs

    Returns:
        Config populated from the INI values
    """
    kwargs: dict = {
        "host": "localhost",
        "port": 62312,
        "network": "tcp",
    }

    for key, value in kvs.items():
        k = key.strip().lower()

        if k == "host":
            kwargs["host"] = value
        elif k == "port":
            p = _parse_int(value)
            if p > 0:
                kwargs["port"] = p
        elif k == "agent":
            kwargs["gateway_actor_name"] = value
        elif k == "client":
            kwargs["client_name"] = value
        elif k == "passcode":
            kwargs["passcode"] = value
        elif k == "stream_messages":
            kwargs["enable_streaming"] = _parse_bool(value) or None
        elif k == "concurrent_mode":
            kwargs["enable_concurrent_mode"] = _parse_bool(value)
        elif k == "external_receiver":
            kwargs["external_receiver"] = _parse_bool(value)
        elif k == "dial_timeout":
            secs = _parse_float(value)
            if secs > 0:
                kwargs["dial_timeout"] = secs
        elif k == "send_timeout":
            secs = _parse_float(value)
            if secs > 0:
                kwargs["send_timeout"] = secs
        elif k == "receive_timeout":
            secs = _parse_float(value)
            if secs > 0:
                kwargs["receive_timeout"] = secs
        elif k == "log_level":
            kwargs["log_level"] = _parse_int(value)
        elif k == "reconnect_enabled":
            kwargs["enable_reconnection"] = _parse_bool(value)
        elif k == "reconnect_max_retries":
            kwargs["max_retries"] = _parse_int(value)
        elif k == "reconnect_initial_backoff":
            secs = _parse_float(value)
            if secs > 0:
                kwargs["initial_backoff"] = secs
        elif k == "reconnect_backoff_multiplier":
            f = _parse_float(value)
            if f > 0:
                kwargs["backoff_multiplier"] = f
        elif k == "reconnect_max_backoff":
            secs = _parse_float(value)
            if secs > 0:
                kwargs["max_backoff"] = secs

    return Config(**kwargs)


def _parse_bool(v: str) -> bool:
    return v.strip().upper() in ("Y", "YES", "TRUE", "1")


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
