"""Poll until an actor or gateway answers an AIP health probe."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pod_os_client.message.types import Message
from pod_os_client.readiness.health_probe import (
    actor_health_probe_succeeded,
    build_actor_health_probe_message,
)

SendFunc = Callable[[Message, str], Awaitable[Message]]


@dataclass
class ActorAIPReadinessConfig:
    """Tuning for the readiness polling loop."""

    timeout: float = 0.0
    initial_backoff: float = 0.0
    max_backoff: float = 0.0
    required_consecutive: int = 0
    success_interval: float = 0.0

    def normalized(self) -> ActorAIPReadinessConfig:
        return ActorAIPReadinessConfig(
            timeout=self.timeout if self.timeout > 0 else 60.0,
            initial_backoff=self.initial_backoff if self.initial_backoff > 0 else 2.0,
            max_backoff=self.max_backoff if self.max_backoff > 0 else 8.0,
            required_consecutive=self.required_consecutive if self.required_consecutive > 0 else 1,
            success_interval=self.success_interval if self.success_interval > 0 else 2.0,
        )


@dataclass
class GatewayReadinessProbe:
    """Stable anchor actor for gateway route readiness."""

    probe_actor: str = ""
    probe_actor_type: str = ""


async def wait_for_actor_aip_ready(
    send: SendFunc,
    actor_address: str,
    from_address: str,
    client_name: str,
    actor_type: str,
    rc: ActorAIPReadinessConfig | None = None,
) -> None:
    """Poll until the named actor answers an AIP health probe."""
    await _wait_for_aip_ready(send, actor_address, from_address, client_name, actor_type, rc)


async def wait_for_gateway_aip_ready(
    send: SendFunc,
    probe: GatewayReadinessProbe,
    from_address: str,
    client_name: str,
    rc: ActorAIPReadinessConfig | None = None,
) -> None:
    """Poll until the anchor actor in probe answers an AIP health probe."""
    if not probe.probe_actor:
        raise ValueError("gateway readiness probe: probe_actor is required")
    await _wait_for_aip_ready(
        send,
        probe.probe_actor,
        from_address,
        client_name,
        probe.probe_actor_type,
        rc,
    )


async def _wait_for_aip_ready(
    send: SendFunc,
    actor_address: str,
    from_address: str,
    client_name: str,
    actor_type: str,
    rc: ActorAIPReadinessConfig | None,
) -> None:
    if send is None:
        raise ValueError("gateway readiness: nil send function")

    cfg = (rc or ActorAIPReadinessConfig()).normalized()
    backoff = cfg.initial_backoff
    loop = asyncio.get_running_loop()
    deadline = loop.time() + cfg.timeout
    last_err: Exception | None = None
    consecutive = 0
    attempt = 0

    while loop.time() < deadline:
        attempt += 1
        probe_msg = build_actor_health_probe_message(
            actor_address, from_address, client_name, actor_type
        )
        label = f"aip_ready_{actor_address}"
        send_err: Exception | None = None
        aip: Message | None = None
        try:
            aip = await send(probe_msg, label)
        except Exception as exc:
            send_err = exc

        if actor_health_probe_succeeded(send_err, aip):
            consecutive += 1
            if consecutive >= cfg.required_consecutive:
                return
            backoff = cfg.initial_backoff
            await asyncio.sleep(cfg.success_interval)
            continue

        consecutive = 0
        if send_err is not None:
            last_err = send_err
        elif aip is not None:
            last_err = RuntimeError(f"actor returned error: {aip.processing_message()}")
        else:
            last_err = RuntimeError("probe returned no response")

        await asyncio.sleep(backoff)
        if backoff < cfg.max_backoff:
            backoff = min(backoff * 2, cfg.max_backoff)

    if last_err is None:
        last_err = TimeoutError("deadline exceeded")
    raise TimeoutError(
        f"actor {actor_address} not reachable over AIP within {cfg.timeout}s: {last_err}"
    ) from last_err
