"""Pod-OS Python Client.

High-performance Python client library for Pod-OS Actor system with Evolutionary Neural Memory support.
"""

from pod_os_client.client import Client, ConnectionState
from pod_os_client.config import Config, ReconnectConfig
from pod_os_client.readiness import (
    ActorAIPReadinessConfig,
    GatewayReadinessProbe,
    wait_for_actor_aip_ready,
    wait_for_gateway_aip_ready,
)
from pod_os_client.errors import (
    AuthenticationError,
    ConnectionError,
    MessageError,
    PodOSError,
    TimeoutError,
)

__version__ = "0.1.1"

__all__ = [
    "Client",
    "Config",
    "ConnectionState",
    "ReconnectConfig",
    "ActorAIPReadinessConfig",
    "GatewayReadinessProbe",
    "wait_for_actor_aip_ready",
    "wait_for_gateway_aip_ready",
    "PodOSError",
    "ConnectionError",
    "MessageError",
    "TimeoutError",
    "AuthenticationError",
]
