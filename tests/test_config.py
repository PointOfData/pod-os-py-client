"""Tests for Config dataclass."""

import pytest

from pod_os_client.config import Config


def test_config_valid() -> None:
    """Test valid configuration."""
    config = Config(host="localhost", port=8080, gateway_actor_name="zeroth.pod-os.com")
    assert config.host == "localhost"
    assert config.port == 8080
    assert config.network == "tcp"


def test_config_default_enable_streaming_is_none() -> None:
    """Default config has enable_streaming None (streaming on by default)."""
    config = Config(host="localhost", port=8080, gateway_actor_name="zeroth.pod-os.com")
    assert config.enable_streaming is None


def test_config_enable_streaming_false() -> None:
    """Config with enable_streaming=False is valid (streaming off)."""
    config = Config(host="localhost", port=8080, gateway_actor_name="zeroth.pod-os.com", enable_streaming=False)
    assert config.enable_streaming is False


def test_config_invalid_gateway_actor_name() -> None:
    """Test config with empty gateway_actor_name raises ValueError."""
    with pytest.raises(ValueError, match="gateway_actor_name is required"):
        Config(host="localhost", port=8080, gateway_actor_name="")


def test_config_invalid_host() -> None:
    """Test config with empty host raises ValueError."""
    with pytest.raises(ValueError, match="host is required"):
        Config(host="", port=8080, gateway_actor_name="zeroth.pod-os.com")


def test_config_invalid_port_low() -> None:
    """Test config with port 0 raises ValueError."""
    with pytest.raises(ValueError, match="port must be 1-65535"):
        Config(host="localhost", port=0, gateway_actor_name="zeroth.pod-os.com")


def test_config_invalid_port_high() -> None:
    """Test config with port > 65535 raises ValueError."""
    with pytest.raises(ValueError, match="port must be 1-65535"):
        Config(host="localhost", port=65536, gateway_actor_name="zeroth.pod-os.com")


def test_config_invalid_network() -> None:
    """Test config with invalid network type raises ValueError."""
    with pytest.raises(ValueError, match="network must be"):
        Config(host="localhost", port=8080, gateway_actor_name="zeroth.pod-os.com", network="invalid")


def test_config_invalid_timeout() -> None:
    """Test config with negative timeout raises ValueError."""
    with pytest.raises(ValueError, match="dial_timeout must be positive"):
        Config(host="localhost", port=8080, gateway_actor_name="zeroth.pod-os.com", dial_timeout=-1)


def test_config_pool_capacity() -> None:
    """Test config with invalid pool capacity raises ValueError."""
    with pytest.raises(ValueError, match="pool_max_capacity must be"):
        Config(
            host="localhost",
            port=8080,
            gateway_actor_name="zeroth.pod-os.com",
            pool_initial_capacity=10,
            pool_max_capacity=5,
        )
