## Message handling

The client communicates with Gateway Actors and Actors via `Client.send_message()` and the returned `Message`. `send_message()` takes a `Message`, encodes it to the wire format, sends it to the Gateway Actor's connection, and returns the decoded response `Message`. The Gateway uses the `to` and `from_` addressing to route the message. Messages are sent and received much like e-mail.

Message structure: Messages are composed of two address specifications (`to`, `from_`), a header (including `intent`, `client_name`, `message_id`), and an optional data payload which may be up to 2 gigabytes in size. The address specifications are strings (actor@gateway). The message type is derived from the intent. The payload is carried in `Message.payload` with `data`, `data_type`, and `mime_type`.

Connection event sequence: When connecting to a Gateway Actor, a socket connection is first established at which point the Gateway Actor is aware that there is a client, but has no other information about the connection. The Gateway Actor assigns the connection a temporary internal name. Following the connection, an identifier message (GatewayId) is sent by the connecting client which identifies the connection point so that message traffic can be routed appropriately.

The ID message is required before any other messages will be recognized. Until the ID message is received, all messages received from the new client will be ignored. However, shutdown or forced disconnect messages may be sent to the new service. Once an ID is established, messages can be addressed and delivered to the specified Actor@Gateway.

The client uses one of two states: (a) the Gateway is streaming responses for asynchronous message ("STREAM ON"), or (b) synchronous message mode where the Client requests message one at a time from a mailbox queue ("STREAM OFF"). Default state is "STREAM OFF". The Python client uses STREAM ON by default (`Config.enable_streaming=True`) for responsiveness.

There are two use cases to support:

1. **Client (e.g. a script or service)** uses `Client.send_message(msg)` to send a message and inspects the returned `Message` (e.g. `response.processing_status()`, `response.payload_data()`, `response.event`) to manage Actors.

2. **Optionally**, customers may use SocketIO events vended by Dashboard software acting as a proxy client to exchange JSON objects and stream binary payload attachments. SocketIO events are not provided by this package; check with the Dashboard software for details.

### Python example: send and handle response

```python
import asyncio
from uuid import uuid4
from pod_os_client import Client, Config
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, EventFields, PayloadFields

async def main():
    config = Config(
        host="localhost",
        port=62312,
        client_name="MyApp",
        gateway_actor_name="zeroth.example.com",
        passcode="pass",
        user_name="user",
    )
    async with Client(config) as client:
        msg = Message(
            to="mem@zeroth.example.com",
            from_=f"{config.client_name}@{config.gateway_actor_name}",
            intent=IntentType.StoreEvent.name,
            client_name=config.client_name,
            message_id=str(uuid4()),
            event=EventFields(
                unique_id=str(uuid4()),
                owner="$sys",
                type="example",
            ),
            payload=PayloadFields(data="Hello", mime_type="text/plain"),
        )
        response = await client.send_message(msg)
        status = response.processing_status()  # "OK" or "ERROR"
        detail = response.processing_message()
        if response.event:
            event_id = response.event_id()

asyncio.run(main())
```
