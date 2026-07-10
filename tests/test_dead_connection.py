"""Transport-level dead-connection detection tests.

These spin up a local asyncio TCP server, drive a specific failure scenario, and
assert the ConnectionClient classifies it correctly (fatal ConnectionLostError
vs benign ReceiveIdleTimeoutError) and clears its `_connected` flag on fatal
errors.

Written as plain (sync) tests driven via ``asyncio.run`` so they do not require
the ``pytest-asyncio`` plugin.
"""

import asyncio
import socket

from pod_os_client.connection.client import ConnectionClient
from pod_os_client.errors import ConnectionLostError, ReceiveIdleTimeoutError


async def _start_server(handler):
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


async def _connect(port: int) -> ConnectionClient:
    client = ConnectionClient("127.0.0.1", port, send_timeout=0.5)
    await client.connect(timeout=2.0)
    return client


def _run(coro_factory):
    """Run an async test body under a hard timeout so a regression cannot hang
    the suite. Only server.close() is used for teardown (no wait_closed) because
    waiting on still-active handler connections can block on Python 3.12."""

    async def guarded():
        await asyncio.wait_for(coro_factory(), timeout=10.0)

    asyncio.run(guarded())


def test_corrupt_prefix_is_fatal():
    async def run():
        async def handler(reader, writer):
            writer.write(b"!!garbage")  # 9 invalid prefix bytes
            await writer.drain()
            await asyncio.sleep(1.0)

        server, port = await _start_server(handler)
        try:
            client = await _connect(port)
            try:
                raised = None
                try:
                    await client.receive(timeout=1.0)
                except Exception as e:  # noqa: BLE001
                    raised = e
                assert isinstance(raised, ConnectionLostError), raised
                assert client.is_connected() is False
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)


def test_rst_mid_response_is_fatal():
    async def run():
        async def handler(reader, writer):
            # Claim a 100-byte message, send only the prefix + a few body bytes,
            # then abruptly close so the client hits EOF/RST mid-frame.
            writer.write(b"x00000064")  # hex 0x64 = 100 total bytes
            writer.write(b"partial")
            await writer.drain()
            sock = writer.get_extra_info("socket")
            if sock is not None:
                # LINGER 0 -> RST on close
                sock.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    __import__("struct").pack("ii", 1, 0),
                )
            writer.close()

        server, port = await _start_server(handler)
        try:
            client = await _connect(port)
            try:
                loop = asyncio.get_event_loop()
                start = loop.time()
                raised = None
                try:
                    await client.receive(timeout=1.0)
                except Exception as e:  # noqa: BLE001
                    raised = e
                assert isinstance(raised, ConnectionLostError), raised
                assert client.is_connected() is False
                assert (loop.time() - start) < 1.5
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)


def test_idle_timeout_is_benign():
    async def run():
        async def handler(reader, writer):
            await asyncio.sleep(2.0)  # stay connected but silent
            writer.close()

        server, port = await _start_server(handler)
        try:
            client = await _connect(port)
            try:
                raised = None
                try:
                    await client.receive(timeout=0.3)
                except Exception as e:  # noqa: BLE001
                    raised = e
                assert isinstance(raised, ReceiveIdleTimeoutError), raised
                assert client.is_connected() is True
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)


def test_send_after_peer_close_is_fatal():
    async def run():
        closed = asyncio.Event()

        async def handler(reader, writer):
            sock = writer.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    __import__("struct").pack("ii", 1, 0),
                )
            writer.close()
            closed.set()

        server, port = await _start_server(handler)
        try:
            client = await _connect(port)
            try:
                await asyncio.wait_for(closed.wait(), timeout=2.0)
                raised = None
                # Repeated sends reliably surface the dead socket.
                for _ in range(50):
                    try:
                        await client.send(b"x00000009")
                    except Exception as e:  # noqa: BLE001
                        raised = e
                        break
                    await asyncio.sleep(0.02)
                assert isinstance(raised, ConnectionLostError), raised
                assert client.is_connected() is False
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)
