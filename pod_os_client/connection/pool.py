"""Connection pool for high-throughput scenarios."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

from pod_os_client.connection.client import ConnectionClient

__all__ = ["ConnectionPool"]


class ConnectionPool:
    """Async connection pool for managing multiple connections.

    Provides connection reuse and limits maximum concurrent connections.
    """

    def __init__(
        self,
        initial_capacity: int,
        max_capacity: int,
        factory: Callable[[], Awaitable[ConnectionClient]],
    ) -> None:
        """Initialize connection pool.

        Args:
            initial_capacity: Initial number of connections to create
            max_capacity: Maximum number of connections allowed
            factory: Async factory function to create new connections
        """
        self._initial_capacity = initial_capacity
        self._max_capacity = max_capacity
        self._factory = factory
        self._available: deque[ConnectionClient] = deque()
        self._in_use: set[ConnectionClient] = set()
        self._lock = asyncio.Lock()
        self._waiters: deque[asyncio.Future[ConnectionClient]] = deque()

    async def initialize(self) -> None:
        """Initialize the pool by creating initial connections."""
        for _ in range(self._initial_capacity):
            conn = await self._factory()
            self._available.append(conn)

    async def acquire(self) -> ConnectionClient:
        """Acquire a connection from the pool.

        If no connections are available and the pool is at capacity,
        waits until a connection is released.

        Returns:
            A connection from the pool
        """
        async with self._lock:
            # Try to get an available connection
            if self._available:
                conn = self._available.popleft()
                self._in_use.add(conn)
                return conn

            # Try to create a new connection if under capacity
            if len(self._in_use) < self._max_capacity:
                conn = await self._factory()
                self._in_use.add(conn)
                return conn

        # Pool is at capacity, wait for a connection
        future: asyncio.Future[ConnectionClient] = asyncio.Future()
        self._waiters.append(future)
        return await future

    async def release(self, conn: ConnectionClient) -> None:
        """Return a connection to the pool.

        Args:
            conn: Connection to release
        """
        async with self._lock:
            self._in_use.discard(conn)

            # If there are waiters, give connection to first waiter
            if self._waiters:
                waiter = self._waiters.popleft()
                if not waiter.done():
                    waiter.set_result(conn)
                    self._in_use.add(conn)
                    return

            # Check if connection is still healthy
            if conn.is_connected():
                self._available.append(conn)
            else:
                # Connection is dead, close it
                await conn.close()

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            # Close available connections
            while self._available:
                conn = self._available.popleft()
                await conn.close()

            # Close in-use connections
            for conn in self._in_use:
                await conn.close()
            self._in_use.clear()

            # Cancel all waiters
            while self._waiters:
                waiter = self._waiters.popleft()
                if not waiter.done():
                    waiter.cancel()

    def size(self) -> tuple[int, int]:
        """Get current pool size.

        Returns:
            Tuple of (available_count, in_use_count)
        """
        return (len(self._available), len(self._in_use))

    async def __aenter__(self) -> "ConnectionPool":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Async context manager exit."""
        await self.close_all()
