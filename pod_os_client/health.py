"""Actor health-check helpers for non-Neural Memory socket Actors."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pod_os_client.message.encoder import encode_message
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, ResponseFields

if TYPE_CHECKING:
    from pod_os_client.client import Client

logger = logging.getLogger(__name__)

__all__ = ["build_status_health_reply", "respond_to_health_checks"]


def build_status_health_reply(client: Client, inbound: Message) -> Message:
    """Construct a Status response for an inbound StatusRequest probe."""
    request_id = inbound.message_id if inbound is not None else ""
    to = inbound.from_ if inbound is not None else ""
    return Message(
        to=to,
        from_=f"{client.client_name()}@{client.actor_name()}",
        intent=IntentType.Status.name,
        client_name=client.client_name(),
        message_id=request_id,
        response=ResponseFields(status="OK", message="actor is healthy"),
    )


def respond_to_health_checks(client: Client) -> None:
    """Register an unmatched-message handler that replies to StatusRequest probes.

    Requires enable_concurrent_mode so the background receiver is active.
    """
    if client is None:
        return

    async def _send_reply(inbound: Message) -> None:
        if inbound.intent != IntentType.StatusRequest.name:
            return
        reply = build_status_health_reply(client, inbound)
        try:
            wire = encode_message(reply, IntentType.Status, client._conversation_id)
            await client.send_control_message(wire)
        except Exception as exc:
            logger.debug("health reply failed: %s", exc)

    def handler(inbound: Message) -> None:
        asyncio.create_task(_send_reply(inbound))

    client.set_unmatched_message_handler(handler)
