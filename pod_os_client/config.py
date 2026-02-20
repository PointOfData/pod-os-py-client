"""Pod-OS client configuration."""

from dataclasses import dataclass

__all__ = ["Config"]


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
    max_retries: int = 3
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

    # Logging
    log_level: int = 0  # 0=None, 1=Error, 2=Warn, 3=Info, 4=Debug

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
