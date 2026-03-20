"""Tests for message validation (validate.py).

Covers:
- Environment gate (enabled / disabled)
- Envelope validation
- Per-intent struct validators (all covered intents)
- Payload validation (batch intents)
- Wire validation (validate_raw_message)
- Format helpers (format_validation_errors, validation_errors_to_llm_json)
"""

import json

import pytest

import pod_os_client.message.validate as validate_mod
from pod_os_client.message.validate import (
    ValidationError,
    format_validation_errors,
    validate_message,
    validate_raw_message,
    validation_errors_to_llm_json,
)
from pod_os_client.message.types import (
    BatchEventSpec,
    BatchLinkEventSpec,
    EventFields,
    GetEventOptions,
    GetEventsForTagsOptions,
    LinkFields,
    Message,
    NeuralMemoryFields,
    PayloadFields,
    ResponseFields,
    Tag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enable_validation(monkeypatch):
    monkeypatch.setattr(validate_mod, "_validation_enabled", True)


def _disable_validation(monkeypatch):
    monkeypatch.setattr(validate_mod, "_validation_enabled", False)


def _valid_envelope(**overrides) -> dict:
    """Return kwargs for a Message with valid envelope fields."""
    defaults = {
        "to": "actor@gateway.example.com",
        "from_": "client@gateway.example.com",
        "intent": "StoreEvent",
    }
    defaults.update(overrides)
    return defaults


def _build_raw_message(
    to: str = "actor@gw",
    from_: str = "client@gw",
    header: str = "",
    message_type: int = 1000,
    data_type: int = 0,
    payload: bytes = b"",
) -> bytes:
    """Build a raw wire-format message for wire validation tests."""
    to_b = to.encode("ascii")
    from_b = from_.encode("ascii")
    header_b = header.encode("ascii")

    payload_len = f"x{len(payload):08x}"
    to_len = f"x{len(to_b):08x}"
    from_len = f"x{len(from_b):08x}"
    header_len = f"x{len(header_b):08x}"
    msg_type = f"{message_type:09d}"
    dt = f"{data_type:09d}"

    total = (
        len(to_b) + 9
        + len(from_b) + 9
        + len(header_b) + 9
        + len(msg_type)
        + len(dt)
        + len(payload) + 9
        + 9
    )
    total_enc = f"x{total:08x}"

    prefix = (
        total_enc + to_len + from_len + header_len
        + msg_type + dt + payload_len
    )
    return prefix.encode("ascii") + to_b + from_b + header_b + payload


def _find_error(errs, *, rule=None, intent=None, struct_path=None, wire_field=None):
    """Find the first error matching the given criteria."""
    for e in errs:
        if rule and e.rule != rule:
            continue
        if intent and e.intent != intent:
            continue
        if struct_path and struct_path not in e.struct_path:
            continue
        if wire_field and wire_field not in e.wire_field:
            continue
        return e
    return None


# ===========================================================================
# ENV GATE
# ===========================================================================

class TestEnvGate:
    def test_disabled_returns_empty(self, monkeypatch):
        _disable_validation(monkeypatch)
        msg = Message(**_valid_envelope())
        assert validate_message(msg) == []

    def test_disabled_raw_returns_empty(self, monkeypatch):
        _disable_validation(monkeypatch)
        assert validate_raw_message(b"bad") == []

    def test_enabled_produces_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(to="", from_="", intent="")
        errs = validate_message(msg)
        assert len(errs) > 0


# ===========================================================================
# ENVELOPE VALIDATION
# ===========================================================================

class TestEnvelope:
    def test_missing_to(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(to=""))
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", struct_path="to")

    def test_invalid_to_format(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(to="no-at-sign"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="format", struct_path="to")

    def test_missing_from(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(from_=""))
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", struct_path="from_")

    def test_invalid_from_format(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(from_="no-at-sign"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="format", struct_path="from_")

    def test_missing_intent(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent=""))
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", struct_path="intent")

    def test_gateway_id_requires_client_name(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="GatewayId", client_name=""))
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="id:name")

    def test_valid_envelope_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(),
            event=EventFields(
                owner="$sys", location="TERRA|0|0", location_separator="|",
            ),
        )
        errs = validate_message(msg)
        envelope_errs = [e for e in errs if "Envelope" in e.struct_path]
        assert envelope_errs == []


# ===========================================================================
# STORE EVENT
# ===========================================================================

class TestStoreEvent:
    def test_nil_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="StoreEvent"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="event")

    def test_missing_owner_and_owner_unique_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreEvent"),
            event=EventFields(location="LOC", location_separator="|"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="owner")

    def test_missing_location(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreEvent"),
            event=EventFields(owner="$sys", location_separator="|"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="loc")

    def test_missing_location_separator(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreEvent"),
            event=EventFields(owner="$sys", location="LOC", location_separator=""),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="loc_delim")

    def test_valid_store_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreEvent"),
            event=EventFields(
                owner="$sys", location="TERRA|0|0", location_separator="|",
            ),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# STORE BATCH EVENTS
# ===========================================================================

class TestStoreBatchEvents:
    def test_empty_batch_events(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="StoreBatchEvents"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="required")

    def test_per_record_missing_fields(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchEvents"),
            neural_memory=NeuralMemoryFields(
                batch_events=[
                    BatchEventSpec(event=EventFields()),
                ],
            ),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="timestamp")
        assert _find_error(errs, rule="one_of_required", wire_field="owner")
        assert _find_error(errs, rule="payload_format", wire_field="loc")

    def test_valid_batch_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchEvents"),
            neural_memory=NeuralMemoryFields(
                batch_events=[
                    BatchEventSpec(
                        event=EventFields(
                            owner="$sys",
                            timestamp="+123.456",
                            location="LOC",
                            location_separator="|",
                        ),
                    ),
                ],
            ),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# STORE BATCH TAGS
# ===========================================================================

class TestStoreBatchTags:
    def test_nil_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="StoreBatchTags"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="event")

    def test_missing_event_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchTags"),
            event=EventFields(owner="$sys"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="event_id")

    def test_missing_owner(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchTags"),
            event=EventFields(id="evt-1"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="owner")

    def test_empty_tags(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchTags"),
            event=EventFields(id="evt-1", owner="$sys"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", struct_path="neural_memory.tags")

    def test_tag_missing_key(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchTags"),
            event=EventFields(id="evt-1", owner="$sys"),
            neural_memory=NeuralMemoryFields(tags=[Tag(key="", value="v")]),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="payload_format", wire_field="key")

    def test_tag_none_value(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchTags"),
            event=EventFields(id="evt-1", owner="$sys"),
            neural_memory=NeuralMemoryFields(tags=[Tag(key="k", value=None)]),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="payload_format", wire_field="value")

    def test_valid_batch_tags(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchTags"),
            event=EventFields(id="evt-1", owner="$sys"),
            neural_memory=NeuralMemoryFields(tags=[Tag(key="k", value="v")]),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# GET EVENT
# ===========================================================================

class TestGetEvent:
    def test_nil_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="GetEvent"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="event")

    def test_missing_id_and_unique_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GetEvent"),
            event=EventFields(),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="event_id")

    def test_valid_with_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GetEvent"),
            event=EventFields(id="evt-1"),
        )
        errs = validate_message(msg)
        assert errs == []

    def test_valid_with_unique_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GetEvent"),
            event=EventFields(unique_id="u-1"),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# GET EVENTS FOR TAGS
# ===========================================================================

class TestGetEventsForTags:
    def test_nil_neural_memory(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="GetEventsForTags"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="neural_memory")

    def test_nil_get_events_for_tags(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GetEventsForTags"),
            neural_memory=NeuralMemoryFields(),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="get_events_for_tags")

    def test_valid(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GetEventsForTags"),
            neural_memory=NeuralMemoryFields(
                get_events_for_tags=GetEventsForTagsOptions(buffer_results=True),
            ),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# LINK EVENT
# ===========================================================================

class TestLinkEvent:
    def _valid_link_msg(self, **link_overrides) -> Message:
        link_defaults = {
            "event_a": "a", "event_b": "b",
            "category": "related", "strength_a": 1.0, "strength_b": 1.0,
            "timestamp": "+123.456",
            "owner_event_id": "owner-1",
            "location": "TERRA|0|0", "location_separator": "|",
        }
        link_defaults.update(link_overrides)
        return Message(
            **_valid_envelope(intent="LinkEvent"),
            neural_memory=NeuralMemoryFields(link=LinkFields(**link_defaults)),
        )

    def test_nil_neural_memory(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="LinkEvent"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="neural_memory")

    def test_nil_link(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="LinkEvent"),
            neural_memory=NeuralMemoryFields(),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="neural_memory.link")

    def test_missing_event_pairs(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(event_a="", event_b="")
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="event_id_a")

    def test_unique_id_pair_accepted(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(
            event_a="", event_b="",
            unique_id_a="ua", unique_id_b="ub",
        )
        errs = validate_message(msg)
        assert not _find_error(errs, rule="one_of_required", wire_field="event_id_a")

    def test_missing_category(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(category="")
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="category")

    def test_zero_strength_a(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(strength_a=0)
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="strength_a")

    def test_zero_strength_b(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(strength_b=0)
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="strength_b")

    def test_missing_timestamp(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(timestamp="")
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="timestamp")

    def test_missing_owner(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(owner_event_id="", owner_unique_id="")
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="owner_event_id")

    def test_missing_location(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(location="")
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="loc")

    def test_missing_location_separator(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg(location_separator="")
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="loc_delim")

    def test_valid_link_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = self._valid_link_msg()
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# UNLINK EVENT
# ===========================================================================

class TestUnlinkEvent:
    def test_nil_neural_memory(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="UnlinkEvent"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="neural_memory")

    def test_nil_link(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="UnlinkEvent"),
            neural_memory=NeuralMemoryFields(),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="neural_memory.link")

    def test_missing_id_and_unique_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="UnlinkEvent"),
            neural_memory=NeuralMemoryFields(link=LinkFields()),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="one_of_required", wire_field="event_id")

    def test_location_without_separator(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="UnlinkEvent"),
            neural_memory=NeuralMemoryFields(
                link=LinkFields(id="lnk-1", location="LOC", location_separator=""),
            ),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="loc_delim")

    def test_valid_unlink(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="UnlinkEvent"),
            neural_memory=NeuralMemoryFields(link=LinkFields(id="lnk-1")),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# STORE BATCH LINKS
# ===========================================================================

class TestStoreBatchLinks:
    def test_nil_neural_memory(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="StoreBatchLinks"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="neural_memory")

    def test_empty_batch_links(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchLinks"),
            neural_memory=NeuralMemoryFields(),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", struct_path="batch_links")

    def test_per_record_missing_fields(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchLinks"),
            neural_memory=NeuralMemoryFields(
                batch_links=[
                    BatchLinkEventSpec(event=EventFields(), link=LinkFields()),
                ],
            ),
        )
        errs = validate_message(msg)
        assert _find_error(errs, struct_path="event.timestamp")
        assert _find_error(errs, struct_path="link.timestamp")
        assert _find_error(errs, wire_field="event_id_a")
        assert _find_error(errs, wire_field="category")
        assert _find_error(errs, wire_field="strength_a")
        assert _find_error(errs, wire_field="owner_event_id")

    def test_valid_batch_link(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreBatchLinks"),
            neural_memory=NeuralMemoryFields(
                batch_links=[
                    BatchLinkEventSpec(
                        event=EventFields(
                            owner="$sys", timestamp="+1.0",
                        ),
                        link=LinkFields(
                            event_a="a", event_b="b",
                            category="rel", strength_a=1.0, strength_b=1.0,
                            timestamp="+1.0", owner_event_id="o",
                        ),
                    ),
                ],
            ),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# GATEWAY / ACTOR VALIDATORS
# ===========================================================================

class TestGatewayId:
    def test_missing_client_name(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="GatewayId"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="id:name")

    def test_passcode_without_user_name(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GatewayId"),
            client_name="c", passcode="pass",
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="id:user")

    def test_user_name_without_passcode(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GatewayId"),
            client_name="c", user_name="admin",
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="id:passcode")

    def test_valid_gateway_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="GatewayId"),
            client_name="myClient",
        )
        errs = validate_message(msg)
        assert errs == []


class TestGatewayStream:
    def test_stream_on_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="GatewayStreamOn"))
        errs = validate_message(msg)
        assert errs == []

    def test_stream_off_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="GatewayStreamOff"))
        errs = validate_message(msg)
        assert errs == []


class TestActorRequest:
    def test_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="ActorRequest"))
        errs = validate_message(msg)
        assert errs == []


class TestActorResponse:
    def test_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="ActorResponse"))
        errs = validate_message(msg)
        assert errs == []


class TestActorReport:
    def test_nil_response(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="ActorReport"))
        errs = validate_message(msg)
        assert _find_error(errs, rule="nil_struct", struct_path="response")

    def test_missing_status(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="ActorReport"),
            response=ResponseFields(message="ok"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="_status")

    def test_missing_message(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="ActorReport"),
            response=ResponseFields(status="OK"),
        )
        errs = validate_message(msg)
        assert _find_error(errs, rule="required", wire_field="_msg")

    def test_valid(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="ActorReport"),
            response=ResponseFields(status="OK", message="healthy"),
        )
        errs = validate_message(msg)
        assert errs == []


class TestStatus:
    def test_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent="Status"))
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# RESPONSE INTENTS
# ===========================================================================

class TestResponseIntents:
    @pytest.mark.parametrize("intent_name", [
        "StoreEventResponse",
        "StoreBatchEventsResponse",
        "StoreBatchTagsResponse",
        "GetEventResponse",
        "GetEventsForTagsResponse",
        "LinkEventResponse",
        "UnlinkEventResponse",
        "StoreBatchLinksResponse",
    ])
    def test_nil_response_warns(self, monkeypatch, intent_name):
        _enable_validation(monkeypatch)
        msg = Message(**_valid_envelope(intent=intent_name))
        errs = validate_message(msg)
        e = _find_error(errs, rule="nil_struct", struct_path="response")
        assert e is not None
        assert e.severity == "warn"

    @pytest.mark.parametrize("intent_name", [
        "StoreEventResponse",
        "GetEventResponse",
        "LinkEventResponse",
    ])
    def test_missing_status_warns(self, monkeypatch, intent_name):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent=intent_name),
            response=ResponseFields(),
        )
        errs = validate_message(msg)
        e = _find_error(errs, rule="required", wire_field="_status")
        assert e is not None
        assert e.severity == "warn"

    def test_valid_response(self, monkeypatch):
        _enable_validation(monkeypatch)
        msg = Message(
            **_valid_envelope(intent="StoreEventResponse"),
            response=ResponseFields(status="OK"),
        )
        errs = validate_message(msg)
        assert errs == []


# ===========================================================================
# WIRE VALIDATION — validate_raw_message
# ===========================================================================

class TestWireValidation:
    def test_nil_raw(self, monkeypatch):
        _enable_validation(monkeypatch)
        errs = validate_raw_message(None)
        assert _find_error(errs, rule="nil_struct")

    def test_too_short(self, monkeypatch):
        _enable_validation(monkeypatch)
        errs = validate_raw_message(b"x" * 10)
        assert _find_error(errs, rule="format")

    def test_too_long(self, monkeypatch):
        from pod_os_client.message.constants import MAX_MESSAGE_SIZE
        _enable_validation(monkeypatch)
        errs = validate_raw_message(b"x" * (MAX_MESSAGE_SIZE + 1))
        assert _find_error(errs, rule="format")

    def test_invalid_length_field(self, monkeypatch):
        _enable_validation(monkeypatch)
        bad = b"XXXXXXXXX" + b"x00000000" * 6 + b"a@b" * 2
        errs = validate_raw_message(bad)
        assert _find_error(errs, rule="format")

    def test_bad_to_format(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(to="no-at", from_="c@g", header="_db_cmd=store")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="format", struct_path="to")

    def test_bad_from_format(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(to="a@g", from_="no-at", header="_db_cmd=store")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="format", struct_path="from")

    def test_unknown_message_type(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=999999)
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="format", struct_path="messageType")

    def test_valid_gateway_stream_on(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=10, header="")
        errs = validate_raw_message(raw)
        assert errs == []


class TestWireNeuralMemoryRequest:
    def test_missing_db_cmd(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=1000, header="foo=bar")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="_db_cmd")

    def test_unknown_db_cmd(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=bogus")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_value", wire_field="_db_cmd")

    def test_store_missing_timestamp_warns(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=store\tloc=X")
        errs = validate_raw_message(raw)
        e = _find_error(errs, wire_field="timestamp")
        assert e is not None
        assert e.severity == "warn"

    def test_store_batch_empty_payload(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=store_batch")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="required", struct_path="batch_events")

    def test_tag_store_batch_missing_event_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=tag_store_batch\towner=x")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="event_id")

    def test_tag_store_batch_missing_owner(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=tag_store_batch\tevent_id=x")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="owner")

    def test_get_missing_event_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=get")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="event_id")

    def test_events_for_tag_missing_buffer_results(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=events_for_tag")
        errs = validate_raw_message(raw)
        e = _find_error(errs, wire_field="buffer_results")
        assert e is not None
        assert e.severity == "warn"

    def test_link_missing_fields(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=link")
        errs = validate_raw_message(raw)
        assert _find_error(errs, wire_field="strength_a")
        assert _find_error(errs, wire_field="strength_b")
        assert _find_error(errs, wire_field="category")
        assert _find_error(errs, wire_field="timestamp")
        assert _find_error(errs, wire_field="owner_event_id")
        assert _find_error(errs, wire_field="event_id_a")

    def test_link_valid(self, monkeypatch):
        _enable_validation(monkeypatch)
        hdr = "\t".join([
            "_db_cmd=link",
            "event_id_a=a", "event_id_b=b",
            "strength_a=1.0", "strength_b=1.0",
            "category=related", "timestamp=+1.0",
            "owner_event_id=o",
        ])
        raw = _build_raw_message(header=hdr)
        errs = validate_raw_message(raw)
        assert errs == []

    def test_unlink_missing_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=unlink")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="event_id")

    def test_link_batch_empty_payload(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(header="_db_cmd=link_batch")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="required", struct_path="batch_links")


class TestWireNonNeuralMemory:
    def test_gateway_id_missing_name(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=5, header="foo=bar")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="id:name")

    def test_actor_echo_missing_msg_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=2, header="")
        errs = validate_raw_message(raw)
        e = _find_error(errs, wire_field="_msg_id")
        assert e is not None
        assert e.severity == "warn"

    def test_actor_request_missing_type(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=4, header="")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="_type")

    def test_actor_request_wrong_type(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=4, header="_type=wrong")
        errs = validate_raw_message(raw)
        assert _find_error(errs, rule="header_missing", wire_field="_type")

    def test_status_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=3, header="")
        errs = validate_raw_message(raw)
        assert errs == []

    def test_actor_report_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=19, header="")
        errs = validate_raw_message(raw)
        assert errs == []

    def test_actor_response_no_errors(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=30, header="")
        errs = validate_raw_message(raw)
        assert errs == []


class TestWireNeuralMemoryResponse:
    def test_missing_status_warns(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(message_type=1001, header="_type=store")
        errs = validate_raw_message(raw)
        e = _find_error(errs, wire_field="_status")
        assert e is not None
        assert e.severity == "warn"

    def test_get_response_missing_event_id(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(
            message_type=1001,
            header="_type=get\t_status=OK",
        )
        errs = validate_raw_message(raw)
        assert _find_error(errs, wire_field="_event_id")

    def test_link_response_missing_link_event(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(
            message_type=1001,
            header="_type=link\t_status=OK",
        )
        errs = validate_raw_message(raw)
        assert _find_error(errs, wire_field="link_event")

    def test_store_response_missing_count(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(
            message_type=1001,
            header="_type=store\t_status=OK",
        )
        errs = validate_raw_message(raw)
        assert _find_error(errs, wire_field="_count")

    def test_link_batch_response_missing_links_ok(self, monkeypatch):
        _enable_validation(monkeypatch)
        raw = _build_raw_message(
            message_type=1001,
            header="_type=link_batch\t_status=OK",
        )
        errs = validate_raw_message(raw)
        assert _find_error(errs, wire_field="_links_ok")


# ===========================================================================
# FORMAT HELPERS
# ===========================================================================

class TestFormatHelpers:
    def test_format_empty(self):
        assert format_validation_errors([]) == ""

    def test_format_error(self):
        errs = [ValidationError(
            severity="error", intent="StoreEvent",
            struct_path="event.location", wire_field="loc",
            rule="required",
            message="Location is required.",
            fix="Set event.location.",
            example_code='msg.event.location = "TERRA"',
        )]
        out = format_validation_errors(errs)
        assert "[ERROR]" in out
        assert "StoreEvent" in out
        assert "loc" in out
        assert "Fix:" in out

    def test_format_warn(self):
        errs = [ValidationError(severity="warn", intent="wire", rule="uncovered")]
        out = format_validation_errors(errs)
        assert "[WARN]" in out

    def test_llm_json_empty(self):
        assert validation_errors_to_llm_json([]) == "[]"

    def test_llm_json_structure(self):
        errs = [ValidationError(
            severity="error", intent="LinkEvent",
            struct_path="neural_memory.link.category", wire_field="category",
            rule="required", message="Missing.", fix="Set it.",
            example_code="x=1", references=["types.py:LinkFields"],
        )]
        raw = validation_errors_to_llm_json(errs)
        data = json.loads(raw)
        assert isinstance(data, list)
        assert len(data) == 1
        obj = data[0]
        assert obj["severity"] == "error"
        assert obj["intent"] == "LinkEvent"
        assert obj["struct_path"] == "neural_memory.link.category"
        assert obj["wire_field"] == "category"
        assert obj["rule"] == "required"
        assert obj["references"] == ["types.py:LinkFields"]
