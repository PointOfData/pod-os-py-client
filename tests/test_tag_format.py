"""Tests for extended tag formats: GetEvent tag_format=1 and GetEventsForTags buffer_format=1.

Fixtures in tests/fixtures/tag_format are raw Pod-OS response frames captured live from a
kind cluster (see knowledge/docs/Pod-OS-Intent-Field-Validation.md, "Tag formats").
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import pod_os_client.message.validate as validate_mod
from pod_os_client.client import Client
from pod_os_client.config import Config
from pod_os_client.message import TagOwnerOutput, apply_tag_owner_output
from pod_os_client.message.decoder import decode_message
from pod_os_client.message.encoder import encode_message
from pod_os_client.message.header import (
    _get_event_message_header,
    _get_events_for_tag_message_header,
)
from pod_os_client.message.intents import IntentType
from pod_os_client.message.tag_format import normalize_tag_owner_lines, parse_event_tag_header
from pod_os_client.message.types import (
    EventFields,
    GetEventOptions,
    GetEventsForTagsOptions,
    Message,
    NeuralMemoryFields,
    PayloadFields,
    TagOutput,
    parse_posix_timestamp,
)
from pod_os_client.message.validate import validate_message, validate_raw_message

FIXTURES = Path(__file__).parent / "fixtures" / "tag_format"

OWNER_KEY = "+1790266973.206042\x01TERRA\x0247.6\x02-122.5"
TARGET_KEY = "+1790266973.420335\x01TERRA\x0247.6\x02-122.5"
OWNED_KEY = "+1790266973.723095\x01TERRA\x0247.6\x02-122.5"
OWNER_UID = "tagprobe-owner-dlnoodm3eox6"
TARGET_UID = "tagprobe-target-dlnoodm3eox6"
OWNED_UID = "tagprobe-owned-dlnoodm3eox6"
PROBE_VALUE = "dlnoodm3eox6"


def _decode_fixture(name: str) -> Message:
    return decode_message((FIXTURES / f"{name}.bin").read_bytes())


def _find_tags(tags: list[TagOutput], key: str, value: str = "") -> list[TagOutput]:
    return [t for t in tags if t.key == key and (not value or t.value == value)]


def _event_by_key(msg: Message, key: str) -> EventFields:
    assert msg.response is not None
    for event in msg.response.event_records:
        if event.id == key:
            return event
    raise AssertionError(f"event {key!r} not found in {len(msg.response.event_records)} records")


# ---------------------------------------------------------------------------
# GetEvent decoding
# ---------------------------------------------------------------------------

def test_decode_get_event_tag_format_0() -> None:
    msg = _decode_fixture("get_event_tag_format_0")
    assert msg.event is not None
    tags = msg.event.tags
    assert len(tags) == 36
    for i, tag in enumerate(tags):
        assert tag.tag_number == i + 1, "tags must be ordered by tag number"
        assert tag.timestamp == "" and tag.owner == ""
    color = _find_tags(tags, "color", "red")
    assert len(color) == 1
    assert color[0].frequency == 3
    assert color[0].tag_number == 18
    size = _find_tags(tags, "size")
    assert len(size) == 2
    assert size[0].value == "a:b=c"


@pytest.mark.parametrize(
    "name", ["get_event_tag_format_1", "get_event_tag_format_1_output_tag_owner_y"]
)
def test_decode_get_event_tag_format_1(name: str) -> None:
    msg = _decode_fixture(name)
    assert msg.event is not None and msg.response is not None
    tags = msg.event.tags
    assert len(tags) == 36
    assert len(msg.response.event_records) == 1
    assert len(msg.response.event_records[0].tags) == 36

    size = _find_tags(tags, "size", "a:b=c")
    assert len(size) == 2
    assert size[0].tag_number == 19
    assert size[0].frequency == 5
    assert size[0].timestamp == "1790266974.325930"
    assert size[1].timestamp == "1790266974.325980"

    ts = size[0].time()
    assert ts == datetime.fromtimestamp(1790266974, tz=timezone.utc).replace(microsecond=325930)
    assert ts is not None and ts.tzinfo == timezone.utc

    w = _find_tags(tags, "$W")
    assert len(w) == 1
    assert w[0].value == "TERRA\x0247.6\x02-122.5"
    assert w[0].tag_number == 1

    # This Pod-OS build omits the owner segment on GetEvent even with output_tag_owner=Y.
    assert all(tag.owner == "" for tag in tags)


@pytest.mark.parametrize(
    ("header", "value", "want"),
    [
        pytest.param("event_tag:000000017:4", "k=v",
                     TagOutput(tag_number=17, frequency=4, key="k", value="v"), id="format 0"),
        pytest.param("event_tag:000000002:3:1790266974.325930", "k=a=b",
                     TagOutput(tag_number=2, frequency=3, timestamp="1790266974.325930", key="k", value="a=b"),
                     id="format 1 without owner"),
        pytest.param("event_tag:000000003:1:1790266974.000001:" + OWNER_KEY, "k=v",
                     TagOutput(tag_number=3, frequency=1, timestamp="1790266974.000001", owner=OWNER_KEY,
                               key="k", value="v"),
                     id="format 1 with event key owner"),
        pytest.param("event_tag:000000004:1:1790266974.000001:urn:a:b", "k=v",
                     TagOutput(tag_number=4, frequency=1, timestamp="1790266974.000001", owner="urn:a:b",
                               key="k", value="v"),
                     id="format 1 owner containing colons"),
        pytest.param("event_tag:000000005:1:1790266974.000001:NULL", "k=v",
                     TagOutput(tag_number=5, frequency=1, timestamp="1790266974.000001", key="k", value="v"),
                     id="format 1 NULL owner"),
        pytest.param("event_tag:000000006:1:1790266974.000001:+0000000000.000000\x01000000.000000", "k=v",
                     TagOutput(tag_number=6, frequency=1, timestamp="1790266974.000001", key="k", value="v"),
                     id="format 1 null event key owner"),
    ],
)
def test_parse_event_tag_header_formats(header: str, value: str, want: TagOutput) -> None:
    assert parse_event_tag_header(header, value) == want


def test_parse_event_tag_header_rejects_non_tag_header() -> None:
    assert parse_event_tag_header("unique_id", "x") is None


# ---------------------------------------------------------------------------
# GetEventsForTags decoding
# ---------------------------------------------------------------------------

def test_decode_events_for_tags_buffer_format_0() -> None:
    msg = _decode_fixture("events_for_tag_buffer_format_0")
    assert msg.response is not None
    assert len(msg.response.event_records) == 2
    target = _event_by_key(msg, TARGET_KEY)
    # Includes both duplicate tag:5:size=a:b=c fields.
    assert len(target.tags) == 21
    assert target.unique_id == TARGET_UID
    assert all(tag.timestamp == "" for tag in target.tags)


def test_decode_events_for_tags_buffer_format_1() -> None:
    msg = _decode_fixture("events_for_tag_buffer_format_1")
    assert msg.response is not None
    assert len(msg.response.event_records) == 2
    target = _event_by_key(msg, TARGET_KEY)
    owned = _event_by_key(msg, OWNED_KEY)
    assert len(target.tags) == 21
    assert len(owned.tags) == 18
    assert target.unique_id == TARGET_UID
    assert owned.unique_id == OWNED_UID

    color = _find_tags(target.tags, "color", "red")
    assert len(color) == 1
    assert color[0].frequency == 3
    assert color[0].timestamp == "1790266973.722260"
    assert color[0].owner == ""

    probe = _find_tags(owned.tags, "probe_sfx", PROBE_VALUE)
    assert len(probe) == 1
    assert probe[0].frequency == 4
    assert probe[0].timestamp == "1790266974.024690"


def test_decode_events_for_tags_buffer_format_1_owner_event_key() -> None:
    msg = _decode_fixture("events_for_tag_buffer_format_1_get_tag_owner")
    target = _event_by_key(msg, TARGET_KEY)
    owned = _event_by_key(msg, OWNED_KEY)
    assert len(target.tags) == 21
    assert len(owned.tags) == 18

    color = _find_tags(target.tags, "color", "red")
    assert len(color) == 1 and color[0].owner == "", "$sys-owned tag owner must be empty"
    size = _find_tags(target.tags, "size", "a:b=c")
    assert len(size) == 2
    assert all(s.owner == OWNER_KEY for s in size)
    uid = _find_tags(target.tags, "_unique_id")
    assert len(uid) == 1 and uid[0].owner == TARGET_KEY
    w = _find_tags(owned.tags, "$W")
    assert len(w) == 1
    assert w[0].owner == OWNER_KEY
    assert w[0].timestamp == "1790266974.024420"

    for tag in target.tags + owned.tags:
        assert "_event_tag" not in tag.owner, f"owner not separated from next record: {tag}"
        assert "owner" not in tag.timestamp, f"owner not separated from timestamp: {tag}"


def test_decode_events_for_tags_buffer_format_1_owner_unique_id() -> None:
    req = Message(
        intent=IntentType.GetEventsForTags.name,
        neural_memory=NeuralMemoryFields(get_events_for_tags=GetEventsForTagsOptions(
            buffer_format="1", tag_owner_output=TagOwnerOutput.UNIQUE_ID,
        )),
    )
    msg = _decode_fixture("events_for_tag_buffer_format_1_get_tag_owner_unique_id")
    apply_tag_owner_output(req, msg)

    target = _event_by_key(msg, TARGET_KEY)
    owned = _event_by_key(msg, OWNED_KEY)
    color = _find_tags(target.tags, "color", "red")
    assert len(color) == 1
    assert color[0].owner == "" and color[0].owner_unique_id == "", "NULL owner must be normalized"
    size = _find_tags(target.tags, "size", "a:b=c")
    assert len(size) == 2
    for s in size:
        assert s.owner_unique_id == OWNER_UID
        assert s.owner == ""
    uid = _find_tags(owned.tags, "_unique_id")
    assert len(uid) == 1 and uid[0].owner_unique_id == OWNED_UID


# ---------------------------------------------------------------------------
# apply_tag_owner_output
# ---------------------------------------------------------------------------

def test_apply_tag_owner_output_noop_for_event_key() -> None:
    req = Message(
        intent=IntentType.GetEvent.name,
        neural_memory=NeuralMemoryFields(get_event=GetEventOptions(tag_owner_output=TagOwnerOutput.EVENT_KEY)),
    )
    resp = Message(event=EventFields(tags=[TagOutput(key="k", owner=OWNER_KEY)]))
    apply_tag_owner_output(req, resp)
    assert resp.event is not None
    assert resp.event.tags[0].owner == OWNER_KEY
    assert resp.event.tags[0].owner_unique_id == ""


def test_apply_tag_owner_output_shared_tag_list_is_moved_once() -> None:
    req = Message(
        intent=IntentType.GetEvent.name,
        neural_memory=NeuralMemoryFields(get_event=GetEventOptions(
            tag_format=1, tag_owner_output=TagOwnerOutput.UNIQUE_ID,
        )),
    )
    msg = decode_message((FIXTURES / "get_event_tag_format_1.bin").read_bytes())
    assert msg.event is not None and msg.response is not None
    msg.event.tags[0].owner = OWNER_UID
    assert msg.response.event_records[0].tags is msg.event.tags

    apply_tag_owner_output(req, msg)

    assert msg.event.tags[0].owner == ""
    assert msg.event.tags[0].owner_unique_id == OWNER_UID


def test_apply_tag_owner_output_tolerates_none() -> None:
    apply_tag_owner_output(None, None)
    apply_tag_owner_output(Message(intent="GetEvent"), Message())


def test_client_send_message_applies_tag_owner_output() -> None:
    client = Client(Config(
        host="localhost", port=62312, gateway_actor_name="zeroth.pod-os.com",
        client_name="c", enable_concurrent_mode=False,
    ))
    client._connected = True
    conn = MagicMock()
    conn.send = AsyncMock()
    conn.receive = AsyncMock(
        return_value=(FIXTURES / "events_for_tag_buffer_format_1_get_tag_owner_unique_id.bin").read_bytes()
    )
    client._connection = conn
    req = _events_for_tags_msg(GetEventsForTagsOptions(
        buffer_results=True, buffer_format="1", tag_owner_output=TagOwnerOutput.UNIQUE_ID,
    ))

    resp = asyncio.run(client.send_message(req))

    size = _find_tags(_event_by_key(resp, TARGET_KEY).tags, "size", "a:b=c")
    assert [s.owner_unique_id for s in size] == [OWNER_UID, OWNER_UID]
    assert all(s.owner == "" for s in size)


# ---------------------------------------------------------------------------
# Payload repair and timestamps
# ---------------------------------------------------------------------------

def test_normalize_tag_owner_lines() -> None:
    spec = (
        "_event_tag=E\ttag_freq=1\ttag_value=a=b\ttag_timestamp=1.000001\towner=O1\n"
        "_event_tag=E\ttag_freq=2\ttag_value=c=d\ttag_timestamp=1.000002\towner=O2\n"
    )
    assert normalize_tag_owner_lines(spec) == spec, "documented form must be unchanged"

    server = (
        "_event_id=E\n_event_tag=E\ttag_freq=1\ttag_value=a=b\ttag_timestamp=1.000001\n"
        "\towner=O1_event_tag=E\ttag_freq=2\ttag_value=c=d\ttag_timestamp=1.000002\n\towner=O2\n\n"
    )
    want = (
        "_event_id=E\n_event_tag=E\ttag_freq=1\ttag_value=a=b\ttag_timestamp=1.000001\towner=O1\n"
        "_event_tag=E\ttag_freq=2\ttag_value=c=d\ttag_timestamp=1.000002\towner=O2\n\n"
    )
    assert normalize_tag_owner_lines(server) == want


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("1790266974.325930", datetime.fromtimestamp(1790266974, tz=timezone.utc).replace(microsecond=325930)),
        ("+1790266974.5", datetime.fromtimestamp(1790266974, tz=timezone.utc).replace(microsecond=500000)),
        ("1790266974", datetime.fromtimestamp(1790266974, tz=timezone.utc)),
        ("", None),
        ("abc", None),
    ],
)
def test_parse_posix_timestamp(raw: str, want: datetime | None) -> None:
    assert parse_posix_timestamp(raw) == want


# ---------------------------------------------------------------------------
# Header encoding
# ---------------------------------------------------------------------------

def _get_event_header(opts: GetEventOptions) -> str:
    return _get_event_message_header(Message(
        event=EventFields(id="e1"), neural_memory=NeuralMemoryFields(get_event=opts),
    )) + "\t"


def _events_for_tag_header(opts: GetEventsForTagsOptions) -> str:
    return _get_events_for_tag_message_header(Message(
        neural_memory=NeuralMemoryFields(get_events_for_tags=opts),
    )) + "\t"


def test_get_event_message_header_tag_format() -> None:
    h = _get_event_header(GetEventOptions(get_tags=True))
    assert "tag_format=0\t" in h and "output_tag_owner" not in h
    assert "tag_format=1\t" in _get_event_header(GetEventOptions(get_tags=True, tag_format=1))
    assert "output_tag_owner=Y\t" in _get_event_header(
        GetEventOptions(tag_format=1, tag_owner_output=TagOwnerOutput.EVENT_KEY))
    assert "output_tag_owner=N\t" in _get_event_header(
        GetEventOptions(tag_format=1, tag_owner_output=TagOwnerOutput.UNIQUE_ID))


def test_get_events_for_tag_message_header_tag_owner() -> None:
    h = _events_for_tag_header(GetEventsForTagsOptions(buffer_format="1"))
    assert "buffer_format=1\t" in h and "get_tag_owner" not in h
    assert "get_tag_owner=Y\t" in _events_for_tag_header(
        GetEventsForTagsOptions(buffer_format="1", tag_owner_output=TagOwnerOutput.EVENT_KEY))
    assert "get_tag_owner_unique_id=Y\t" in _events_for_tag_header(
        GetEventsForTagsOptions(buffer_format="1", tag_owner_output=TagOwnerOutput.UNIQUE_ID))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.fixture
def validation_enabled(monkeypatch):
    monkeypatch.setattr(validate_mod, "_validation_enabled", True)


def _get_event_msg(opts: GetEventOptions) -> Message:
    return Message(
        to="test@zeroth.pod-os.com", from_="c@zeroth.pod-os.com", intent=IntentType.GetEvent.name,
        event=EventFields(id="e1"), neural_memory=NeuralMemoryFields(get_event=opts),
    )


def _events_for_tags_msg(opts: GetEventsForTagsOptions) -> Message:
    return Message(
        to="test@zeroth.pod-os.com", from_="c@zeroth.pod-os.com", intent=IntentType.GetEventsForTags.name,
        payload=PayloadFields(data="clause_type:S\tboolean:or\tlow:k=v"),
        neural_memory=NeuralMemoryFields(get_events_for_tags=opts),
    )


def _intent_for(msg: Message):
    return IntentType.GetEvent if msg.intent == IntentType.GetEvent.name else IntentType.GetEventsForTags


@pytest.mark.parametrize(
    ("msg", "want_field", "want_sev"),
    [
        pytest.param(_get_event_msg(GetEventOptions(
            get_tags=True, tag_format=1, tag_owner_output=TagOwnerOutput.EVENT_KEY)), "", "",
            id="valid tag_format=1 with owner"),
        pytest.param(_get_event_msg(GetEventOptions(get_tags=True, tag_format=2)),
                     "neural_memory.get_event.tag_format", "error", id="tag_format=2"),
        pytest.param(_get_event_msg(GetEventOptions(get_tags=True, tag_owner_output=TagOwnerOutput.UNIQUE_ID)),
                     "neural_memory.get_event.tag_owner_output", "error", id="owner without tag_format=1"),
        pytest.param(_get_event_msg(GetEventOptions(get_tags=True, tag_format=1, tag_owner_output="owner")),
                     "neural_memory.get_event.tag_owner_output", "error", id="invalid owner value"),
        pytest.param(_get_event_msg(GetEventOptions(tag_format=1)),
                     "neural_memory.get_event.tag_format", "warn", id="tag_format=1 without get_tags"),
        pytest.param(_events_for_tags_msg(GetEventsForTagsOptions(
            buffer_results=True, buffer_format="1", tag_owner_output=TagOwnerOutput.UNIQUE_ID)), "", "",
            id="valid buffer_format=1 with owner"),
        pytest.param(_events_for_tags_msg(GetEventsForTagsOptions(buffer_results=True, buffer_format="2")),
                     "neural_memory.get_events_for_tags.buffer_format", "error", id="buffer_format=2"),
        pytest.param(_events_for_tags_msg(GetEventsForTagsOptions(
            buffer_results=True, tag_owner_output=TagOwnerOutput.EVENT_KEY)),
            "neural_memory.get_events_for_tags.tag_owner_output", "warn", id="owner without buffer_format=1"),
    ],
)
def test_validate_tag_format(validation_enabled, msg: Message, want_field: str, want_sev: str) -> None:
    errs = validate_message(msg)
    if not want_field:
        assert errs == []
        raw = encode_message(msg, _intent_for(msg), "conv")
        assert validate_raw_message(raw) == []
        return
    matches = [e for e in errs if e.struct_path == want_field and e.severity == want_sev]
    assert matches, f"want {want_sev} on {want_field}, got {errs}"
    assert matches[0].fix and matches[0].example_code


def _reframe_header_length(raw: bytes, delta: int) -> bytes:
    """Grow the total and header length prefixes of an encoded frame by delta."""
    total = int(raw[1:9], 16)
    header = int(raw[28:36], 16)
    return (
        f"x{total + delta:08x}".encode() + raw[9:27]
        + f"x{header + delta:08x}".encode() + raw[36:]
    )


def _inject_header_field(raw: bytes, after: bytes, field: bytes) -> bytes:
    assert after in raw
    injected = raw.replace(after, after + b"\t" + field, 1)
    return _reframe_header_length(injected, len(field) + 1)


def _wire_errors(raw: bytes, wire_field: str, rule: str, severity: str = "error"):
    return [
        e for e in validate_raw_message(raw)
        if e.wire_field == wire_field and e.rule == rule and e.severity == severity
    ]


def test_validate_raw_message_rejects_non_yn_get_tag_owner(validation_enabled) -> None:
    msg = _events_for_tags_msg(GetEventsForTagsOptions(buffer_results=True, buffer_format="1"))
    raw = encode_message(msg, IntentType.GetEventsForTags, "conv")
    raw = _inject_header_field(raw, b"buffer_format=1", b"get_tag_owner=yes")
    errs = _wire_errors(raw, "get_tag_owner", "header_value")
    assert errs, validate_raw_message(raw)
    assert "bare flag" in errs[0].message


def test_validate_raw_message_rejects_bad_buffer_format(validation_enabled) -> None:
    msg = _events_for_tags_msg(GetEventsForTagsOptions(buffer_results=True, buffer_format="1"))
    raw = encode_message(msg, IntentType.GetEventsForTags, "conv").replace(b"buffer_format=1", b"buffer_format=9", 1)
    assert _wire_errors(raw, "buffer_format", "header_value")


def test_validate_raw_message_warns_owner_without_buffer_format_1(validation_enabled) -> None:
    msg = _events_for_tags_msg(GetEventsForTagsOptions(buffer_results=True))
    raw = encode_message(msg, IntentType.GetEventsForTags, "conv")
    raw = _inject_header_field(raw, b"buffer_format=0", b"get_tag_owner_unique_id=Y")
    assert _wire_errors(raw, "get_tag_owner / get_tag_owner_unique_id", "semantic", "warn")


def test_validate_raw_message_get_event_tag_format_headers(validation_enabled) -> None:
    msg = _get_event_msg(GetEventOptions(get_tags=True))
    raw = encode_message(msg, IntentType.GetEvent, "conv")

    bad_tf = raw.replace(b"tag_format=0", b"tag_format=7", 1)
    assert _wire_errors(bad_tf, "tag_format", "header_value")

    bad_owner = _inject_header_field(raw, b"tag_format=0", b"output_tag_owner=yes")
    assert _wire_errors(bad_owner, "output_tag_owner", "header_value")

    owner_tf0 = _inject_header_field(raw, b"tag_format=0", b"output_tag_owner=Y")
    assert _wire_errors(owner_tf0, "output_tag_owner", "semantic", "warn")
