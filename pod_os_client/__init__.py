"""Pod-OS Python Client.

High-performance Python client library for Pod-OS Actor system with Evolutionary Neural Memory support.
"""

from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.errors import (
    AuthenticationError,
    ConnectionError,
    MessageError,
    PodOSError,
    TimeoutError,
)

__version__ = "0.1.0"

__all__ = [
    "Client",
    "Config",
    "PodOSError",
    "ConnectionError",
    "MessageError",
    "TimeoutError",
    "AuthenticationError",
]
