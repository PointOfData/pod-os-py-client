"""Pod-OS client configuration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

__all__ = ["Config", "ReconnectConfig"]


@dataclass
class ReconnectConfig:
    """Configuration for automatic reconnection behavior.

    Mirrors Go's ReconnectConfig struct.
    """

    enabled: bool = True
    max_retries: int = 10
    initial_backoff: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff: float = 60.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.initial_backoff <= 0:
            raise ValueError("initial_backoff must be positive")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")
        if self.max_backoff <= 0:
            raise ValueError("max_backoff must be positive")


@dataclass
class Config:
    """Configuration for Pod-OS client.

    Attributes:
        host: Server hostname or IP address
        port: Server port number
        network: Network type ('tcp', 'udp', or 'unix')
        gateway_actor_name: Name of the gateway actor
        client_name: Unique client identifier
        passcode: Authentication passcode
        user_name: Authentication username
        dial_timeout: Connection timeout in seconds
        send_timeout: Send timeout in seconds
        receive_timeout: Receive timeout in seconds
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff delay in seconds
        backoff_multiplier: Backoff multiplier for exponential backoff
        max_backoff: Maximum backoff delay in seconds
        enable_pooling: Enable connection pooling
        pool_initial_capacity: Initial connection pool size
        pool_max_capacity: Maximum connection pool size
        enable_streaming: Enable streaming mode (STREAM ON). None (default) or True
            sends STREAM ON after successful ID handshake; False does not send it.
        enable_concurrent_mode: Enable concurrent message handling
        enable_reconnection: Enable automatic reconnection
        external_receiver: App owns ``connection.receive()`` (Gateway actor loops).
            When True the client never starts its receive loop, ``send_message``
            will not call ``receive()``, and send-path auto-reconnect is disabled
            (reconnect must pause the app receive loop first). Use ``send_no_wait``.
        log_level: Logging level (0=None, 1=Error, 2=Warn, 3=Info, 4=Debug)
    """

    # Connection
    host: str
    port: int
    network: str = "tcp"  # 'tcp', 'udp', or 'unix'
    gateway_actor_name: str = "gateway"

    # Client identity
    client_name: str = ""
    passcode: str = ""
    user_name: str = ""

    # Timeouts
    dial_timeout: float = 10.0
    send_timeout: float = 5.0
    receive_timeout: float = 30.0

    # Retry settings
    # Keep in sync with ReconnectConfig.max_retries (10) so the structured
    # reconnect config built in __post_init__ has a consistent default.
    max_retries: int = 10
    initial_backoff: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff: float = 30.0

    # Connection pool
    enable_pooling: bool = False
    pool_initial_capacity: int = 1
    pool_max_capacity: int = 10

    # Features
    enable_streaming: bool | None = None  # None or True = send STREAM ON; False = do not
    enable_concurrent_mode: bool = True
    enable_reconnection: bool = True
    # App owns the single receive() waiter (mesh / Gateway actor shells).
    external_receiver: bool = False

    # Structured reconnect config (built from flat fields if not provided)
    reconnect_config: ReconnectConfig | None = field(default=None, repr=False)

    # Logging
    log_level: int = 0  # 0=None, 1=Error, 2=Warn, 3=Info, 4=Debug

    # App-level AIP Keepalive interval in seconds. None uses the default (30s).
    # Zero or negative disables keepalive.
    keepalive_interval: float | None = None

    # Bounds each background receive iteration in concurrent mode. None/zero uses 30s.
    receive_loop_timeout: float | None = None

    # Liveness backstop when requests are pending but no frame received. None/zero uses 90s.
    # Negative disables the backstop.
    connection_liveness_timeout: float | None = None

    # TCP keepalive tuning (seconds/count). None/zero uses connection-layer defaults.
    tcp_keep_alive_idle: float | None = None
    tcp_keep_alive_interval: float | None = None
    tcp_keep_alive_count: int | None = None
    tcp_user_timeout: float | None = None

    # Invoked for inbound messages that do not match a pending outbound request when
    # enable_concurrent_mode is true. Wired before start_receiver in Client.connect.
    unmatched_message_handler: Callable[..., None] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.host:
            raise ValueError("host is required")
        if not 0 < self.port < 65536:
            raise ValueError("port must be 1-65535")
        if self.network not in ("tcp", "udp", "unix"):
            raise ValueError("network must be 'tcp', 'udp', or 'unix'")
        if self.dial_timeout <= 0:
            raise ValueError("dial_timeout must be positive")
        if self.send_timeout <= 0:
            raise ValueError("send_timeout must be positive")
        if self.receive_timeout <= 0:
            raise ValueError("receive_timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.initial_backoff <= 0:
            raise ValueError("initial_backoff must be positive")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")
        if self.max_backoff <= 0:
            raise ValueError("max_backoff must be positive")
        if self.pool_initial_capacity < 1:
            raise ValueError("pool_initial_capacity must be >= 1")
        if self.pool_max_capacity < self.pool_initial_capacity:
            raise ValueError("pool_max_capacity must be >= pool_initial_capacity")
        if not 0 <= self.log_level <= 4:
            raise ValueError("log_level must be 0-4")

        if self.reconnect_config is None:
            self.reconnect_config = ReconnectConfig(
                enabled=self.enable_reconnection,
                max_retries=self.max_retries,
                initial_backoff=self.initial_backoff,
                backoff_multiplier=self.backoff_multiplier,
                max_backoff=self.max_backoff,
            )

    def get_keepalive_interval(self) -> float:
        """Return keepalive interval in seconds; 0 disables keepalive."""
        if self.keepalive_interval is not None:
            if self.keepalive_interval <= 0:
                return 0.0
            return self.keepalive_interval
        return 30.0

    def get_receive_loop_timeout(self) -> float:
        """Return receive-loop poll timeout in seconds."""
        if self.receive_loop_timeout is None or self.receive_loop_timeout <= 0:
            return 30.0
        return self.receive_loop_timeout

    def get_connection_liveness_timeout(self) -> float:
        """Return pending-request liveness backstop in seconds.

        Returns 0 when the backstop is explicitly disabled (negative value).
        """
        if self.connection_liveness_timeout is None:
            return 90.0
        if self.connection_liveness_timeout < 0:
            return 0.0
        if self.connection_liveness_timeout == 0:
            return 90.0
        return self.connection_liveness_timeout
