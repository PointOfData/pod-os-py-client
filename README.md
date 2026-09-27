# Pod-OS Python Client

High-performance Python client library for registering as a Pod-OS Actor and or communicating with a Pod-OS Actor, handling the Pod-OS/AIP message protocol (send and receive), and includes Intents for Evolutionary Neural Memory database operations.

## Features

- **Async/Await Support**: Built on asyncio for high concurrency and low latency
- **Connection Management**: TCP/UDP support with automatic reconnection and exponential backoff
- **Connection Pooling**: Optional pooling for high-throughput scenarios
- **Message Protocol**: Full Pod-OS message encoding/decoding with MessagePack
- **Evolutionary Neural Memory**: Complete Evolutionary Neural Memory database operations (store, retrieve, link, search)
- **Type Safe**: Full type hints with mypy validation
- **High Performance**: Sub-millisecond encoding/decoding with compiled extensions

## Requirements

- Python 3.12 or higher

## Installation

```bash
pip install pod-os-py-client
```

For development with optional performance improvements:

```bash
pip install pod-os-py-client[uvloop]
```

## Quick Start

### Connect to a hosted gateway

1. Dial the **chosen** gateway's TCP endpoint (`host:62312`).
2. Set `gateway_actor_name` to **that gateway's FQN** (the connection gateway you dialed — any gateway you are permitted to use; not necessarily the actor's `@domain`).
3. Use a unique `client_name` per TCP connection. The SDK sets `From = client_name@<dialed-gateway-FQN>` (`client.from_address()`). Leave `from_` empty or equal to `from_address()` — a mismatched `from_` raises `ValueError`, not silently rewritten. `gateway_actor_name` is required (no default).
4. Keep roughly **8–10 concurrent** ENM requests per connection when `enable_concurrent_mode` is true; higher fan-out can time out silently.
4. Omit `user_name` / `passcode` unless that gateway's INI requires them. These are optional AIP fields, not Auth0 or dashboard OAuth tokens.
5. If `GatewayId` succeeds but a request times out, the gateway likely could not route the reply — check unique `client_name` and `From`. This is not an authentication failure.

```python
import asyncio
from uuid import uuid4
from pod_os_client import Client, Config
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message

async def main():
    config = Config(
        host="gateway-nlb.example.com",
        port=62312,
        gateway_actor_name="zeroth.customer.example.com",
        client_name=f"my-app-{uuid4().hex[:8]}",
        enable_concurrent_mode=True,
    )
    async with Client(config) as client:
        msg = Message(
            to="Foobar@zeroth.customer.example.com",
            from_=client.from_address(),
            intent=IntentType.GetEvent.name,
            client_name=client.client_name(),
            message_id=str(uuid4()),
        )
        response = await client.send_message(msg)
        print(response.processing_status())

asyncio.run(main())
```

## Configuration

The `Config` dataclass supports extensive configuration options:

```python
from pod_os_client import Config

config = Config(
    # Connection
    host="localhost",
    port=8080,
    network="tcp",  # 'tcp', 'udp', or 'unix'
    gateway_actor_name="zeroth.example.com",
    
    # Identity (passcode/user_name optional — omit unless gateway INI requires them)
    client_name="my_client",
    
    # Timeouts
    dial_timeout=10.0,
    send_timeout=5.0,
    receive_timeout=30.0,
    
    # Retry settings
    max_retries=3,
    initial_backoff=1.0,
    backoff_multiplier=2.0,
    max_backoff=30.0,
    
    # Connection pooling
    enable_pooling=False,
    pool_initial_capacity=1,
    pool_max_capacity=10,
    
    # Features (streaming is on by default; set enable_streaming=False to disable)
    enable_concurrent_mode=True,
    enable_reconnection=True,
    # App owns connection.receive() (Gateway actor / mesh shells). Use send_no_wait().
    external_receiver=False,

    # App-level AIP Keepalive (default 30s; 0 or negative disables)
    keepalive_interval=30.0,
    
    # Logging
    log_level=3,  # 0=None, 1=Error, 2=Warn, 3=Info, 4=Debug
)
```

## External receiver (Gateway actor / mesh shells)

When your process runs its own `connection.receive()` loop (e.g. ActorRequest
dispatch), set `external_receiver=True`. The client then:

- does **not** start its background receive loop
- rejects `send_message()` / `start_receiver()` (they would race `receive()`)
- exposes `send_no_wait(msg)` for fire-and-forget encode+send
- disables send-path auto-reconnect; pause your loop, then `await client.reconnect()`

```python
config = Config(
    host="localhost",
    port=62312,
    client_name="ingest-worker",
    enable_concurrent_mode=False,
    external_receiver=True,
)
client = Client(config)
await client.connect()
await client.send_no_wait(actor_request_msg)
# Idle poll on prefix only; do NOT asyncio.wait_for(receive(), 1.0) — that
# cancels mid-frame on large buffered NM replies (get_match_links).
from pod_os_client.errors import ReceiveIdleTimeoutError
while running:
    try:
        data = await client._connection.receive(timeout=1.0, body_timeout=None)
    except ReceiveIdleTimeoutError:
        continue
    # decode + route ...
```

## App-Level Keepalive

The client sends periodic AIP `Keepalive` frames (message_type 18) on the primary connection and idle pooled connections. Configure with `keepalive_interval` (seconds); default is `30.0`. Set to `0` or negative to disable. The asyncio task starts after connect, pauses during reconnect, and stops on `close()`.

On explicit close (`await client.close()` or async context manager exit), the client sends a fire-and-forget AIP `GatewayDisconnect` frame (message_type 6) on the ID-authenticated primary connection, then closes the TCP socket. Unexpected connection loss and reconnect teardown do not send Disconnect. Unauthenticated pool sockets are closed without Disconnect because they never completed a GatewayId handshake.

## Connection Liveness

In concurrent mode the receive loop polls with a short idle timeout (default **30s**). Idle timeouts are benign — the connection is still considered healthy. If requests are pending but no frame has been received for `connection_liveness_timeout` (default **90s**), the connection is declared dead and reconnect runs when enabled. Set `connection_liveness_timeout` to a negative value to disable this backstop.

## Actor Health Checks (Non-Neural Memory Actors)

Neural Memory Actors are typically probed with store/get intents. **Socket Actors** use the lightweight AIP `StatusRequest` / `Status` pair instead:

| Intent | message_type | Role |
|---|---|---|
| `StatusRequest` | 110 | Inbound health probe (envelope + optional `_msg_id`) |
| `Status` | 3 | Health reply (`_status`, `_msg`, echoed `_msg_id`) |

### Responding to probes (Actor side)

Enable concurrent mode and call `respond_to_health_checks` after connect:

```python
from pod_os_client import Client, Config
from pod_os_client.health import respond_to_health_checks

config = Config(
    host="gateway-lb.example.com",
    port=62312,
    gateway_actor_name="zeroth.pod-os.com",
    client_name="my-socket-actor",
    enable_concurrent_mode=True,
)
client = Client(config)
await client.connect()
respond_to_health_checks(client)
```

### Sending probes (monitor side)

```python
from uuid import uuid4
from pod_os_client.message import Message
from pod_os_client.message.intents import IntentType

probe_id = str(uuid4())
probe = Message(
    to="my-socket-actor@zeroth.pod-os.com",
    from_=f"{client.client_name()}@{client.actor_name()}",
    intent=IntentType.StatusRequest.name,
    client_name=client.client_name(),
    message_id=probe_id,
)
resp = await client.send_message(probe)
assert resp.processing_status() == "OK"
assert resp.message_id == probe_id
```

## Evolutionary Neural Memory Operations

Batch intents expect structured payloads; the encoder formats them automatically (aligned with the Go client):

```python
from pod_os_client.message import Message, PayloadFields
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    BatchEventSpec,
    EventFields,
    NeuralMemoryFields,
    Tag,
)
from uuid import uuid4

# StoreBatchEvents: pass list of BatchEventSpec; encoder formats the payload
batch_msg = Message(
    to="mem@gateway",
    from_="client@gateway",
    intent=IntentType.StoreBatchEvents.name,
    client_name="client",
    message_id=str(uuid4()),
    payload=PayloadFields(
        data=[
            BatchEventSpec(
                event=EventFields(unique_id="ev-1", type="my_type", owner="$sys"),
                tags=[Tag(key="category", value="example", frequency=1)],
            ),
        ],
    ),
)
response = await client.send_message(batch_msg)

# StoreBatchTags: pass list of Tag in payload.data or neural_memory.tags
tag_msg = Message(
    to="mem@gateway",
    from_="client@gateway",
    intent=IntentType.StoreBatchTags.name,
    client_name="client",
    message_id=str(uuid4()),
    payload=PayloadFields(data=[Tag(frequency=1, key="k", value="v")]),
    # Or use neural_memory=NeuralMemoryFields(tags=[...]) when payload is empty
)
```

Other intents (e.g. StoreEvent, StoreData, GetEvent, GetEventsForTags) use `PayloadFields(data=...)` with `str`, `bytes`, or `list[str]` as appropriate.

`StoreData` stores raw payload data associated with a unique identifier, timestamp, and location (no tags):

```python
from uuid import uuid4

data_msg = Message(
    to="mem@gateway",
    from_="client@gateway",
    intent=IntentType.StoreData.name,
    client_name="client",
    message_id=str(uuid4()),
    event=EventFields(
        unique_id=str(uuid4()),
        timestamp=get_timestamp(),
        location="TERRA|47.619463|-122.518691",
        location_separator="|",
    ),
    payload=PayloadFields(data=b"binary or text content", mime_type="application/octet-stream"),
)
response = await client.send_message(data_msg)
```

### Tag Metadata (timestamps and owners)

GetEvent and GetEventsForTags can return each tag's storage time and owning event. Both are opt-in:

```python
from pod_os_client.message import TagOwnerOutput
from pod_os_client.message.types import GetEventOptions, GetEventsForTagsOptions, NeuralMemoryFields

# GetEvent: tag_format=1 adds tag_number and timestamp to every tag
msg.neural_memory = NeuralMemoryFields(get_event=GetEventOptions(get_tags=True, tag_format=1))

# GetEventsForTags: buffer_format="1" adds timestamp; tag_owner_output adds the owner
msg.neural_memory = NeuralMemoryFields(get_events_for_tags=GetEventsForTagsOptions(
    buffer_results=True,
    buffer_format="1",
    tag_owner_output=TagOwnerOutput.UNIQUE_ID,  # or TagOwnerOutput.EVENT_KEY
))

response = await client.send_message(msg)
for tag in response.response.event_records[0].tags:
    print(tag.key, tag.value, tag.time(), tag.owner_unique_id)  # tag.owner with EVENT_KEY
```

`Client.send_message` routes the owner into `owner` (event key) or `owner_unique_id` according to the request. When decoding raw bytes yourself, call `apply_tag_owner_output(request, response)` from `pod_os_client.message`. See "Tag Metadata" in `knowledge/docs/Pod-OS-Neural-Memory-Retrieval-Prompts.md` for the rules.

## Performance Optimization

For maximum performance:

1. **Enable concurrent mode**: Allows multiple in-flight requests
2. **Use connection pooling**: For high-throughput scenarios
3. **Install uvloop**: 2-4x faster event loop (optional)

```python
# Optional: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

config = Config(
    host="localhost",
    port=8080,
    enable_concurrent_mode=True,
    enable_pooling=True,
    pool_max_capacity=20,
)
```

## Architecture

The client is organized into several packages:

- `pod_os_client.client`: Main Client class
- `pod_os_client.config`: Configuration management
- `pod_os_client.message`: Message protocol (encoding, decoding, types)
- `pod_os_client.connection`: Network connection management (TCP/UDP, pooling, retry)
- `pod_os_client.errors`: Custom exceptions

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Type checking:

```bash
mypy pod_os_client
```

Linting and formatting:

```bash
ruff check .
ruff format .
```

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
