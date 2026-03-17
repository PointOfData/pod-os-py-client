# Pod-OS Python Client

High-performance Python client library for registering as a Pod-OS Actor and or communicating with a Pod-OS Actor, handling the Pod-OS/AIP message protocol (send and receive), and includes Intents for Neural Memory database operations.

## Features

- **Async/Await Support**: Built on asyncio for high concurrency and low latency
- **Connection Management**: TCP/UDP support with automatic reconnection and exponential backoff
- **Connection Pooling**: Optional pooling for high-throughput scenarios
- **Message Protocol**: Full Pod-OS message encoding/decoding with MessagePack
- **Neural Memory**: Complete Neural Memory database operations (store, retrieve, link, search)
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

```python
import asyncio
from pod_os_client import Client, Config

async def main():
    # Configure client
    config = Config(
        host="localhost",
        port=8080,
        client_name="my_client",
        passcode="secret",
        enable_concurrent_mode=True
    )
    
    # Create and connect client
    client = Client(config)
    await client.connect()
    
    # Send a message
    from pod_os_client.message import Message
    from uuid import uuid4
    
    msg = Message(
        intent="ActorEcho",
        payload={"message": "Hello, Pod-OS!"},
        message_id=uuid4()
    )
    
    response = await client.send_message(msg)
    print(f"Response: {response.payload}")
    
    # Close connection
    await client.close()

if __name__ == "__main__":
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
    
    # Authentication
    client_name="my_client",
    passcode="secret",
    user_name="user",
    
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
    
    # Logging
    log_level=3,  # 0=None, 1=Error, 2=Warn, 3=Info, 4=Debug
)
```

## Neural Memory Operations

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
