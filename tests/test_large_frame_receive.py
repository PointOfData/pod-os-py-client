"""Large-frame receive: idle timeout must not cancel mid-body reads."""

import asyncio

from pod_os_client.connection.client import ConnectionClient
from pod_os_client.errors import ReceiveIdleTimeoutError


async def _start_server(handler):
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def _run(coro_factory):
    async def guarded():
        await asyncio.wait_for(coro_factory(), timeout=15.0)

    asyncio.run(guarded())


def test_slow_large_body_completes_with_short_idle_timeout():
    """Body transfer >1s must succeed when only prefix idle timeout is 0.5s."""

    async def run():
        body_size = 512 * 1024
        msg_length = 9 + body_size
        prefix = f"x{msg_length:08x}".encode()
        body = b"B" * body_size

        async def handler(reader, writer):
            writer.write(prefix)
            await writer.drain()
            await asyncio.sleep(1.5)
            writer.write(body)
            await writer.drain()
            writer.close()

        server, port = await _start_server(handler)
        try:
            client = ConnectionClient("127.0.0.1", port)
            await client.connect(timeout=2.0)
            try:
                data = await client.receive(timeout=0.5, body_timeout=10.0)
                assert len(data) == msg_length
                assert client.is_connected() is True
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)


def test_wait_for_on_full_receive_would_fail_pattern():
    """Document anti-pattern: asyncio.wait_for(receive()) cancels mid-body."""

    async def run():
        body_size = 64 * 1024
        msg_length = 9 + body_size
        prefix = f"x{msg_length:08x}".encode()
        body = b"C" * body_size

        async def handler(reader, writer):
            writer.write(prefix)
            await writer.drain()
            await asyncio.sleep(0.8)
            writer.write(body)
            await writer.drain()
            writer.close()

        server, port = await _start_server(handler)
        try:
            client = ConnectionClient("127.0.0.1", port)
            await client.connect(timeout=2.0)
            try:
                raised = None
                try:
                    await asyncio.wait_for(client.receive(timeout=0.5), timeout=0.5)
                except Exception as exc:  # noqa: BLE001
                    raised = exc
                assert raised is not None
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)


def test_idle_still_raises_when_no_prefix():
    async def run():
        async def handler(reader, writer):
            await asyncio.sleep(2.0)
            writer.close()

        server, port = await _start_server(handler)
        try:
            client = ConnectionClient("127.0.0.1", port)
            await client.connect(timeout=2.0)
            try:
                raised = None
                try:
                    await client.receive(timeout=0.3, body_timeout=10.0)
                except Exception as exc:  # noqa: BLE001
                    raised = exc
                assert isinstance(raised, ReceiveIdleTimeoutError)
                assert client.is_connected() is True
            finally:
                await client.close()
        finally:
            server.close()

    _run(run)
