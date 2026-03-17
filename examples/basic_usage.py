"""Basic usage example for Pod-OS Python client."""

import asyncio
from uuid import uuid4

from pod_os_client import Client, Config
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import EventFields, Message, PayloadFields


async def main() -> None:
    """Demonstrate basic Pod-OS client usage."""
    # Configure client
    config = Config(
        host="localhost",
        port=62312,
        client_name="example_client",
        passcode="your_passcode",
        user_name="your_username",
        enable_concurrent_mode=True,
    )

    # Create and connect client using context manager
    async with Client(config) as client:
        print(f"Connected to Pod-OS Gateway: {config.host}:{config.port}")

        # Send an echo message
        echo_msg = Message(
            to="$system@gateway",
            from_=f"{config.client_name}@gateway",
            intent=IntentType.ActorEcho.name,
            message_id=str(uuid4()),
            payload=PayloadFields(data="Hello, Pod-OS!"),
        )

        print(f"Sending echo message: {echo_msg.message_id}")
        response = await client.send_message(echo_msg)
        print(f"Received response: {response.payload_data()}")

        # Store an event in Evolutionary Neural Memory
        store_msg = Message(
            to="mem@gateway",
            from_=f"{config.client_name}@gateway",
            intent=IntentType.StoreEvent.name,
            message_id=str(uuid4()),
            event=EventFields(
                unique_id=f"example-event-{uuid4()}",
                type="example_event",
                owner="$sys",
            ),
            payload=PayloadFields(
                data="Example event data",
                mime_type="text/plain",
            ),
        )

        print(f"Storing event: {store_msg.event.unique_id}")  # type: ignore[union-attr]
        store_response = await client.send_message(store_msg)
        print(f"Store status: {store_response.processing_status()}")

        print("\nClient operations completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
