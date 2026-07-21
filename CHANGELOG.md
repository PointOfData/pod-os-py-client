# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-07-21

### Added
- `Config.external_receiver` — application owns the sole `connection.receive()` waiter
  (Gateway / mesh actor shells). Disables the client's background receive loop and
  send-path auto-reconnect that would race an external receive.
- `Client.send_no_wait(msg)` — encode + send without calling `receive()`.
- `Client.deliver_response(msg)` — complete a pending future from an external loop.
- `Client.reconnect()` — explicit reconnect after the app has paused its receive loop.
- Env `PODOS_EXTERNAL_RECEIVER` and INI `external_receiver`.

### Fixed
- Prevent `readexactly() called while another coroutine is already waiting` when an
  app receive loop coexists with sync `send_message` / client auto-reconnect.

## [0.1.0] - 2024-02-15

### Added
- Initial release of Pod-OS Python client
- Async/await support with asyncio
- Full Pod-OS message protocol implementation
- Message encoding/decoding with wire format support
- TCP connection management with automatic reconnection
- Connection pooling for high-throughput scenarios
- Concurrent message handling with MessageId-based routing
- Evolutionary Neural Memory database operations (store, retrieve, link, search)
- Comprehensive type hints and mypy validation
- Configuration management with validation
- Error handling with custom exception hierarchy
- Test suite with pytest

### Features
- Python 3.12+ support
- Full feature parity with Go client
- Sub-millisecond encoding/decoding performance
- Exponential backoff retry logic
- Context manager support for client lifecycle
- Streaming mode support (STREAM ON/OFF)

[0.1.1]: https://github.com/PointOfData/pod-os-py-client/releases/tag/v0.1.1
[0.1.0]: https://github.com/PointOfData/pod-os-py-client/releases/tag/v0.1.0
