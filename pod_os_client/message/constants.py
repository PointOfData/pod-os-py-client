"""Pod-OS message constants and limits."""

# Maximum allowed size of a full Pod-OS message in bytes,
# including length prefix, header, tags, and payload.
#
# The wire-format length prefix is a 9-byte field that can express values up to
# ~999,999,999 bytes in decimal or 0xffffffff (~4GB) in hex. However, this
# client constrains the total message size to 2 GiB to avoid excessive memory
# usage and to provide a consistent upper bound for both encoding and decoding.
MAX_MESSAGE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GiB


# DataType represents the data type for message payloads
class DataType:
    """Data type constants for message payloads."""

    RAW = 0
    # BPE = 0x0001
    # GZIP = 0x0002
    # LZ7 = 0x0004
    # BZIP = 0x0008
    # RC4 = 0x0100
