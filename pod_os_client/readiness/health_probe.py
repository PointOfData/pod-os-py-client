"""AIP health probe message construction and success evaluation."""

from __future__ import annotations

from uuid import uuid4

from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import GetEventsForTagsOptions, Message, NeuralMemoryFields, PayloadFields

_NM_PROBE_TYPES = frozenset(
    {
        "pod_db",
        "evolutionary-neural-memory",
        "neural_memory",
        "neural-memory",
    }
)


def is_neural_memory_backed_for_health_probe(actor_type: str) -> bool:
    """Return True when actor type can answer Neural-Memory intents."""
    return actor_type.strip().lower() in _NM_PROBE_TYPES


def build_actor_health_probe_message(
    actor_address: str,
    from_address: str,
    client_name: str,
    actor_type: str,
) -> Message:
    """Build the AIP health probe for one actor based on type."""
    message_id = str(uuid4())

    if is_neural_memory_backed_for_health_probe(actor_type):
        health_check_tag = f"_podos_health_check_{uuid4()}"
        search_clause = f"health_check={health_check_tag}"
        return Message(
            to=actor_address,
            from_=from_address,
            intent=IntentType.GetEventsForTags.name,
            client_name=client_name,
            message_id=message_id,
            payload=PayloadFields(data=search_clause),
            neural_memory=NeuralMemoryFields(
                get_events_for_tags=GetEventsForTagsOptions(count_only=True),
            ),
        )

    return Message(
        to=actor_address,
        from_=from_address,
        intent=IntentType.StatusRequest.name,
        client_name=client_name,
        message_id=message_id,
    )


def actor_health_probe_succeeded(err: BaseException | None, resp: Message | None) -> bool:
    """Return True when transport and AIP status indicate probe success."""
    if err is not None:
        return False
    return resp is None or resp.processing_status() != "ERROR"
