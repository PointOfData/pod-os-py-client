"""Async network connection client for Pod-OS."""

import asyncio
import socket
from typing import Optional

from pod_os_client.errors import ConnectionError as PodOSConnectionError
from pod_os_client.errors import ConnectionLostError, ReceiveIdleTimeoutError

__all__ = ["ConnectionClient"]

_HEX_DIGITS = frozenset(b"0123456789abcdefABCDEF")
_DEC_DIGITS = frozenset(b"0123456789")

# Aggressive keepalive so a dead/half-open peer surfaces within ~30s (idle 15s,
# then up to 3 probes 5s apart), plus a matching TCP_USER_TIMEOUT (Linux) so
# unacknowledged writes fail fast instead of blocking for the OS default.
_KEEPALIVE_IDLE_SECS = 15
_KEEPALIVE_INTERVAL_SECS = 5
_KEEPALIVE_PROBE_COUNT = 3
_TCP_USER_TIMEOUT_MS = 30_000


def _apply_tcp_options(
    sock: socket.socket,
    *,
    keepalive_idle: float | None = None,
    keepalive_interval: float | None = None,
    keepalive_count: int | None = None,
    user_timeout_ms: float | None = None,
) -> None:
    """Apply TCP_NODELAY, aggressive keepalive, and TCP_USER_TIMEOUT (best-effort)."""
    idle = int(keepalive_idle if keepalive_idle and keepalive_idle > 0 else _KEEPALIVE_IDLE_SECS)
    interval = int(
        keepalive_interval if keepalive_interval and keepalive_interval > 0 else _KEEPALIVE_INTERVAL_SECS
    )
    count = int(keepalive_count if keepalive_count and keepalive_count > 0 else _KEEPALIVE_PROBE_COUNT)
    user_timeout = int(
        user_timeout_ms if user_timeout_ms and user_timeout_ms > 0 else _TCP_USER_TIMEOUT_MS
    )
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass
    # Per-probe keepalive knobs are Linux-specific (and named differently elsewhere).
    for opt_name, value in (
        ("TCP_KEEPIDLE", idle),
        ("TCP_KEEPINTVL", interval),
        ("TCP_KEEPCNT", count),
    ):
        opt = getattr(socket, opt_name, None)
        if opt is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, opt, value)
            except OSError:
                pass
    tcp_user_timeout = getattr(socket, "TCP_USER_TIMEOUT", None)
    if tcp_user_timeout is not None:
        try:
            sock.setsockopt(socket.IPPROTO_TCP, tcp_user_timeout, user_timeout)
        except OSError:
            pass


def _is_valid_length_prefix(data: bytes) -> bool:
    """Validate a 9-byte length prefix: 'x' + 8 hex digits, or 9 decimal digits."""
    if len(data) != 9:
        return False
    if data[0:1] == b"x":
        return all(b in _HEX_DIGITS for b in data[1:])
    return all(b in _DEC_DIGITS for b in data)


class ConnectionClient:
    """Async TCP/UDP connection client.

    Handles low-level network communication with Pod-OS Gateway.
    """

    def __init__(
        self,
        host: str,
        port: int,
        network: str = "tcp",
        send_timeout: Optional[float] = None,
        *,
        tcp_keep_alive_idle: float | None = None,
        tcp_keep_alive_interval: float | None = None,
        tcp_keep_alive_count: int | None = None,
        tcp_user_timeout: float | None = None,
    ) -> None:
        """Initialize connection client.

        Args:
            host: Server hostname or IP address
            port: Server port number
            network: Network type ('tcp', 'udp', or 'unix')
            send_timeout: Timeout in seconds for send operations (None for no timeout)
            tcp_keep_alive_idle: TCP keepalive idle seconds (None for default)
            tcp_keep_alive_interval: TCP keepalive probe interval seconds
            tcp_keep_alive_count: TCP keepalive probe count
            tcp_user_timeout: TCP user timeout in seconds (Linux)
        """
        self.host = host
        self.port = port
        self.network = network
        self.send_timeout = send_timeout
        self.tcp_keep_alive_idle = tcp_keep_alive_idle
        self.tcp_keep_alive_interval = tcp_keep_alive_interval
        self.tcp_keep_alive_count = tcp_keep_alive_count
        self.tcp_user_timeout = tcp_user_timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False

    async def connect(self, timeout: float = 10.0) -> None:
        """Establish connection with timeout.

        Args:
            timeout: Connection timeout in seconds

        Raises:
            ConnectionError: If connection fails
            asyncio.TimeoutError: If connection times out
        """
        try:
            if self.network == "tcp":
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), timeout=timeout
                )
                sock = self._writer.get_extra_info("socket")
                if sock is not None:
                    user_timeout_ms = (
                        self.tcp_user_timeout * 1000 if self.tcp_user_timeout else None
                    )
                    _apply_tcp_options(
                        sock,
                        keepalive_idle=self.tcp_keep_alive_idle,
                        keepalive_interval=self.tcp_keep_alive_interval,
                        keepalive_count=self.tcp_keep_alive_count,
                        user_timeout_ms=user_timeout_ms,
                    )
            elif self.network == "udp":
                raise NotImplementedError("UDP transport not yet implemented")
            elif self.network == "unix":
                raise NotImplementedError("Unix socket transport not yet implemented")
            else:
                raise PodOSConnectionError(f"unsupported network type: {self.network}")

            self._connected = True

        except asyncio.TimeoutError:
            self._connected = False
            raise PodOSConnectionError(
                f"connection timeout after {timeout}s to {self.host}:{self.port}"
            ) from None
        except Exception as e:
            self._connected = False
            raise PodOSConnectionError(
                f"failed to connect to {self.host}:{self.port}: {e}"
            ) from e

    async def send(self, data: bytes) -> int:
        """Send data to connection.

        Args:
            data: Data bytes to send

        Returns:
            Number of bytes sent

        Raises:
            ConnectionError: If not connected or send fails
        """
        if not self._connected or not self._writer:
            raise PodOSConnectionError("not connected")

        try:
            self._writer.write(data)
            if self.send_timeout is not None:
                await asyncio.wait_for(self._writer.drain(), timeout=self.send_timeout)
            else:
                await self._writer.drain()
            return len(data)
        except asyncio.TimeoutError:
            # A write timeout means the socket is dead (TCP_USER_TIMEOUT / peer gone).
            self._connected = False
            raise ConnectionLostError(
                f"send timeout after {self.send_timeout}s"
            ) from None
        except Exception as e:
            self._connected = False
            raise ConnectionLostError(f"send failed: {e}") from e

    async def receive(self, timeout: Optional[float] = None) -> bytes:
        """Receive data with optional timeout.

        Reads a complete Pod-OS message using the 9-byte length prefix.

        Args:
            timeout: Receive timeout in seconds (None for no timeout)

        Returns:
            Received data bytes

        Raises:
            ConnectionError: If not connected or receive fails
            asyncio.TimeoutError: If receive times out
        """
        if not self._connected or not self._reader:
            raise PodOSConnectionError("not connected")

        # Phase 1: read the 9-byte length prefix. A timeout here is a benign idle
        # read (no frame was in progress); any other error is fatal.
        try:
            length_bytes = await asyncio.wait_for(
                self._reader.readexactly(9), timeout=timeout
            )
        except asyncio.TimeoutError:
            # Connection still considered healthy: nothing was mid-flight.
            raise ReceiveIdleTimeoutError(
                f"receive idle timeout after {timeout}s" if timeout else "receive idle timeout"
            ) from None
        except asyncio.IncompleteReadError as e:
            self._connected = False
            raise ConnectionLostError(
                f"connection closed during receive (got {len(e.partial)} bytes)"
            ) from e
        except Exception as e:
            self._connected = False
            raise ConnectionLostError(f"receive failed: {e}") from e

        # Framing errors cannot be resynced on a length-prefixed stream -> fatal.
        if not _is_valid_length_prefix(length_bytes):
            self._connected = False
            raise ConnectionLostError(
                f"connection out of sync: invalid length prefix {length_bytes!r}"
                " - previous message may not have been fully consumed"
            )

        try:
            # Parse length (format: x00000000 in hex or 9 decimal digits)
            if length_bytes[0:1] == b"x":
                msg_length = int(length_bytes[1:], 16)
            else:
                msg_length = int(length_bytes, 10)
        except ValueError as e:
            self._connected = False
            raise ConnectionLostError(
                f"failed to parse message length prefix {length_bytes!r}: {e}"
            ) from e

        # Phase 2: read the body. We are mid-frame, so a timeout or any error here
        # desyncs the stream / signals a dead peer -> fatal.
        remaining = msg_length - 9  # Subtract the length field itself
        if remaining <= 0:
            return length_bytes
        try:
            message_data = await asyncio.wait_for(
                self._reader.readexactly(remaining), timeout=timeout
            )
            return length_bytes + message_data
        except asyncio.TimeoutError:
            self._connected = False
            raise ConnectionLostError(
                f"receive timeout mid-frame after {timeout}s" if timeout else "receive timeout mid-frame"
            ) from None
        except asyncio.IncompleteReadError as e:
            self._connected = False
            raise ConnectionLostError(
                f"connection closed during receive (got {len(e.partial)} bytes)"
            ) from e
        except Exception as e:
            self._connected = False
            raise ConnectionLostError(f"receive failed: {e}") from e

    async def close(self) -> None:
        """Close connection gracefully."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass  # Ignore errors during close
        self._connected = False
        self._reader = None
        self._writer = None

    async def reconnect(self, timeout: float = 10.0) -> None:
        """Close existing connection and re-establish it.

        Re-applies TCP settings (NODELAY, KEEPALIVE) after reconnection.

        Args:
            timeout: Connection timeout in seconds

        Raises:
            ConnectionError: If reconnection fails
        """
        await self.close()
        await self.connect(timeout)

    def is_connected(self) -> bool:
        """Check if connection is active.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    def remote_addr(self) -> str:
        """Get remote address.

        Returns:
            Remote address string
        """
        return f"{self.host}:{self.port}"

    def local_addr(self) -> str:
        """Get local address.

        Returns:
            Local address string or empty if not connected
        """
        if self._writer:
            try:
                sock = self._writer.get_extra_info("socket")
                if sock:
                    addr = sock.getsockname()
                    return f"{addr[0]}:{addr[1]}"
            except Exception:
                pass
        return ""
