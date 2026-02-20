"""Pod-OS client exception hierarchy."""

from enum import Enum
from typing import Optional

__all__ = [
    "PodOSError",
    "ConnectionError",
    "MessageError",
    "EncodeError",
    "DecodeError",
    "TimeoutError",
    "AuthenticationError",
    "DecodeErrorCode",
    "EncodeErrorCode",
]


class DecodeErrorCode(Enum):
    """Error codes for message decoding failures."""

    DECODE_MESSAGE_TOO_SHORT = "DECODE_MESSAGE_TOO_SHORT"
    DECODE_INVALID_SIZE_PARAM = "DECODE_INVALID_SIZE_PARAM"
    DECODE_PAYLOAD_TOO_LARGE = "DECODE_PAYLOAD_TOO_LARGE"
    DECODE_INVALID_HEADER = "DECODE_INVALID_HEADER"
    DECODE_INVALID_MESSAGE_TYPE = "DECODE_INVALID_MESSAGE_TYPE"
    DECODE_INVALID_DATA_TYPE = "DECODE_INVALID_DATA_TYPE"
    DECODE_HEADER_TRANSFORMATION_FAILED = "DECODE_HEADER_TRANSFORMATION_FAILED"
    DECODE_UNKNOWN_INTENT = "DECODE_UNKNOWN_INTENT"
    DECODE_PAYLOAD_PARSE_FAILED = "DECODE_PAYLOAD_PARSE_FAILED"


class EncodeErrorCode(Enum):
    """Error codes for message encoding failures."""

    ENCODE_MESSAGE_NIL = "ENCODE_MESSAGE_NIL"
    ENCODE_PAYLOAD_TOO_LARGE = "ENCODE_PAYLOAD_TOO_LARGE"
    ENCODE_INVALID_ADDRESS = "ENCODE_INVALID_ADDRESS"
    ENCODE_INVALID_TAG_VALUE = "ENCODE_INVALID_TAG_VALUE"
    ENCODE_HEADER_CONSTRUCTION_FAILED = "ENCODE_HEADER_CONSTRUCTION_FAILED"
    ENCODE_BATCH_PAYLOAD_FAILED = "ENCODE_BATCH_PAYLOAD_FAILED"


class PodOSError(Exception):
    """Base exception for all Pod-OS client errors."""

    pass


class ConnectionError(PodOSError):
    """Connection-related errors."""

    pass


class MessageError(PodOSError):
    """Message encoding/decoding errors."""

    pass


class EncodeError(MessageError):
    """Message encoding errors with detailed context.

    Attributes:
        message: Error description
        field: Field name that caused the error
        code: Error code enum value
        original_error: Optional wrapped exception
    """

    def __init__(
        self,
        message: str,
        field: str = "",
        code: Optional[EncodeErrorCode] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """Initialize encode error.

        Args:
            message: Error description
            field: Field name that caused the error
            code: Error code enum value
            original_error: Optional wrapped exception
        """
        super().__init__(message)
        self.field = field
        self.code = code
        self.original_error = original_error

    def __str__(self) -> str:
        """Format error message with context."""
        parts = []
        if self.code:
            parts.append(f"[{self.code.value}]")
        if self.field:
            parts.append(f"field={self.field}")
        parts.append(super().__str__())
        if self.original_error:
            parts.append(f"cause: {self.original_error}")
        return " ".join(parts)


class DecodeError(MessageError):
    """Message decoding errors with detailed context.

    Attributes:
        message: Error description
        field: Field name that caused the error
        code: Error code enum value
        original_error: Optional wrapped exception
    """

    def __init__(
        self,
        message: str,
        field: str = "",
        code: Optional[DecodeErrorCode] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """Initialize decode error.

        Args:
            message: Error description
            field: Field name that caused the error
            code: Error code enum value
            original_error: Optional wrapped exception
        """
        super().__init__(message)
        self.field = field
        self.code = code
        self.original_error = original_error

    def __str__(self) -> str:
        """Format error message with context."""
        parts = []
        if self.code:
            parts.append(f"[{self.code.value}]")
        if self.field:
            parts.append(f"field={self.field}")
        parts.append(super().__str__())
        if self.original_error:
            parts.append(f"cause: {self.original_error}")
        return " ".join(parts)


class TimeoutError(PodOSError):
    """Operation timeout errors."""

    pass


class AuthenticationError(PodOSError):
    """Authentication failure errors."""

    pass
