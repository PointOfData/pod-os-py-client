# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Extended tag formats with per-tag storage timestamps and owners: GetEvent `tag_format=1`
  and GetEventsForTags `buffer_format="1"` (one `_event_tag` line per tag).
- `TagOwnerOutput` (`NONE`, `EVENT_KEY`, `UNIQUE_ID`) on `GetEventOptions.tag_owner_output`
  (`output_tag_owner=Y`/`N`) and `GetEventsForTagsOptions.tag_owner_output`
  (`get_tag_owner=Y` / `get_tag_owner_unique_id=Y`).
- `TagOutput.tag_number`, `TagOutput.owner_unique_id`, and `TagOutput.time()` (UTC `datetime`
  from `TagOutput.timestamp`).
- `apply_tag_owner_output(request, response)` moves owners into `owner_unique_id` when the
  request asked for unique IDs; `Client.send_message` applies it automatically.
- Validation for `tag_format`, `buffer_format`, `tag_owner_output`, and the matching wire flags.

### Fixed
- GetEventsForTags `buffer_format=1` responses requested with an owner flag: Pod-OS writes
  `\towner=` after the tag line's newline, gluing it onto the next record. The decoder rejoins
  each owner to its tag line and restores the record break.
- Tag owners `NULL` and the all-zero event key (unowned / `$sys` tags) decode as empty.
- GetEvent tag frequency is read from the third `event_tag:<seq>:<freq>` component instead of the
  tag sequence number, and tags are returned ordered by sequence.
- GetEventsForTags `buffer_format=0` keeps every inline tag, including repeated tags with the same
  key and frequency.

## [0.1.2] - 2026-08-18

### Added
- Store batch response decoding for events and links (count mapping and finalization).
- Configurable connection liveness timeout with default and disabled states.
- Receive idle timeout for large frame body reads, preventing premature cancellation during large transfers.
- Client message normalization so sender `From` aligns with the connection gateway identity.

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

[0.1.2]: https://github.com/PointOfData/pod-os-py-client/releases/tag/v0.1.2
[0.1.1]: https://github.com/PointOfData/pod-os-py-client/releases/tag/v0.1.1
[0.1.0]: https://github.com/PointOfData/pod-os-py-client/releases/tag/v0.1.0
