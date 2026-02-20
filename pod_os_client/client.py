"""Main Pod-OS client implementation."""

import asyncio
from uuid import uuid4

from pod_os_client.config import Config
from pod_os_client.connection.client import ConnectionClient
from pod_os_client.errors import AuthenticationError
from pod_os_client.errors import ConnectionError as PodOSConnectionError
from pod_os_client.errors import TimeoutError as PodOSTimeoutError
from pod_os_client.message.decoder import decode_message
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message

__all__ = ["Client"]


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
        self._receiver_task: asyncio.Task[None] | None = None
        self._pending_responses: dict[str, asyncio.Future[Message]] = {}
        self._conversation_id = str(uuid4())
        self._reconnecting = False
        self._reconnect_attempt = 0
        self._lock = asyncio.Lock()

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
        self._connection = ConnectionClient(self.config.host, self.config.port, self.config.network)

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

        # Start background receiver for concurrent mode
        if self.config.enable_concurrent_mode:
            self.start_receiver()

    async def send_message(self, msg: Message) -> Message:
        """Send message and wait for response.

        Args:
            msg: Message to send

        Returns:
            Response message

        Raises:
            ConnectionError: If not connected or send fails
            TimeoutError: If receive times out
        """
        if not self._connected or not self._connection:
            raise PodOSConnectionError("client not connected")

        # Determine intent
        from pod_os_client.message.intents import intent_from_message_type

        intent = intent_from_message_type(msg.intent)
        if not intent:
            raise ValueError(f"unknown intent: {msg.intent}")

        # Encode and send
        encoded = encode_message(msg, intent, self._conversation_id)
        await self._connection.send(encoded)

        # If concurrent mode, register future and wait
        if self.config.enable_concurrent_mode:
            future: asyncio.Future[Message] = asyncio.Future()
            async with self._lock:
                self._pending_responses[msg.message_id] = future

            try:
                response = await asyncio.wait_for(future, timeout=self.config.receive_timeout)
                return response
            except TimeoutError:
                # Clean up pending future
                async with self._lock:
                    self._pending_responses.pop(msg.message_id, None)
                raise PodOSTimeoutError(
                    f"receive timeout after {self.config.receive_timeout}s for message {msg.message_id}"
                ) from None
        else:
            # Synchronous mode: receive immediately
            try:
                response_data = await asyncio.wait_for(
                    self._connection.receive(), timeout=self.config.receive_timeout
                )
                return decode_message(response_data)
            except TimeoutError:
                raise PodOSTimeoutError(f"receive timeout after {self.config.receive_timeout}s") from None

    def start_receiver(self) -> None:
        """Start background receiver task for concurrent mode."""
        if self._receiver_task is None or self._receiver_task.done():
            self._receiver_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        """Background loop to receive and route messages.

        Routes responses to waiting futures based on message ID.
        """
        while self._connected and self._connection:
            try:
                data = await self._connection.receive(timeout=None)
                msg = decode_message(data)

                # Route to waiting future
                async with self._lock:
                    if msg.message_id in self._pending_responses:
                        future = self._pending_responses.pop(msg.message_id)
                        if not future.done():
                            future.set_result(msg)

            except PodOSConnectionError:
                # Connection error - attempt reconnection if enabled
                if self.config.enable_reconnection and not self._reconnecting:
                    asyncio.create_task(self._reconnect())
                else:
                    break
            except Exception:
                # Unexpected error - stop receiver
                break

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        self._reconnecting = True
        self._reconnect_attempt = 0

        while self._reconnect_attempt < self.config.max_retries:
            self._reconnect_attempt += 1

            try:
                # Close existing connection
                if self._connection:
                    await self._connection.close()

                # Wait before reconnecting
                backoff = min(
                    self.config.initial_backoff
                    * (self.config.backoff_multiplier**self._reconnect_attempt),
                    self.config.max_backoff,
                )
                await asyncio.sleep(backoff)

                # Attempt to reconnect
                await self.connect()

                # Success
                self._reconnecting = False
                self._reconnect_attempt = 0
                return

            except Exception:
                # Reconnection failed, will retry
                continue

        # All reconnection attempts failed
        self._connected = False
        self._reconnecting = False

    async def close(self) -> None:
        """Close client and connection.

        Stops background tasks and closes network connection.
        """
        self._connected = False

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
        if self._connection:
            await self._connection.close()
            self._connection = None

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
