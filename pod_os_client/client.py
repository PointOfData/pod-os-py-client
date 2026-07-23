"""Main Pod-OS client implementation."""

import asyncio
import logging
from collections.abc import Callable
from enum import Enum
from uuid import uuid4

from pod_os_client.config import Config
from pod_os_client.connection.client import ConnectionClient
from pod_os_client.connection.pool import ConnectionPool
from pod_os_client.errors import AuthenticationError
from pod_os_client.errors import ConnectionError as PodOSConnectionError
from pod_os_client.errors import ConnectionLostError, ReceiveIdleTimeoutError
from pod_os_client.errors import DecodeError
from pod_os_client.errors import TimeoutError as PodOSTimeoutError
from pod_os_client.message.decoder import decode_message
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message

logger = logging.getLogger(__name__)

__all__ = ["Client", "ConnectionState"]


class ConnectionState(Enum):
    """Represents the current state of a Client's connection.

    Mirrors Go's ConnectionState type.
    """

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    RECONNECT_FAILED = "reconnect_failed"


class Client:
    """High-performance async Pod-OS client.

    Supports concurrent message handling, automatic reconnection,
    and connection pooling.
    """

    def __init__(self, config: Config) -> None:
        """Initialize Pod-OS client.

        Args:
            config: Client configuration
        """
        self.config = config
        self._connection: ConnectionClient | None = None
        self._connected = False
        self._closed = False
        self._receiver_task: asyncio.Task[None] | None = None
        self._pending_responses: dict[str, asyncio.Future[Message]] = {}
        self._conversation_id = str(uuid4())
        self._reconnecting = False
        self._reconnect_attempt = 0
        self._reconnect_event = asyncio.Event()
        self._reconnect_event.set()  # Initially set (not waiting)
        self._state_handler: Callable[[ConnectionState, Exception | None], None] | None = None
        self._unmatched_handler: Callable[[Message], None] | None = config.unmatched_message_handler
        self._lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task[None] | None = None
        self._pool: ConnectionPool | None = None

    async def connect(self) -> None:
        """Connect to Pod-OS Gateway with authentication.

        Establishes TCP connection, sends ID message for authentication,
        and enables streaming mode by default (send STREAM ON after ID handshake).
        Set config.enable_streaming=False to disable.

        Raises:
            ConnectionError: If connection or authentication fails
            TimeoutError: If operation times out
        """
        # Create connection
        self._connection = ConnectionClient(
            self.config.host,
            self.config.port,
            self.config.network,
            send_timeout=self.config.send_timeout,
            tcp_keep_alive_idle=self.config.tcp_keep_alive_idle,
            tcp_keep_alive_interval=self.config.tcp_keep_alive_interval,
            tcp_keep_alive_count=self.config.tcp_keep_alive_count,
            tcp_user_timeout=self.config.tcp_user_timeout,
        )

        # Connect with timeout
        await self._connection.connect(self.config.dial_timeout)

        # Send GatewayId authentication message
        auth_msg = Message(
            to=f"$system@{self.config.gateway_actor_name}",
            from_=f"{self.config.client_name}@{self.config.gateway_actor_name}",
            intent=IntentType.GatewayId.name,
            client_name=self.config.client_name,
            passcode=self.config.passcode,
            user_name=self.config.user_name,
            message_id=str(uuid4()),
        )

        # Encode and send
        encoded = encode_message(auth_msg, IntentType.GatewayId, self._conversation_id)
        await self._connection.send(encoded)

        # Receive authentication response
        try:
            response_data = await asyncio.wait_for(
                self._connection.receive(), timeout=self.config.receive_timeout
            )
            auth_response = decode_message(response_data)

            # Check authentication result
            if auth_response.processing_status() == "ERROR":
                error_msg = auth_response.processing_message()
                if not error_msg:
                    error_msg = "Authentication rejected by Gateway"
                raise AuthenticationError(error_msg)

        except TimeoutError:
            await self._connection.close()
            raise PodOSTimeoutError(f"authentication timeout after {self.config.receive_timeout}s") from None

        # Send STREAM ON when streaming is enabled (default); only skip when enable_streaming is False
        if self.config.enable_streaming is not False:
            stream_msg = Message(
                to=f"$system@{self.config.gateway_actor_name}",
                from_=f"{self.config.client_name}@{self.config.gateway_actor_name}",
                intent=IntentType.GatewayStreamOn.name,
                client_name=self.config.client_name,
                message_id=str(uuid4()),
            )
            stream_encoded = encode_message(
                stream_msg, IntentType.GatewayStreamOn, self._conversation_id
            )
            await self._connection.send(stream_encoded)

        self._connected = True

        if self.config.enable_pooling and self.config.pool_max_capacity > 0:
            self._pool = ConnectionPool(
                self.config.pool_initial_capacity,
                self.config.pool_max_capacity,
                self._create_pool_connection,
            )
            await self._pool.initialize()

        # Start background receiver for concurrent mode — skipped when the
        # application owns receive() (external_receiver / Gateway actor shells).
        if self.config.enable_concurrent_mode and not self.config.external_receiver:
            self.start_receiver()

        self._start_keepalive_loop()

    async def send_keepalive(self) -> None:
        """Send an app-level AIP Keepalive (message_type 18) on the primary connection."""
        if not self._connection or not self._connected:
            raise PodOSConnectionError("client not connected")

        msg = Message(
            to=f"$system@{self.config.gateway_actor_name}",
            from_=f"{self.config.client_name}@{self.config.gateway_actor_name}",
            intent=IntentType.Keepalive.name,
            client_name=self.config.client_name,
            message_id=str(uuid4()),
        )
        encoded = encode_message(msg, IntentType.Keepalive, self._conversation_id)
        async with self._send_lock:
            await self._connection.send(encoded)

    async def send_disconnect(self) -> None:
        """Send an app-level AIP GatewayDisconnect (message_type 6) on the primary connection."""
        if not self._connection or not self._connection.is_connected():
            return

        msg = Message(
            to=f"$system@{self.config.gateway_actor_name}",
            from_=f"{self.config.client_name}@{self.config.gateway_actor_name}",
            intent=IntentType.GatewayDisconnect.name,
            client_name=self.config.client_name,
            message_id=str(uuid4()),
        )
        encoded = encode_message(msg, IntentType.GatewayDisconnect, self._conversation_id)
        async with self._send_lock:
            if not self._connection or not self._connection.is_connected():
                return
            await self._connection.send(encoded)

    async def send_control_message(self, data: bytes) -> None:
        """Send a pre-encoded control message without waiting for a response."""
        if not self._connection or not self._connected:
            raise PodOSConnectionError("client not connected")
        async with self._send_lock:
            await self._connection.send(data)

    async def send_no_wait(self, msg: Message) -> None:
        """Encode and send a message without calling ``receive()``.

        Safe with ``Config.external_receiver=True`` and with an application
        Gateway receive loop that is the sole ``connection.receive()`` waiter.
        Does not auto-reconnect (reconnect must pause the external receiver).
        """
        if not self._connected or not self._connection:
            raise PodOSConnectionError("client not connected")

        from pod_os_client.message.intents import intent_from_message_type

        intent = intent_from_message_type(msg.intent)
        if not intent:
            raise ValueError(f"unknown intent: {msg.intent}")

        encoded = encode_message(msg, intent, self._conversation_id)
        async with self._send_lock:
            if not self._connection or not self._connected:
                raise PodOSConnectionError("client not connected")
            await self._connection.send(encoded)

    def deliver_response(self, msg: Message) -> bool:
        """Complete a pending future from an external receive loop.

        Returns True if ``msg.message_id`` matched a waiting future.
        Prefer registering futures yourself when using ``send_no_wait``; this
        helper is for apps that share the client's ``_pending_responses`` map.
        """
        fut = self._pending_responses.pop(msg.message_id, None)
        if fut is None:
            return False
        if not fut.done():
            fut.set_result(msg)
        return True

    async def _create_pool_connection(self) -> ConnectionClient:
        conn = ConnectionClient(
            self.config.host,
            self.config.port,
            self.config.network,
            send_timeout=self.config.send_timeout,
            tcp_keep_alive_idle=self.config.tcp_keep_alive_idle,
            tcp_keep_alive_interval=self.config.tcp_keep_alive_interval,
            tcp_keep_alive_count=self.config.tcp_keep_alive_count,
            tcp_user_timeout=self.config.tcp_user_timeout,
        )
        await conn.connect(self.config.dial_timeout)
        return conn

    def _start_keepalive_loop(self) -> None:
        interval = self.config.get_keepalive_interval()
        if interval <= 0:
            return
        if self._keepalive_task and not self._keepalive_task.done():
            return
        self._keepalive_task = asyncio.create_task(self._keepalive_loop(interval))

    async def _keepalive_loop(self, interval: float) -> None:
        while not self._closed:
            await asyncio.sleep(interval)
            if self._closed or not self.is_connected() or self._reconnecting:
                continue
            try:
                await self.send_keepalive()
                await self._send_pool_keepalives()
            except Exception as exc:
                logger.debug("keepalive send failed: %s", exc)

    async def _send_pool_keepalives(self) -> None:
        if self._pool is None:
            return
        msg = Message(
            to=f"$system@{self.config.gateway_actor_name}",
            from_=f"{self.config.client_name}@{self.config.gateway_actor_name}",
            intent=IntentType.Keepalive.name,
            client_name=self.config.client_name,
            message_id=str(uuid4()),
        )
        encoded = encode_message(msg, IntentType.Keepalive, self._conversation_id)

        async def ping(conn: ConnectionClient) -> None:
            await conn.send(encoded)

        await self._pool.ping_idle_connections(ping)

    async def send_message(self, msg: Message) -> Message:
        """Send message and wait for response.

        Args:
            msg: Message to send

        Returns:
            Response message

        Raises:
            ConnectionError: If not connected or send fails
            TimeoutError: If receive times out
            RuntimeError: If ``external_receiver=True`` (use ``send_no_wait``)
        """
        if self.config.external_receiver:
            raise RuntimeError(
                "send_message cannot wait for a response when external_receiver=True "
                "(another coroutine owns connection.receive()). Use send_no_wait() and "
                "route responses in your receive loop (optionally via deliver_response)."
            )

        if not self._connected or not self._connection:
            rc = self.config.reconnect_config
            if rc is not None and rc.enabled and self._reconnecting:
                if not await self._wait_for_reconnect():
                    raise PodOSConnectionError("connection to gateway was lost during request")
            else:
                raise PodOSConnectionError("client not connected")

        # Determine intent
        from pod_os_client.message.intents import intent_from_message_type

        intent = intent_from_message_type(msg.intent)
        if not intent:
            raise ValueError(f"unknown intent: {msg.intent}")

        # Encode
        encoded = encode_message(msg, intent, self._conversation_id)

        # If concurrent mode, register future, send, and wait
        if self.config.enable_concurrent_mode:
            future: asyncio.Future[Message] = asyncio.Future()
            async with self._lock:
                self._pending_responses[msg.message_id] = future

            try:
                # Send with reconnect-and-retry on a fatal connection error so a
                # dropped socket does not strand the request.
                try:
                    await self._connection.send(encoded)
                except ConnectionLostError as e:
                    rc = self.config.reconnect_config
                    if rc is not None and rc.enabled:
                        logger.info(
                            "concurrent send failed with connection error, attempting reconnection: %s",
                            e,
                        )
                        await self._reconnect_once()
                        if self._connected and self._connection:
                            await self._connection.send(encoded)
                        else:
                            raise
                    else:
                        raise

                response = await asyncio.wait_for(future, timeout=self.config.receive_timeout)
                return response
            except TimeoutError:
                async with self._lock:
                    self._pending_responses.pop(msg.message_id, None)
                raise PodOSTimeoutError(
                    f"receive timeout after {self.config.receive_timeout}s for message {msg.message_id}"
                ) from None
            except PodOSConnectionError:
                async with self._lock:
                    self._pending_responses.pop(msg.message_id, None)
                raise
        else:
            # Synchronous mode: send, then receive immediately, with
            # reconnect-and-retry on a fatal connection error.
            await self._connection.send(encoded)
            try:
                response_data = await asyncio.wait_for(
                    self._connection.receive(), timeout=self.config.receive_timeout
                )
                return decode_message(response_data)
            except ConnectionLostError as e:
                rc = self.config.reconnect_config
                if rc is not None and rc.enabled:
                    logger.info("sync send failed with connection error, attempting reconnection: %s", e)
                    await self._reconnect_once()
                    if self._connected and self._connection:
                        # Re-send after reconnection
                        encoded = encode_message(msg, intent, self._conversation_id)
                        await self._connection.send(encoded)
                        response_data = await asyncio.wait_for(
                            self._connection.receive(), timeout=self.config.receive_timeout
                        )
                        return decode_message(response_data)
                raise
            except TimeoutError:
                raise PodOSTimeoutError(f"receive timeout after {self.config.receive_timeout}s") from None

    def start_receiver(self) -> None:
        """Start background receiver task for concurrent mode."""
        if self.config.external_receiver:
            raise RuntimeError(
                "start_receiver() is disabled when external_receiver=True; "
                "the application must own connection.receive()"
            )
        if self._receiver_task is None or self._receiver_task.done():
            self._receiver_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        """Background loop to receive and route messages.

        Routes responses to waiting futures based on message ID.
        Uses a 30-second receive timeout to periodically check for shutdown
        and detect half-open connections.
        """
        idle_timeout = self.config.get_receive_loop_timeout()
        liveness_timeout = self.config.get_connection_liveness_timeout()
        loop = asyncio.get_event_loop()
        last_activity = loop.time()
        while self._connected and self._connection:
            try:
                data = await self._connection.receive(timeout=idle_timeout)
                last_activity = loop.time()
                msg = decode_message(data)

                # Route to waiting future
                async with self._lock:
                    if msg.message_id in self._pending_responses:
                        future = self._pending_responses.pop(msg.message_id)
                        if not future.done():
                            future.set_result(msg)
                    elif self._unmatched_handler is not None:
                        handler = self._unmatched_handler
                        try:
                            handler(msg)
                        except Exception as exc:
                            logger.debug("unmatched message handler failed: %s", exc)

            except ReceiveIdleTimeoutError:
                # Benign idle timeout: still alive unless we have pending requests
                # and have heard nothing for too long (liveness backstop).
                if (
                    liveness_timeout == 0
                    or not self._pending_responses
                    or (loop.time() - last_activity) <= liveness_timeout
                ):
                    continue
                logger.error(
                    "liveness timeout: pending requests with no frames received; treating connection as dead"
                )
                await self._handle_connection_lost(
                    ConnectionLostError("liveness timeout: no frames received with pending requests")
                )
                break
            except PodOSConnectionError as e:
                # Any other transport error is fatal: fail all in-flight callers
                # fast, then reconnect.
                logger.error("connection error in receiver: %s", e)
                await self._handle_connection_lost(e)
                break
            except DecodeError as e:
                # A fully-read but malformed frame keeps the stream aligned; log and
                # continue rather than tearing down a healthy connection.
                logger.warning("undecipherable frame: %s", e)
                continue
            except Exception as e:
                logger.error("unexpected error in receiver: %s", e)
                await self._handle_connection_lost(
                    ConnectionLostError(f"unexpected receiver error: {e}")
                )
                break

    async def _handle_connection_lost(self, err: Exception) -> None:
        """Mark disconnected, fail every in-flight caller with a retryable error,
        emit the disconnected state, and trigger reconnect."""
        # Fix transport/high-level desync: ensure both are marked disconnected.
        self._connected = False
        await self._fail_all_pending()
        self._emit_state(ConnectionState.DISCONNECTED, err)
        rc = self.config.reconnect_config
        if rc is not None and rc.enabled and not self._reconnecting:
            asyncio.create_task(self._reconnect(trigger_err=err))

    async def _fail_all_pending(self) -> None:
        """Resolve all pending futures with a retryable ConnectionLostError so
        callers fail fast instead of blocking until their own timeout."""
        async with self._lock:
            for future in self._pending_responses.values():
                if not future.done():
                    future.set_exception(
                        ConnectionLostError("connection to gateway was lost during request")
                    )
            self._pending_responses.clear()

    async def _reconnect_once(self) -> None:
        """Attempt a single reconnection cycle (close, reconnect, re-authenticate).

        Used by the sync send path to retry a message once after a connection error.
        Disabled when ``external_receiver=True`` — auth ``receive()`` would race the
        application receive loop; the app must pause receive, then call reconnect().
        """
        if self._closed:
            return
        if self.config.external_receiver:
            self._connected = False
            raise ConnectionLostError(
                "connection lost with external_receiver=True; pause your receive "
                "loop and call Client.reconnect() explicitly"
            )
        if self._connection:
            await self._connection.close()

        try:
            await self.connect()
        except Exception:
            self._connected = False

    async def reconnect(self) -> None:
        """Explicit reconnect for ``external_receiver`` apps.

        Caller must have stopped / awaited its ``connection.receive()`` loop
        before calling this. Performs close + connect (ID handshake receive).
        """
        if self._closed:
            raise PodOSConnectionError("client is closed")
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None
        self._connected = False
        await self.connect()

    async def _reconnect(self, trigger_err: Exception | None = None) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._closed:
            return
        if self.config.external_receiver:
            # Background auto-reconnect would race the app's receive loop.
            self._connected = False
            await self._fail_all_pending()
            self._emit_state(ConnectionState.DISCONNECTED, trigger_err)
            return
        self._reconnecting = True
        self._reconnect_attempt = 0
        self._reconnect_event.clear()

        rc = self.config.reconnect_config
        assert rc is not None

        self._emit_state(ConnectionState.RECONNECTING, trigger_err)

        unlimited = rc.max_retries == 0
        last_err: Exception | None = trigger_err

        while unlimited or self._reconnect_attempt < rc.max_retries:
            if self._closed:
                break
            self._reconnect_attempt += 1

            try:
                if self._connection:
                    await self._connection.close()

                backoff = min(
                    rc.initial_backoff * (rc.backoff_multiplier ** self._reconnect_attempt),
                    rc.max_backoff,
                )
                await asyncio.sleep(backoff)

                if self._closed:
                    break

                await self.connect()

                self._reconnecting = False
                self._reconnect_attempt = 0
                self._reconnect_event.set()
                self._emit_state(ConnectionState.CONNECTED, None)
                return

            except Exception as e:
                last_err = e
                continue

        # All reconnection attempts failed
        self._connected = False
        self._reconnecting = False
        self._reconnect_event.set()
        self._emit_state(ConnectionState.RECONNECT_FAILED, last_err)

    async def close(self) -> None:
        """Close client and connection.

        Stops background tasks and closes network connection.
        """
        self._closed = True
        self._reconnect_event.set()  # Unblock any waiters
        self._connected = False

        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None

        # Stop receiver task
        if self._receiver_task:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling task
            self._receiver_task = None

        # Fail all pending responses
        async with self._lock:
            for future in self._pending_responses.values():
                if not future.done():
                    future.cancel()
            self._pending_responses.clear()

        # Close connection
        if self._pool is not None:
            await self._pool.close_all()
            self._pool = None
        if self._connection:
            try:
                await self.send_disconnect()
            except Exception as exc:
                logger.warning("failed to send GatewayDisconnect before close: %s", exc)
            await self._connection.close()
            self._connection = None

    def on_connection_state_change(
        self, fn: Callable[[ConnectionState, Exception | None], None] | None
    ) -> None:
        """Register a callback that fires on every connection state transition.

        The error parameter semantics per state:
        - DISCONNECTED: the error that caused the disconnect.
        - RECONNECTING: the trigger error (may be None).
        - CONNECTED: None (reconnect succeeded).
        - RECONNECT_FAILED: the last reconnect attempt error.

        Note: CONNECTED is not emitted for the initial connection because no
        handler can be registered before connect() returns.

        The callback is invoked synchronously so it should be fast and non-blocking.
        """
        self._state_handler = fn

    def set_unmatched_message_handler(
        self, fn: Callable[[Message], None] | None
    ) -> None:
        """Register a handler for inbound messages that do not match pending requests.

        Must be called before start_receiver (or before connect when
        enable_concurrent_mode is true) to avoid missing early messages.
        """
        self._unmatched_handler = fn

    def _emit_state(self, state: ConnectionState, err: Exception | None = None) -> None:
        """Call the registered state handler, if any."""
        fn = self._state_handler
        if fn is not None:
            fn(state, err)

    async def _wait_for_reconnect(self, timeout: float | None = None) -> bool:
        """Block until the client is connected or timeout expires.

        Returns True if the connection was restored, False otherwise.
        """
        if self._connected and self._connection:
            return True
        if not self._reconnecting:
            return False
        try:
            effective_timeout = timeout or self.config.receive_timeout
            await asyncio.wait_for(self._reconnect_event.wait(), timeout=effective_timeout)
            return self._connected and self._connection is not None and not self._closed
        except asyncio.TimeoutError:
            return False

    def is_connected(self) -> bool:
        """Check if client is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._connection is not None

    def is_reconnecting(self) -> bool:
        """Check if client is currently reconnecting.

        Returns:
            True if reconnecting, False otherwise
        """
        return self._reconnecting

    def reconnect_attempt(self) -> int:
        """Get current reconnection attempt number.

        Returns:
            Reconnection attempt number (0 if not reconnecting)
        """
        return self._reconnect_attempt

    def client_name(self) -> str:
        """Get client name.

        Returns:
            Client name from configuration
        """
        return self.config.client_name

    def actor_name(self) -> str:
        """Get gateway actor name.

        Returns:
            Gateway actor name from configuration
        """
        return self.config.gateway_actor_name

    async def __aenter__(self) -> "Client":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Async context manager exit."""
        await self.close()
