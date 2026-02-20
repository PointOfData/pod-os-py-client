"""Neural Memory operations example."""

import asyncio
from uuid import uuid4

from pod_os_client import Client, Config
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    EventFields,
    GetEventOptions,
    Message,
    NeuralMemoryFields,
    PayloadFields,
    Tag,
)


async def main() -> None:
    """Demonstrate Neural Memory database operations."""
    config = Config(
        host="localhost",
        port=62312,
        client_name="neural_memory_example",
        passcode="your_passcode",
        user_name="your_username",
    )

    async with Client(config) as client:
        print("Neural Memory Operations Demo\n")

        # 1. Store an event with tags
        unique_id = f"demo-event-{uuid4()}"
        print(f"1. Storing event with unique_id: {unique_id}")

        store_msg = Message(
            to="mem@gateway",
            from_=f"{config.client_name}@gateway",
            intent=IntentType.StoreEvent.name,
            message_id=str(uuid4()),
            event=EventFields(
                unique_id=unique_id,
                type="demo_event",
                owner="$sys",
            ),
            payload=PayloadFields(
                data="This is example event data",
                mime_type="text/plain",
            ),
            neural_memory=NeuralMemoryFields(
                tags=[
                    Tag(key="category", value="example", frequency=1),
                    Tag(key="priority", value="high", frequency=1),
                ]
            ),
        )

        response = await client.send_message(store_msg)
        print(f"   Status: {response.processing_status()}")
        print(f"   Message: {response.processing_message()}\n")

        # 2. Retrieve the event
        print(f"2. Retrieving event by unique_id: {unique_id}")

        get_msg = Message(
            to="mem@gateway",
            from_=f"{config.client_name}@gateway",
            intent=IntentType.GetEvent.name,
            message_id=str(uuid4()),
            event=EventFields(unique_id=unique_id),
            neural_memory=NeuralMemoryFields(
                get_event=GetEventOptions(
                    send_data=True,
                    get_tags=True,
                )
            ),
        )

        get_response = await client.send_message(get_msg)
        print(f"   Status: {get_response.processing_status()}")
        if get_response.response:
            print(f"   Event count: {get_response.response.total_events}")
            print(f"   Tag count: {get_response.response.tag_count}")
        if get_response.payload:
            print(f"   Data: {get_response.payload.data}\n")

        print("Neural Memory operations completed!")


if __name__ == "__main__":
    asyncio.run(main())
