"""Async network connection client for Pod-OS."""

import asyncio
from typing import Optional

from pod_os_client.errors import ConnectionError as PodOSConnectionError

__all__ = ["ConnectionClient"]


class ConnectionClient:
    """Async TCP/UDP connection client.

    Handles low-level network communication with Pod-OS Gateway.
    """

    def __init__(self, host: str, port: int, network: str = "tcp") -> None:
        """Initialize connection client.

        Args:
            host: Server hostname or IP address
            port: Server port number
            network: Network type ('tcp', 'udp', or 'unix')
        """
        self.host = host
        self.port = port
        self.network = network
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
            elif self.network == "udp":
                # UDP transport (simplified - actual implementation would need datagram protocol)
                raise NotImplementedError("UDP transport not yet implemented")
            elif self.network == "unix":
                # Unix socket
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
            await self._writer.drain()
            return len(data)
        except Exception as e:
            self._connected = False
            raise PodOSConnectionError(f"send failed: {e}") from e

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

        try:
            # Read 9-byte length prefix
            length_bytes = await asyncio.wait_for(
                self._reader.readexactly(9), timeout=timeout
            )

            # Parse length (format: x00000000 in hex)
            length_str = length_bytes.decode("ascii").strip()
            if length_str.startswith("x"):
                msg_length = int(length_str[1:], 16)
            else:
                msg_length = int(length_str, 10)

            # Read remaining message data
            # The length includes everything after the first 9-byte length field
            remaining = msg_length - 9  # Subtract the length field itself
            if remaining > 0:
                message_data = await asyncio.wait_for(
                    self._reader.readexactly(remaining), timeout=timeout
                )
                return length_bytes + message_data
            else:
                return length_bytes

        except asyncio.IncompleteReadError as e:
            self._connected = False
            raise PodOSConnectionError(
                f"connection closed during receive (got {len(e.partial)} bytes)"
            ) from e
        except asyncio.TimeoutError:
            raise PodOSConnectionError(
                f"receive timeout after {timeout}s" if timeout else "receive timeout"
            ) from None
        except Exception as e:
            self._connected = False
            raise PodOSConnectionError(f"receive failed: {e}") from e

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
