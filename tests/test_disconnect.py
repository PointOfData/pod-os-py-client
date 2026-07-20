"""Tests for GatewayDisconnect on client close."""

from __future__ import annotations

import asyncio

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.connection.client import ConnectionClient
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message


def test_disconnect_message_shape() -> None:
    cfg = Config(
        host="127.0.0.1",
        port=62312,
        client_name="my-client",
        gateway_actor_name="zeroth.pod-os.com",
    )
    client = Client(cfg)
    msg = Message(
        to=f"$system@{cfg.gateway_actor_name}",
        from_=f"{cfg.client_name}@{cfg.gateway_actor_name}",
        intent=IntentType.GatewayDisconnect.name,
        client_name=cfg.client_name,
        message_id="disconnect-1",
    )
    wire = encode_message(msg, IntentType.GatewayDisconnect, client._conversation_id)
    assert b"000000006" in wire


async def _close_sends_disconnect_before_tcp() -> None:
    received: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = await reader.read(4096)
        if not received.done():
            received.set_result(data)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]

    conn = ConnectionClient(str(host), port, "tcp")
    await conn.connect(5.0)

    cfg = Config(
        host=str(host),
        port=port,
        client_name="close-test-client",
        gateway_actor_name="zeroth.pod-os.com",
    )
    client = Client(cfg)
    client._connection = conn

    await client.close()

    data = await asyncio.wait_for(received, timeout=2.0)
    assert b"000000006" in data

    server.close()
    await server.wait_closed()


def test_close_sends_disconnect_before_tcp() -> None:
    asyncio.run(_close_sends_disconnect_before_tcp())
