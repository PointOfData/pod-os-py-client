"""Pod-OS message validation capability.

Validation is enabled via the PODOS_VALIDATE environment variable.
Accepted values: "1", "true", "yes" (case-insensitive).
Anything else disables validation.

Both Message.validate() and validate_raw_message() return an empty list
immediately when validation is disabled, making the hot path a single bool
check with zero overhead.
"""

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pod_os_client.message.constants import MAX_MESSAGE_SIZE

if TYPE_CHECKING:
    from pod_os_client.message.types import Message

__all__ = [
    "ValidationError",
    "ValidationErrors",
    "validate_raw_message",
    "explain_validation_errors",
]

# =============================================================================
# VALIDATION ENABLED FLAG — set once at module import from env var
# =============================================================================

_v = os.environ.get("PODOS_VALIDATE", "").lower().strip()
_validation_enabled: bool = _v in ("1", "true", "yes")


# =============================================================================
# ERROR TYPES — dual-audience (engineer + LLM)
# =============================================================================

@dataclass
class ValidationError:
    """Represents a single validation violation.

    Designed for two audiences:
    - Engineers: via format_validation_errors() (terminal-friendly)
    - LLMs: via validation_errors_to_llm_json() (structured JSON for prompt injection)
    """

    severity: str = ""      # "error" or "warn"
    intent: str = ""        # Intent name, e.g. "LinkEvent"
    struct_path: str = ""   # Python struct dot-path: "neural_memory.link.category"
    wire_field: str = ""    # Wire protocol key: "category"
    rule: str = ""          # "required", "one_of_required", "format", "nil_struct",
                            #  "header_missing", "header_value", "payload_type",
                            #  "payload_format", "uncovered"
    message: str = ""       # Human-readable description of what is wrong
    fix: str = ""           # Concrete remediation step in plain English
    example_code: str = ""  # Minimal Python snippet showing a correct value
    references: list[str] = field(default_factory=list)  # Source locations


ValidationErrors = list[ValidationError]


def format_validation_errors(errs: ValidationErrors) -> str:
    """Return a terminal-friendly, engineer-readable multiline string.

    Empty list produces "".
    """
    if not errs:
        return ""
    parts = []
    for ve in errs:
        prefix = "[ERROR]" if ve.severity.lower() != "warn" else "[WARN]"
        wire_info = f" ({ve.wire_field})" if ve.wire_field else ""
        field_info = ve.struct_path if ve.struct_path else ve.intent
        parts.append(f"{prefix} {ve.intent} / {field_info}{wire_info}: {ve.rule}")
        if ve.message:
            parts.append(f"  What: {ve.message}")
        if ve.fix:
            parts.append(f"  Fix:  {ve.fix}")
        if ve.example_code:
            parts.append(f"  Code: {ve.example_code}")
    return "\n".join(parts)


def validation_errors_to_llm_json(errs: ValidationErrors) -> str:
    """Return a JSON array of validation errors suitable for injection into an LLM prompt.

    Empty list produces "[]".
    """
    items = []
    for ve in errs:
        items.append({
            "severity": ve.severity,
            "intent": ve.intent,
            "struct_path": ve.struct_path,
            "wire_field": ve.wire_field,
            "rule": ve.rule,
            "description": ve.message,
            "fix": ve.fix,
            "example_code": ve.example_code,
            "references": ve.references or [],
        })
    return json.dumps(items, indent=2)


# =============================================================================
# HELPERS — shared field check utilities
# =============================================================================

def _errorf(severity: str, intent: str, struct_path: str, wire_field: str,
            rule: str, msg: str, fix: str, code: str,
            *refs: str) -> ValidationError:
    return ValidationError(
        severity=severity,
        intent=intent,
        struct_path=struct_path,
        wire_field=wire_field,
        rule=rule,
        message=msg,
        fix=fix,
        example_code=code,
        references=list(refs),
    )


def _required_field(intent: str, struct_path: str, wire_field: str,
                    fix: str, code: str, *refs: str) -> ValidationError:
    return _errorf(
        "error", intent, struct_path, wire_field, "required",
        f"{struct_path} ({wire_field}) is required for {intent} and is missing.",
        fix, code, *refs,
    )


def _nil_struct(intent: str, struct_path: str, fix: str, code: str,
                *refs: str) -> ValidationError:
    return _errorf(
        "error", intent, struct_path, "", "nil_struct",
        f"{struct_path} must be initialized for intent {intent}.",
        fix, code, *refs,
    )


def _one_of_required(intent: str, field_a: str, wire_a: str,
                     field_b: str, wire_b: str,
                     fix: str, code: str, *refs: str) -> ValidationError:
    return _errorf(
        "error", intent,
        f"{field_a} / {field_b}",
        f"{wire_a} / {wire_b}",
        "one_of_required",
        f"One of {field_a} ({wire_a}) or {field_b} ({wire_b}) is required for {intent}.",
        fix, code, *refs,
    )


def _warn_uncovered(intent: str, msg: str) -> ValidationError:
    return _errorf(
        "warn", intent, "", "", "uncovered", msg,
        "This case is currently unsupported. Monitor release notes for support updates.",
        "", "",
    )


def _is_name_at_gateway(s: str) -> bool:
    """Check that s contains exactly one '@' and neither part is empty."""
    idx = s.find("@")
    return 0 < idx < len(s) - 1


# =============================================================================
# VALIDATE — struct-level validation on Message objects
# =============================================================================

def validate_message(msg: "Message") -> ValidationErrors:
    """Validate a Message against the rules for its Intent.

    Returns an empty list immediately if validation is disabled (PODOS_VALIDATE not set).
    Otherwise returns all violations collected across envelope + intent + payload.

    This function is called as msg.validate() via monkey-patching in __init__.
    """
    if not _validation_enabled:
        return []

    errs: ValidationErrors = []
    errs.extend(_validate_envelope(msg))

    intent_name = msg.intent
    if intent_name and intent_name in _intent_validators:
        errs.extend(_intent_validators[intent_name](msg))

    return errs


# =============================================================================
# ENVELOPE VALIDATOR
# =============================================================================

def _validate_envelope(msg: "Message") -> ValidationErrors:
    errs: ValidationErrors = []
    intent = msg.intent or "(unknown)"

    if not msg.to:
        errs.append(_required_field(
            intent, "Envelope.to", "to",
            'Set Envelope.to to the recipient address in name@gateway format.',
            'msg.to = "actor@gateway.example.com"',
            "message/types.py:Envelope.to",
        ))
    elif not _is_name_at_gateway(msg.to):
        errs.append(_errorf(
            "error", intent, "Envelope.to", "to", "format",
            "Envelope.to must be in name@gateway format.",
            "Set to to a string containing exactly one '@' with non-empty name and gateway parts.",
            'msg.to = "actor@gateway.example.com"',
            "message/types.py:Envelope.to",
        ))

    if not msg.from_:
        errs.append(_required_field(
            intent, "Envelope.from_", "from",
            'Set Envelope.from_ to the sender address in name@gateway format.',
            'msg.from_ = "client@gateway.example.com"',
            "message/types.py:Envelope.from_",
        ))
    elif not _is_name_at_gateway(msg.from_):
        errs.append(_errorf(
            "error", intent, "Envelope.from_", "from", "format",
            "Envelope.from_ must be in name@gateway format.",
            "Set from_ to a string containing exactly one '@' with non-empty name and gateway parts.",
            'msg.from_ = "client@gateway.example.com"',
            "message/types.py:Envelope.from_",
        ))

    if not msg.intent:
        errs.append(_required_field(
            "(unknown)", "Envelope.intent", "intent",
            "Set Envelope.intent to a value from IntentType (e.g. IntentType.StoreEvent).",
            "msg.intent = IntentType.StoreEvent.name",
            "message/intents.py:IntentType",
        ))

    # GatewayId requires client_name
    if msg.intent == "GatewayId" and not msg.client_name:
        errs.append(_required_field(
            intent, "Envelope.client_name", "id:name",
            "Set Envelope.client_name to the unique name for this client connection.",
            'msg.client_name = "MyClient"',
            "message/types.py:Envelope.client_name",
        ))

    return errs


# =============================================================================
# NEURAL MEMORY REQUEST VALIDATORS
# =============================================================================

def _validate_store_event(msg: "Message") -> ValidationErrors:
    intent = "StoreEvent"
    errs: ValidationErrors = []

    if msg.event is None:
        errs.append(_nil_struct(
            intent, "event",
            "Initialize event before building a StoreEvent message.",
            'msg.event = EventFields(owner="owner-id", location="TERRA|47.6|-122.5", location_separator="|")',
            "message/types.py:EventFields", "message/header.py:_store_event_message_header",
        ))
        return errs

    if not msg.event.owner and not msg.event.owner_unique_id:
        errs.append(_one_of_required(
            intent,
            "event.owner", "owner",
            "event.owner_unique_id", "owner_unique_id",
            'Set event.owner or event.owner_unique_id to identify the owning entity.',
            'msg.event.owner = "$sys"',
            "message/types.py:EventFields.owner", "message/header.py:_store_event_message_header",
        ))

    if not msg.event.location:
        errs.append(_required_field(
            intent, "event.location", "loc",
            'Set event.location to a location string (e.g. TERRA|47.6|-122.5).',
            'msg.event.location = "TERRA|47.6|-122.5"',
            "message/types.py:EventFields.location", "message/header.py:_store_event_message_header",
        ))

    if not msg.event.location_separator:
        errs.append(_required_field(
            intent, "event.location_separator", "loc_delim",
            "Set event.location_separator to the delimiter used in event.location.",
            'msg.event.location_separator = "|"',
            "message/types.py:EventFields.location_separator",
        ))

    return errs


def _validate_store_batch_events(msg: "Message") -> ValidationErrors:
    return _validate_payload(msg)


def _validate_store_batch_tags(msg: "Message") -> ValidationErrors:
    intent = "StoreBatchTags"
    errs: ValidationErrors = []

    if msg.event is None:
        errs.append(_nil_struct(
            intent, "event",
            "Initialize event with the id or unique_id of the target event.",
            'msg.event = EventFields(id="event-id")',
            "message/types.py:EventFields",
        ))
    else:
        if not msg.event.id and not msg.event.unique_id:
            errs.append(_one_of_required(
                intent,
                "event.id", "event_id",
                "event.unique_id", "unique_id",
                "Set event.id or event.unique_id to identify the target event.",
                'msg.event.id = "2024.01.15..."',
                "message/types.py:EventFields",
            ))
        if not msg.event.owner and not msg.event.owner_unique_id:
            errs.append(_one_of_required(
                intent,
                "event.owner", "owner",
                "event.owner_unique_id", "owner_unique_id",
                'Set event.owner or event.owner_unique_id to identify the owning entity.',
                'msg.event.owner = "$sys"',
                "message/types.py:EventFields.owner",
            ))

    errs.extend(_validate_payload(msg))
    return errs


def _validate_get_event(msg: "Message") -> ValidationErrors:
    intent = "GetEvent"
    errs: ValidationErrors = []

    if msg.event is None:
        errs.append(_nil_struct(
            intent, "event",
            "Initialize event with the id or unique_id of the event to retrieve.",
            'msg.event = EventFields(id="2024.01.15...")',
            "message/types.py:EventFields",
        ))
        return errs

    if not msg.event.id and not msg.event.unique_id:
        errs.append(_one_of_required(
            intent,
            "event.id", "event_id",
            "event.unique_id", "unique_id",
            "Set event.id or event.unique_id to identify the event to retrieve.",
            'msg.event.id = "2024.01.15..."',
            "message/types.py:EventFields", "message/header.py:_get_event_message_header",
        ))

    return errs


def _validate_get_events_for_tags(msg: "Message") -> ValidationErrors:
    intent = "GetEventsForTags"
    errs: ValidationErrors = []

    if msg.neural_memory is None:
        errs.append(_nil_struct(
            intent, "neural_memory",
            "Initialize neural_memory with get_events_for_tags options.",
            "msg.neural_memory = NeuralMemoryFields(get_events_for_tags=GetEventsForTagsOptions(buffer_results=True))",
            "message/types.py:NeuralMemoryFields",
        ))
        return errs

    if msg.neural_memory.get_events_for_tags is None:
        errs.append(_nil_struct(
            intent, "neural_memory.get_events_for_tags",
            "Initialize neural_memory.get_events_for_tags with search options.",
            'msg.neural_memory.get_events_for_tags = GetEventsForTagsOptions(event_pattern="my-key=my-value", buffer_results=True)',
            "message/types.py:GetEventsForTagsOptions",
        ))

    return errs


def _validate_link_event(msg: "Message") -> ValidationErrors:
    intent = "LinkEvent"
    errs: ValidationErrors = []

    if msg.neural_memory is None:
        errs.append(_nil_struct(
            intent, "neural_memory",
            "Initialize neural_memory with a link struct.",
            "msg.neural_memory = NeuralMemoryFields(link=LinkFields(...))",
            "message/types.py:NeuralMemoryFields",
        ))
        return errs

    lk = msg.neural_memory.link
    if lk is None:
        errs.append(_nil_struct(
            intent, "neural_memory.link",
            "Initialize neural_memory.link with the link definition.",
            "msg.neural_memory.link = LinkFields(event_a='...', event_b='...', category='related', strength_a=1.0, strength_b=1.0)",
            "message/types.py:LinkFields", "message/header.py:_link_events_message_header",
        ))
        return errs

    has_id_pair = bool(lk.event_a and lk.event_b)
    has_unique_id_pair = bool(lk.unique_id_a and lk.unique_id_b)
    if not has_id_pair and not has_unique_id_pair:
        errs.append(_errorf(
            "error", intent,
            "neural_memory.link.event_a+event_b / neural_memory.link.unique_id_a+unique_id_b",
            "event_id_a+event_id_b / unique_id_a+unique_id_b",
            "one_of_required",
            "Either (event_a AND event_b) or (unique_id_a AND unique_id_b) must be set on neural_memory.link.",
            "Set both event_a and event_b, or both unique_id_a and unique_id_b.",
            'msg.neural_memory.link.event_a = "a-id"\nmsg.neural_memory.link.event_b = "b-id"',
            "message/types.py:LinkFields", "message/header.py:_link_events_message_header",
        ))

    if not lk.category:
        errs.append(_required_field(
            intent, "neural_memory.link.category", "category",
            "Set neural_memory.link.category to a non-empty relationship string.",
            'msg.neural_memory.link.category = "related"',
            "message/types.py:LinkFields.category", "message/header.py:_link_events_message_header",
        ))

    if lk.strength_a == 0:
        errs.append(_required_field(
            intent, "neural_memory.link.strength_a", "strength_a",
            "Set neural_memory.link.strength_a to the A→B link strength (e.g. 1.0).",
            "msg.neural_memory.link.strength_a = 1.0",
            "message/types.py:LinkFields.strength_a",
        ))

    if lk.strength_b == 0:
        errs.append(_required_field(
            intent, "neural_memory.link.strength_b", "strength_b",
            "Set neural_memory.link.strength_b to the B→A link strength (e.g. 1.0).",
            "msg.neural_memory.link.strength_b = 1.0",
            "message/types.py:LinkFields.strength_b",
        ))

    if not lk.timestamp:
        errs.append(_required_field(
            intent, "neural_memory.link.timestamp", "timestamp",
            "Set neural_memory.link.timestamp to the link creation time (POSIX microseconds string).",
            'msg.neural_memory.link.timestamp = "+1234567890.123456"',
            "message/types.py:LinkFields.timestamp", "message/header.py:_link_events_message_header",
        ))

    if not lk.owner_event_id and not lk.owner_unique_id:
        errs.append(_one_of_required(
            intent,
            "neural_memory.link.owner_event_id", "owner_event_id",
            "neural_memory.link.owner_unique_id", "owner_unique_id",
            "Set neural_memory.link.owner_event_id or neural_memory.link.owner_unique_id.",
            'msg.neural_memory.link.owner_event_id = "owner-event-id"',
            "message/types.py:LinkFields.owner_event_id",
        ))

    if not lk.location:
        errs.append(_required_field(
            intent, "neural_memory.link.location", "loc",
            "Set neural_memory.link.location to a location string.",
            'msg.neural_memory.link.location = "TERRA|47.6|-122.5"',
            "message/types.py:LinkFields.location", "message/header.py:_link_events_message_header",
        ))

    if not lk.location_separator:
        errs.append(_required_field(
            intent, "neural_memory.link.location_separator", "loc_delim",
            "Set neural_memory.link.location_separator to the delimiter used in location.",
            'msg.neural_memory.link.location_separator = "|"',
            "message/types.py:LinkFields.location_separator",
        ))

    return errs


def _validate_unlink_event(msg: "Message") -> ValidationErrors:
    intent = "UnlinkEvent"
    errs: ValidationErrors = []

    if msg.neural_memory is None:
        errs.append(_nil_struct(
            intent, "neural_memory",
            "Initialize neural_memory with a link struct.",
            'msg.neural_memory = NeuralMemoryFields(link=LinkFields(id="link-event-id"))',
            "message/types.py:NeuralMemoryFields",
        ))
        return errs

    lk = msg.neural_memory.link
    if lk is None:
        errs.append(_nil_struct(
            intent, "neural_memory.link",
            "Initialize neural_memory.link with the id or unique_id of the link to remove.",
            'msg.neural_memory.link = LinkFields(id="link-event-id")',
            "message/types.py:LinkFields", "message/header.py:_unlink_events_message_header",
        ))
        return errs

    if not lk.id and not lk.unique_id:
        errs.append(_one_of_required(
            intent,
            "neural_memory.link.id", "event_id",
            "neural_memory.link.unique_id", "unique_id",
            "Set neural_memory.link.id or neural_memory.link.unique_id to identify the link event object.",
            'msg.neural_memory.link.id = "link-event-id"',
            "message/types.py:LinkFields", "message/header.py:_unlink_events_message_header",
        ))

    # location_separator required when location is set
    if lk.location and not lk.location_separator:
        errs.append(_required_field(
            intent, "neural_memory.link.location_separator", "loc_delim",
            "Set neural_memory.link.location_separator when location is provided.",
            'msg.neural_memory.link.location_separator = "|"',
            "message/types.py:LinkFields.location_separator",
        ))

    return errs


def _validate_store_batch_links(msg: "Message") -> ValidationErrors:
    intent = "StoreBatchLinks"
    errs: ValidationErrors = []

    if msg.neural_memory is None:
        errs.append(_nil_struct(
            intent, "neural_memory",
            "Initialize neural_memory with batch_links slice.",
            "msg.neural_memory = NeuralMemoryFields(batch_links=[BatchLinkEventSpec(...)])",
            "message/types.py:NeuralMemoryFields",
        ))
        return errs

    errs.extend(_validate_payload(msg))
    return errs


# =============================================================================
# GATEWAY / ACTOR VALIDATORS
# =============================================================================

def _validate_gateway_id(msg: "Message") -> ValidationErrors:
    intent = "GatewayId"
    errs: ValidationErrors = []

    if not msg.client_name:
        errs.append(_required_field(
            intent, "Envelope.client_name", "id:name",
            "Set Envelope.client_name to the unique name for this client connection.",
            'msg.client_name = "MyClient"',
            "message/types.py:Envelope.client_name",
        ))

    # Passcode requires user_name and vice versa
    if msg.passcode and not msg.user_name:
        errs.append(_required_field(
            intent, "Envelope.user_name", "id:user",
            "Set Envelope.user_name when passcode is provided.",
            'msg.user_name = "admin"',
            "message/types.py:Envelope.user_name",
        ))

    if msg.user_name and not msg.passcode:
        errs.append(_required_field(
            intent, "Envelope.passcode", "id:passcode",
            "Set Envelope.passcode when user_name is provided.",
            'msg.passcode = "secret"',
            "message/types.py:Envelope.passcode",
        ))

    return errs


def _validate_gateway_stream(_msg: "Message") -> ValidationErrors:
    # GatewayStreamOn / GatewayStreamOff: only envelope fields are required
    return []


def _validate_actor_request(_msg: "Message") -> ValidationErrors:
    # ActorRequest: _type=status is always written by the encoder; no struct fields beyond envelope
    return []


def _validate_actor_response(_msg: "Message") -> ValidationErrors:
    # ActorResponse: response payload; no required struct fields beyond envelope
    return []


def _validate_actor_report(msg: "Message") -> ValidationErrors:
    intent = "ActorReport"
    errs: ValidationErrors = []

    if msg.response is None:
        errs.append(_nil_struct(
            intent, "response",
            "Initialize response with status and message for an ActorReport.",
            'msg.response = ResponseFields(status="OK", message="...")',
            "message/types.py:ResponseFields",
        ))
        return errs

    if not msg.response.status:
        errs.append(_required_field(
            intent, "response.status", "_status",
            "Set response.status to indicate actor health (e.g. 'OK').",
            'msg.response.status = "OK"',
            "message/types.py:ResponseFields.status",
        ))

    if not msg.response.message:
        errs.append(_required_field(
            intent, "response.message", "_msg",
            "Set response.message to a descriptive status string.",
            'msg.response.message = "actor is healthy"',
            "message/types.py:ResponseFields.message",
        ))

    return errs


def _validate_status(_msg: "Message") -> ValidationErrors:
    # Status: no required struct fields beyond envelope
    return []


def _validate_response_intent(msg: "Message") -> ValidationErrors:
    intent = msg.intent
    errs: ValidationErrors = []

    if msg.response is None:
        errs.append(_errorf(
            "warn", intent, "response", "_status", "nil_struct",
            "response is None; the decoder should have populated it from the wire message.",
            "Ensure decode_message was called before using the decoded message.",
            "decoded = decode_message(raw)",
            "message/decoder.py:decode_message",
        ))
        return errs

    if not msg.response.status:
        errs.append(_errorf(
            "warn", intent, "response.status", "_status", "required",
            "response.status is empty; it may not have been decoded correctly.",
            "Check that the raw message contains a _status header field.",
            "", "message/decoder.py:decode_message",
        ))

    return errs


# =============================================================================
# PAYLOAD VALIDATOR
# =============================================================================

def _validate_payload(msg: "Message") -> ValidationErrors:
    """Validate the payload contents for NeuralMemory batch intents."""
    from pod_os_client.message.types import BatchEventSpec, BatchLinkEventSpec, Tag, TagList

    intent = msg.intent
    errs: ValidationErrors = []

    if intent == "StoreBatchEvents":
        has_batch = msg.neural_memory and msg.neural_memory.batch_events
        payload_data = msg.payload.data if msg.payload else None

        if not has_batch:
            if payload_data is None:
                errs.append(_errorf(
                    "error", intent,
                    "neural_memory.batch_events", "payload",
                    "required",
                    "StoreBatchEvents requires a non-empty neural_memory.batch_events list.",
                    "Populate neural_memory.batch_events with BatchEventSpec records.",
                    "msg.neural_memory = NeuralMemoryFields(batch_events=[BatchEventSpec(event=EventFields(...))])",
                    "message/types.py:NeuralMemoryFields.batch_events",
                    "message/encoder.py:format_batch_events_payload",
                ))
                return errs
            if not isinstance(payload_data, list) or not all(isinstance(x, BatchEventSpec) for x in payload_data):
                errs.append(_errorf(
                    "error", intent,
                    "payload.data", "payload",
                    "payload_type",
                    f"StoreBatchEvents payload must be list[BatchEventSpec], got {type(payload_data).__name__}.",
                    "Cast or assign payload.data as list[BatchEventSpec].",
                    "msg.payload = PayloadFields(data=[BatchEventSpec(...)])",
                    "message/types.py:BatchEventSpec",
                ))
            return errs

        for i, spec in enumerate(msg.neural_memory.batch_events):
            path = f"neural_memory.batch_events[{i}].event"
            if not spec.event.timestamp:
                errs.append(_required_field(
                    intent, f"{path}.timestamp", "timestamp",
                    "Set a POSIX microsecond timestamp for this batch event.",
                    'events[i].event.timestamp = "+1234567890.123456"',
                    "message/types.py:BatchEventSpec",
                ))
            if not spec.event.owner and not spec.event.owner_unique_id:
                errs.append(_errorf(
                    "error", intent,
                    f"{path}.owner / {path}.owner_unique_id",
                    "owner / owner_unique_id",
                    "one_of_required",
                    f"BatchEventSpec[{i}]: owner or owner_unique_id is required.",
                    "Set event.owner or event.owner_unique_id.",
                    'events[i].event.owner = "$sys"',
                    "message/types.py:BatchEventSpec",
                ))
            if not spec.event.location:
                errs.append(_errorf(
                    "error", intent, f"{path}.location", "loc", "payload_format",
                    f"BatchEventSpec[{i}]: location is required.",
                    "Set event.location to a location string.",
                    'events[i].event.location = "TERRA|47.6|-122.5"',
                    "message/types.py:BatchEventSpec",
                ))
            if not spec.event.location_separator:
                errs.append(_errorf(
                    "error", intent, f"{path}.location_separator", "loc_delim", "payload_format",
                    f"BatchEventSpec[{i}]: location_separator is required.",
                    "Set event.location_separator to match the delimiter in location.",
                    'events[i].event.location_separator = "|"',
                    "message/types.py:BatchEventSpec",
                ))

    elif intent == "StoreBatchTags":
        has_tags = msg.neural_memory and msg.neural_memory.tags
        payload_data = msg.payload.data if msg.payload else None

        if not has_tags:
            if payload_data is not None:
                if isinstance(payload_data, list) and all(isinstance(x, Tag) for x in payload_data):
                    errs.extend(_validate_tag_list(intent, payload_data))
                else:
                    errs.append(_errorf(
                        "error", intent,
                        "neural_memory.tags / payload.data", "payload",
                        "payload_type",
                        f"StoreBatchTags payload must be TagList or list[Tag], got {type(payload_data).__name__}.",
                        "Set neural_memory.tags or payload.data to a TagList.",
                        "msg.neural_memory.tags = [Tag(key='k', value='v')]",
                        "message/types.py:TagList",
                    ))
            else:
                errs.append(_errorf(
                    "error", intent,
                    "neural_memory.tags", "payload",
                    "required",
                    "StoreBatchTags requires a non-empty neural_memory.tags (TagList).",
                    "Populate neural_memory.tags with Tag records.",
                    "msg.neural_memory.tags = [Tag(key='category', value='value')]",
                    "message/types.py:TagList",
                ))
        else:
            errs.extend(_validate_tag_list(intent, msg.neural_memory.tags))

    elif intent == "StoreBatchLinks":
        if not msg.neural_memory or not msg.neural_memory.batch_links:
            errs.append(_errorf(
                "error", intent,
                "neural_memory.batch_links", "payload",
                "required",
                "StoreBatchLinks requires a non-empty neural_memory.batch_links list.",
                "Populate neural_memory.batch_links with BatchLinkEventSpec records.",
                "msg.neural_memory.batch_links = [BatchLinkEventSpec(event=EventFields(...), link=LinkFields(...))]",
                "message/types.py:BatchLinkEventSpec",
            ))
            return errs

        for i, spec in enumerate(msg.neural_memory.batch_links):
            ev_path = f"neural_memory.batch_links[{i}].event"
            lk_path = f"neural_memory.batch_links[{i}].link"

            if not spec.event.timestamp:
                errs.append(_errorf(
                    "error", intent, f"{ev_path}.timestamp", "timestamp", "payload_format",
                    f"BatchLinkEventSpec[{i}]: event.timestamp is required.",
                    "Set a POSIX microsecond timestamp for the link event.",
                    'links[i].event.timestamp = "+1234567890.123456"',
                    "message/types.py:BatchLinkEventSpec",
                ))
            if not spec.event.owner and not spec.event.owner_unique_id:
                errs.append(_errorf(
                    "error", intent,
                    f"{ev_path}.owner / {ev_path}.owner_unique_id",
                    "owner / owner_unique_id", "payload_format",
                    f"BatchLinkEventSpec[{i}]: event.owner or event.owner_unique_id is required.",
                    "Set event.owner or event.owner_unique_id.",
                    'links[i].event.owner = "$sys"',
                    "message/types.py:BatchLinkEventSpec",
                ))
            if not spec.link.timestamp:
                errs.append(_errorf(
                    "error", intent, f"{lk_path}.timestamp", "timestamp", "payload_format",
                    f"BatchLinkEventSpec[{i}]: link.timestamp is required (NOT auto-generated).",
                    "Set link.timestamp explicitly to the link creation time.",
                    'links[i].link.timestamp = "+1234567890.123456"',
                    "message/types.py:LinkFields.timestamp",
                ))
            has_id_pair = spec.link.event_a and spec.link.event_b
            has_uid_pair = spec.link.unique_id_a and spec.link.unique_id_b
            if not has_id_pair and not has_uid_pair:
                errs.append(_errorf(
                    "error", intent,
                    f"{lk_path}.event_a+event_b / {lk_path}.unique_id_a+unique_id_b",
                    "event_id_a+event_id_b / unique_id_a+unique_id_b", "payload_format",
                    f"BatchLinkEventSpec[{i}]: (event_a AND event_b) or (unique_id_a AND unique_id_b) required.",
                    "Set both event_a and event_b, or both unique_id_a and unique_id_b.",
                    'links[i].link.event_a = "a"\nlinks[i].link.event_b = "b"',
                    "message/types.py:LinkFields",
                ))
            if not spec.link.category:
                errs.append(_errorf(
                    "error", intent, f"{lk_path}.category", "category", "payload_format",
                    f"BatchLinkEventSpec[{i}]: link.category is required.",
                    "Set link.category to a relationship string.",
                    'links[i].link.category = "related"',
                    "message/types.py:LinkFields.category",
                ))
            if spec.link.strength_a == 0:
                errs.append(_errorf(
                    "error", intent, f"{lk_path}.strength_a", "strength_a", "payload_format",
                    f"BatchLinkEventSpec[{i}]: link.strength_a is required.",
                    "Set link.strength_a to a non-zero float.",
                    "links[i].link.strength_a = 1.0",
                    "message/types.py:LinkFields.strength_a",
                ))
            if spec.link.strength_b == 0:
                errs.append(_errorf(
                    "error", intent, f"{lk_path}.strength_b", "strength_b", "payload_format",
                    f"BatchLinkEventSpec[{i}]: link.strength_b is required.",
                    "Set link.strength_b to a non-zero float.",
                    "links[i].link.strength_b = 1.0",
                    "message/types.py:LinkFields.strength_b",
                ))
            if not spec.link.owner_event_id and not spec.link.owner_unique_id:
                errs.append(_errorf(
                    "error", intent,
                    f"{lk_path}.owner_event_id / {lk_path}.owner_unique_id",
                    "owner_event_id / owner_unique_id", "payload_format",
                    f"BatchLinkEventSpec[{i}]: link.owner_event_id or link.owner_unique_id is required.",
                    "Set link.owner_event_id or link.owner_unique_id.",
                    'links[i].link.owner_event_id = "owner-event-id"',
                    "message/types.py:LinkFields.owner_event_id",
                ))

    return errs


def _validate_tag_list(intent: str, tags: list) -> ValidationErrors:
    """Check each Tag in a list for required fields."""
    errs: ValidationErrors = []
    for i, tag in enumerate(tags):
        if not tag.key:
            errs.append(_errorf(
                "error", intent,
                f"neural_memory.tags[{i}].key", "key", "payload_format",
                f"Tag[{i}]: key is required.",
                "Set tag.key to a non-empty category string.",
                'tags[i].key = "category"',
                "message/types.py:Tag.key",
            ))
        if tag.value is None:
            errs.append(_errorf(
                "error", intent,
                f"neural_memory.tags[{i}].value", "value", "payload_format",
                f"Tag[{i}]: value must not be None.",
                "Set tag.value to a non-None value.",
                'tags[i].value = "some-value"',
                "message/types.py:Tag.value",
            ))
    return errs


# =============================================================================
# INTENT VALIDATORS REGISTRY
# =============================================================================

_intent_validators = {
    # NeuralMemory requests
    "StoreEvent": _validate_store_event,
    "StoreBatchEvents": _validate_store_batch_events,
    "StoreBatchTags": _validate_store_batch_tags,
    "GetEvent": _validate_get_event,
    "GetEventsForTags": _validate_get_events_for_tags,
    "LinkEvent": _validate_link_event,
    "UnlinkEvent": _validate_unlink_event,
    "StoreBatchLinks": _validate_store_batch_links,

    # NeuralMemory responses
    "StoreEventResponse": _validate_response_intent,
    "StoreBatchEventsResponse": _validate_response_intent,
    "StoreBatchTagsResponse": _validate_response_intent,
    "GetEventResponse": _validate_response_intent,
    "GetEventsForTagsResponse": _validate_response_intent,
    "LinkEventResponse": _validate_response_intent,
    "UnlinkEventResponse": _validate_response_intent,
    "StoreBatchLinksResponse": _validate_response_intent,

    # Gateway / Actor
    "GatewayId": _validate_gateway_id,
    "GatewayStreamOn": _validate_gateway_stream,
    "GatewayStreamOff": _validate_gateway_stream,
    "ActorRequest": _validate_actor_request,
    "ActorResponse": _validate_actor_response,
    "ActorReport": _validate_actor_report,
    "Status": _validate_status,
}


# =============================================================================
# WIRE VALIDATOR — validate_raw_message
# =============================================================================

def validate_raw_message(raw: bytes | None) -> ValidationErrors:
    """Validate a raw wire-format bytes object in two stages.

    Stage 1: Wire framing — checks length prefixes, To/From format, and messageType.
    Stage 2: Per-intent header fields — checks required header keys for the resolved intent.

    Returns an empty list immediately if validation is disabled (PODOS_VALIDATE not set).
    """
    if not _validation_enabled:
        return []

    ctx = "wire"
    errs: ValidationErrors = []

    if raw is None:
        errs.append(_errorf(
            "error", ctx, "message", "", "nil_struct",
            "Raw message is None.",
            "Ensure the raw bytes are non-None before calling validate_raw_message.",
            "", "message/decoder.py:decode_message",
        ))
        return errs

    min_size = 63
    if len(raw) < min_size:
        errs.append(_errorf(
            "error", ctx, "message", "", "format",
            f"Raw message is {len(raw)} bytes; minimum is {min_size} bytes (7 × 9-byte length fields).",
            "Check that the wire message was not truncated.",
            "", "message/decoder.py:decode_message",
        ))
        return errs

    if len(raw) > MAX_MESSAGE_SIZE:
        errs.append(_errorf(
            "error", ctx, "message", "", "format",
            f"Raw message is {len(raw)} bytes; maximum is {MAX_MESSAGE_SIZE} bytes.",
            "Reduce payload size or increase MAX_MESSAGE_SIZE.",
            "", "message/constants.py:MAX_MESSAGE_SIZE",
        ))
        return errs

    # Parse 7 length prefix fields
    field_defs = [
        ("totalLength", 0, 9),
        ("toLength", 9, 18),
        ("fromLength", 18, 27),
        ("headerLength", 27, 36),
        ("messageType", 36, 45),
        ("dataType", 45, 54),
        ("payloadDataLength", 54, 63),
    ]

    parsed = []
    for name, start, end in field_defs:
        try:
            field_bytes = raw[start:end].rstrip(b"\x00").decode("ascii").strip()
            if field_bytes.startswith("x"):
                val = int(field_bytes[1:], 16)
            else:
                val = int(field_bytes, 10)
            parsed.append(val)
        except (ValueError, UnicodeDecodeError):
            errs.append(_errorf(
                "error", ctx, name, "", "format",
                f"Failed to parse length field '{name}' at bytes [{start}:{end}].",
                f"Ensure bytes [{start}:{end}] form a valid hex or decimal integer.",
                "", "message/decoder.py:_decode_size_param",
            ))
            return errs

    to_length = parsed[1]
    from_length = parsed[2]
    header_length = parsed[3]
    message_type = int(parsed[4])
    payload_data_length = parsed[6]

    prefix_bytes = 63
    to_start = prefix_bytes
    to_end = to_start + to_length
    from_start = to_end
    from_end = from_start + from_length
    header_start = from_end
    header_end = header_start + header_length

    if len(raw) < to_end:
        errs.append(_errorf(
            "error", ctx, "to", "to", "format",
            f"Message too short for 'to' field: need {to_end} bytes, have {len(raw)}.",
            "", "", "message/decoder.py:decode_message",
        ))
        return errs

    if len(raw) < from_end:
        errs.append(_errorf(
            "error", ctx, "from", "from", "format",
            f"Message too short for 'from' field: need {from_end} bytes, have {len(raw)}.",
            "", "", "message/decoder.py:decode_message",
        ))
        return errs

    if len(raw) < header_end:
        errs.append(_errorf(
            "error", ctx, "header", "header", "format",
            f"Message too short for header: need {header_end} bytes, have {len(raw)}.",
            "", "", "message/decoder.py:decode_message",
        ))
        return errs

    # Validate To format
    to_str = raw[to_start:to_end].decode("utf-8", errors="replace")
    if not to_str:
        errs.append(_errorf(
            "error", ctx, "to", "to", "required",
            "'to' field is empty.",
            "Ensure the encoded message has a non-empty 'to' address.",
            'msg.to = "actor@gateway.example.com"',
            "message/types.py:Envelope.to",
        ))
    elif not _is_name_at_gateway(to_str):
        errs.append(_errorf(
            "error", ctx, "to", "to", "format",
            f"'to' field {to_str!r} is not in name@gateway format.",
            "Use a 'to' address containing exactly one '@' with non-empty parts.",
            'msg.to = "actor@gateway.example.com"',
            "message/types.py:Envelope.to",
        ))

    # Validate From format (strip routing suffix)
    from_str = raw[from_start:from_end].decode("utf-8", errors="replace")
    pipe_idx = from_str.find("|")
    if pipe_idx != -1:
        from_str = from_str[:pipe_idx]

    if not from_str:
        errs.append(_errorf(
            "error", ctx, "from", "from", "required",
            "'from' field is empty.",
            "Ensure the encoded message has a non-empty 'from' address.",
            'msg.from_ = "client@gateway.example.com"',
            "message/types.py:Envelope.from_",
        ))
    elif not _is_name_at_gateway(from_str):
        errs.append(_errorf(
            "error", ctx, "from", "from", "format",
            f"'from' field {from_str!r} is not in name@gateway format.",
            "Use a 'from' address containing exactly one '@' with non-empty parts.",
            'msg.from_ = "client@gateway.example.com"',
            "message/types.py:Envelope.from_",
        ))

    if errs:
        return errs

    # Validate messageType is known
    if not _is_known_message_type(message_type):
        errs.append(_errorf(
            "error", ctx, "messageType", "messageType", "format",
            f"messageType {message_type} is not a recognised Intent.MessageType.",
            "Set Intent to a value from IntentType; the MessageType is derived automatically.",
            "msg.intent = IntentType.StoreEvent.name",
            "message/intents.py:IntentType",
        ))
        return errs

    # Stage 2 — parse header and validate per-intent fields
    header_str = raw[header_start:header_end].decode("utf-8", errors="replace")
    try:
        header_map = _decode_wire_header(header_str)
    except Exception as exc:
        errs.append(_errorf(
            "error", ctx, "header", "header", "format",
            f"Header parse error: {exc}",
            "Ensure the header is tab-separated key=value pairs.",
            "", "message/decoder.py:_decode_header",
        ))
        return errs

    errs.extend(_validate_wire_header(message_type, header_map, payload_data_length))
    return errs


def _decode_wire_header(header_str: str) -> dict[str, str]:
    """Decode wire header string into a dict."""
    h: dict[str, str] = {}
    for part in header_str.split("\t"):
        if "=" in part:
            key, value = part.split("=", 1)
            h[key.strip()] = value.strip()
    return h


def _is_known_message_type(t: int) -> bool:
    """Return True if t matches any known Intent.MessageType."""
    return t in _known_message_types


def _build_known_message_types() -> set[int]:
    """Build the set of all known message type integers from IntentType."""
    from pod_os_client.message.intents import IntentType
    known: set[int] = set()
    it = IntentType
    for intent in [
        it.StoreEvent, it.StoreBatchEvents, it.StoreBatchTags,
        it.GetEvent, it.GetEventsForTags,
        it.LinkEvent, it.UnlinkEvent, it.StoreBatchLinks,
        it.StoreEventResponse, it.StoreBatchEventsResponse, it.StoreBatchTagsResponse,
        it.GetEventResponse, it.GetEventsForTagsResponse,
        it.LinkEventResponse, it.UnlinkEventResponse, it.StoreBatchLinksResponse,
        it.GatewayId, it.GatewayDisconnect,
        it.GatewayStreamOn, it.GatewayStreamOff,
        it.GatewayBatchStart, it.GatewayBatchEnd, it.GatewaySendNext, it.GatewayNoSend,
        it.ActorEcho, it.ActorHalt, it.ActorStart,
        it.ActorRequest, it.ActorResponse, it.ActorReport,
        it.ActorRecord, it.ActorUser,
        it.Status, it.Keepalive,
        it.RouteAnyMessage, it.RouteUserOnlyMessage,
        it.QueueNextRequest, it.QueueAllRequest, it.QueueCountRequest, it.QueueEmpty,
        it.ReportRequest, it.InformationReport,
        it.AuthAddUser, it.AuthUpdateUser, it.AuthUserList, it.AuthDisableUser,
    ]:
        if intent.message_type != 0:
            known.add(intent.message_type)
    return known


# Build the set lazily on first use to avoid circular imports at module load time
_known_message_types: set[int] = set()


def _ensure_known_types() -> None:
    global _known_message_types
    if not _known_message_types:
        _known_message_types = _build_known_message_types()


def _is_known_message_type(t: int) -> bool:
    _ensure_known_types()
    return t in _known_message_types


def _has_header(h: dict[str, str], key: str) -> bool:
    """Check for presence and non-empty value of a wire header key."""
    v = h.get(key)
    return v is not None and v != ""


def _validate_wire_header(message_type: int, h: dict[str, str],
                           payload_length: int) -> ValidationErrors:
    """Stage 2 validation: per-intent header field checks."""
    ctx = "wire"
    errs: ValidationErrors = []

    # All intents: optional _msg_id must be non-empty if present
    if "_msg_id" in h and h["_msg_id"] == "":
        errs.append(_errorf(
            "warn", ctx, "Envelope.message_id", "_msg_id", "format",
            "_msg_id header is present but empty; omit it or supply a non-empty value.",
            "Set Envelope.message_id to a UUID or remove it.",
            "import uuid; msg.message_id = str(uuid.uuid4())",
            "message/types.py:Envelope.message_id",
        ))

    if message_type == 1000:
        db_cmd = h.get("_db_cmd", "")
        if not db_cmd:
            errs.append(_errorf(
                "error", ctx, "_db_cmd", "_db_cmd", "header_missing",
                "NeuralMemory request (messageType 1000) is missing _db_cmd header.",
                "Set Intent to a NeuralMemory IntentType; the encoder writes _db_cmd automatically.",
                "msg.intent = IntentType.StoreEvent.name",
                "message/header.py", "message/intents.py",
            ))
            return errs
        if not _is_known_neural_memory_command(db_cmd):
            errs.append(_errorf(
                "error", ctx, "_db_cmd", "_db_cmd", "header_value",
                f"_db_cmd={db_cmd!r} is not a known NeuralMemory command.",
                "Use a command produced by a NeuralMemory IntentType.",
                "msg.intent = IntentType.StoreEvent.name",
                "message/intents.py:commandToIntent",
            ))
        errs.extend(_validate_neural_memory_request_header(db_cmd, h, payload_length))

    elif message_type == 1001:
        errs.extend(_validate_neural_memory_response_header(h))

    elif message_type == 5:
        if not _has_header(h, "id:name"):
            errs.append(_errorf(
                "error", ctx, "Envelope.client_name", "id:name", "header_missing",
                "GatewayId message is missing required id:name header.",
                "Set Envelope.client_name; the encoder writes id:name automatically.",
                'msg.client_name = "MyClient"',
                "message/types.py:Envelope.client_name", "message/header.py:_gateway_identify_connection_header",
            ))

    elif message_type == 2:
        if not _has_header(h, "_msg_id"):
            errs.append(_errorf(
                "warn", ctx, "Envelope.message_id", "_msg_id", "header_missing",
                "ActorEcho message is missing _msg_id; echo responses may not be correlatable.",
                "Set Envelope.message_id to a UUID.",
                "import uuid; msg.message_id = str(uuid.uuid4())",
                "message/types.py:Envelope.message_id",
            ))

    elif message_type == 4:
        type_val = h.get("_type", "")
        if type_val != "status":
            errs.append(_errorf(
                "error", ctx, "_type", "_type", "header_missing",
                "ActorRequest message must have _type=status header.",
                "Use IntentType.ActorRequest; the encoder writes _type=status automatically.",
                "msg.intent = IntentType.ActorRequest.name",
                "message/header.py:_actor_request_header",
            ))

    elif message_type in (9, 10):
        pass  # GatewayStreamOff/On: no required header fields

    elif message_type in (3, 19, 30):
        pass  # Status/ActorReport/ActorResponse: no required header fields

    else:
        errs.append(_warn_uncovered(
            ctx,
            f"messageType {message_type} is currently uncovered; wire header validation is in development.",
        ))

    return errs


_KNOWN_NEURAL_MEMORY_COMMANDS = frozenset([
    "store", "store_batch", "tag_store_batch", "get",
    "events_for_tag", "link", "unlink", "link_batch",
])


def _is_known_neural_memory_command(cmd: str) -> bool:
    return cmd in _KNOWN_NEURAL_MEMORY_COMMANDS


def _validate_neural_memory_request_header(cmd: str, h: dict[str, str],
                                            payload_length: int) -> ValidationErrors:
    ctx = "wire"
    errs: ValidationErrors = []

    if cmd == "store":
        if not _has_header(h, "timestamp"):
            errs.append(_errorf(
                "warn", ctx, "event.timestamp", "timestamp", "header_missing",
                "StoreEvent header is missing 'timestamp'; the encoder should write it automatically.",
                "Verify that encode_message was called and event.timestamp was set.",
                'msg.event.timestamp = "+1234567890.123456"',
                "message/header.py:_store_event_message_header",
            ))

    elif cmd == "store_batch":
        if payload_length == 0:
            errs.append(_errorf(
                "error", ctx, "neural_memory.batch_events", "payload", "required",
                "StoreBatchEvents payload is empty; batch events must be encoded in the payload.",
                "Populate neural_memory.batch_events before encoding.",
                "msg.neural_memory.batch_events = [BatchEventSpec(...)]",
                "message/encoder.py:format_batch_events_payload",
            ))

    elif cmd == "tag_store_batch":
        if not _has_header(h, "event_id") and not _has_header(h, "unique_id"):
            errs.append(_errorf(
                "error", ctx, "event.id / event.unique_id", "event_id / unique_id", "header_missing",
                "StoreBatchTags header is missing event_id or unique_id.",
                "Set event.id or event.unique_id to identify the target event.",
                'msg.event.id = "2024.01.15..."',
                "message/header.py:_store_batch_tags_message_header",
            ))
        if not _has_header(h, "owner") and not _has_header(h, "owner_unique_id"):
            errs.append(_errorf(
                "error", ctx, "event.owner / event.owner_unique_id", "owner / owner_unique_id", "header_missing",
                "StoreBatchTags header is missing owner or owner_unique_id.",
                "Set event.owner or event.owner_unique_id.",
                'msg.event.owner = "$sys"',
                "message/header.py:_store_batch_tags_message_header",
            ))

    elif cmd == "get":
        if not _has_header(h, "event_id") and not _has_header(h, "unique_id"):
            errs.append(_errorf(
                "error", ctx, "event.id / event.unique_id", "event_id / unique_id", "header_missing",
                "GetEvent header is missing event_id or unique_id.",
                "Set event.id or event.unique_id to identify the event to retrieve.",
                'msg.event.id = "2024.01.15..."',
                "message/header.py:_get_event_message_header",
            ))

    elif cmd == "events_for_tag":
        if not _has_header(h, "buffer_results"):
            errs.append(_errorf(
                "warn", ctx, "neural_memory.get_events_for_tags.buffer_results", "buffer_results", "header_missing",
                "GetEventsForTags header is missing buffer_results; this field is expected.",
                "Set neural_memory.get_events_for_tags.buffer_results.",
                "msg.neural_memory.get_events_for_tags.buffer_results = True",
                "message/types.py:GetEventsForTagsOptions.buffer_results",
            ))

    elif cmd == "link":
        if not _has_header(h, "strength_a"):
            errs.append(_errorf(
                "error", ctx, "neural_memory.link.strength_a", "strength_a", "header_missing",
                "LinkEvent header is missing strength_a.",
                "Set neural_memory.link.strength_a.",
                "msg.neural_memory.link.strength_a = 1.0",
                "message/header.py:_link_events_message_header",
            ))
        if not _has_header(h, "strength_b"):
            errs.append(_errorf(
                "error", ctx, "neural_memory.link.strength_b", "strength_b", "header_missing",
                "LinkEvent header is missing strength_b.",
                "Set neural_memory.link.strength_b.",
                "msg.neural_memory.link.strength_b = 1.0",
                "message/header.py:_link_events_message_header",
            ))
        if not _has_header(h, "category"):
            errs.append(_errorf(
                "error", ctx, "neural_memory.link.category", "category", "header_missing",
                "LinkEvent header is missing category.",
                "Set neural_memory.link.category.",
                'msg.neural_memory.link.category = "related"',
                "message/header.py:_link_events_message_header",
            ))
        if not _has_header(h, "timestamp"):
            errs.append(_errorf(
                "error", ctx, "neural_memory.link.timestamp", "timestamp", "header_missing",
                "LinkEvent header is missing timestamp.",
                "Set neural_memory.link.timestamp.",
                'msg.neural_memory.link.timestamp = "+1234567890.123456"',
                "message/header.py:_link_events_message_header",
            ))
        if not _has_header(h, "owner_event_id") and not _has_header(h, "owner_unique_id"):
            errs.append(_errorf(
                "error", ctx,
                "neural_memory.link.owner_event_id / neural_memory.link.owner_unique_id",
                "owner_event_id / owner_unique_id", "header_missing",
                "LinkEvent header is missing owner_event_id or owner_unique_id.",
                "Set neural_memory.link.owner_event_id or neural_memory.link.owner_unique_id.",
                'msg.neural_memory.link.owner_event_id = "owner-id"',
                "message/header.py:_link_events_message_header",
            ))
        has_event_ids = _has_header(h, "event_id_a") and _has_header(h, "event_id_b")
        has_unique_ids = _has_header(h, "unique_id_a") and _has_header(h, "unique_id_b")
        if not has_event_ids and not has_unique_ids:
            errs.append(_errorf(
                "error", ctx,
                "neural_memory.link.event_a+event_b / neural_memory.link.unique_id_a+unique_id_b",
                "event_id_a+event_id_b / unique_id_a+unique_id_b", "header_missing",
                "LinkEvent header is missing event pair (event_id_a+event_id_b or unique_id_a+unique_id_b).",
                "Set both event_a and event_b, or both unique_id_a and unique_id_b on neural_memory.link.",
                'msg.neural_memory.link.event_a = "a"\nmsg.neural_memory.link.event_b = "b"',
                "message/header.py:_link_events_message_header",
            ))

    elif cmd == "unlink":
        if not _has_header(h, "event_id") and not _has_header(h, "unique_id"):
            errs.append(_errorf(
                "error", ctx,
                "neural_memory.link.id / neural_memory.link.unique_id",
                "event_id / unique_id", "header_missing",
                "UnlinkEvent header is missing event_id or unique_id.",
                "Set neural_memory.link.id or neural_memory.link.unique_id.",
                'msg.neural_memory.link.id = "link-event-id"',
                "message/header.py:_unlink_events_message_header",
            ))

    elif cmd == "link_batch":
        if payload_length == 0:
            errs.append(_errorf(
                "error", ctx, "neural_memory.batch_links", "payload", "required",
                "StoreBatchLinks payload is empty; batch link records must be encoded in the payload.",
                "Populate neural_memory.batch_links before encoding.",
                "msg.neural_memory.batch_links = [BatchLinkEventSpec(...)]",
                "message/encoder.py:format_batch_link_events_payload",
            ))

    else:
        errs.append(_warn_uncovered(
            ctx,
            f"NeuralMemory command {cmd!r} is currently uncovered; header validation is in development.",
        ))

    return errs


def _validate_neural_memory_response_header(h: dict[str, str]) -> ValidationErrors:
    ctx = "wire"
    errs: ValidationErrors = []

    if not _has_header(h, "_status"):
        errs.append(_errorf(
            "warn", ctx, "response.status", "_status", "header_missing",
            "NeuralMemory response (messageType 1001) is missing _status header.",
            "This is expected for brief-hit responses. For other responses, check the Evolutionary Neural Memory Actor.",
            "", "message/decoder.py:decode_message",
        ))

    db_cmd = h.get("_type") or h.get("_command") or h.get("_db_cmd") or ""

    if db_cmd == "get":
        if not _has_header(h, "_event_id") and not _has_header(h, "event_id"):
            errs.append(_errorf(
                "warn", ctx, "event.id", "_event_id / event_id", "header_missing",
                "GetEventResponse is missing _event_id or event_id.",
                "", "", "message/decoder.py",
            ))
    elif db_cmd == "link":
        if not _has_header(h, "link_event"):
            errs.append(_errorf(
                "warn", ctx, "response.link_id", "link_event", "header_missing",
                "LinkEventResponse is missing link_event (the assigned link ID).",
                "", "", "message/decoder.py",
            ))
    elif db_cmd in ("store", "store_batch", "tag_store_batch"):
        if not _has_header(h, "_count"):
            errs.append(_errorf(
                "warn", ctx, "response.total_events", "_count", "header_missing",
                f"{db_cmd} response is missing _count.",
                "", "", "message/decoder.py",
            ))
    elif db_cmd == "link_batch":
        if not _has_header(h, "_links_ok"):
            errs.append(_errorf(
                "warn", ctx, "response.storage_success_count", "_links_ok", "header_missing",
                "StoreBatchLinksResponse is missing _links_ok.",
                "", "", "message/decoder.py",
            ))

    return errs


# =============================================================================
# AI-ASSISTED REMEDIATION — explain_validation_errors (vLLM integration)
# =============================================================================

def _render_error_prompt(ve: ValidationError) -> str:
    refs = ", ".join(ve.references)
    return (
        "You are a Pod-OS Python client expert. A message validation error occurred.\n\n"
        f"Intent: {ve.intent}\n"
        f"Struct Path: {ve.struct_path}\n"
        f"Wire Field: {ve.wire_field}\n"
        f"Rule Violated: {ve.rule}\n"
        f"Description: {ve.message}\n"
        f"Suggested Fix: {ve.fix}\n"
        f"Example Code: {ve.example_code}\n"
        f"Source References: {refs}\n\n"
        f"Task: Provide corrected Python code for this message construction. Show all required fields "
        f"for the {ve.intent} intent. If multiple valid approaches exist (e.g. event_a/event_b vs "
        f"unique_id_a/unique_id_b), show both. Use only types from the message package."
    )


def explain_validation_errors(errs: ValidationErrors, endpoint: str,
                               model: str = "default") -> tuple[str, Exception | None]:
    """Submit validation errors to a vLLM-hosted endpoint for AI-assisted remediation.

    The endpoint must implement the OpenAI-compatible /v1/chat/completions interface.

    Args:
        errs: List of ValidationError objects to explain
        endpoint: Base URL, e.g. "http://localhost:8000"
        model: Model name to request, e.g. "meta-llama/Llama-3.1-8B-Instruct"

    Returns:
        Tuple of (combined AI-generated explanation, error or None).
        Returns ("", None) when validation is disabled or errs is empty.
    """
    if not _validation_enabled or not errs:
        return "", None

    if not endpoint:
        return "", ValueError("vLLM endpoint is required")

    if not model:
        model = "default"

    parts: list[str] = []

    for ve in errs:
        prompt = _render_error_prompt(ve)

        req_body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert in the Pod-OS Python client message library. Provide concise, correct Python code examples.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "max_tokens": 512,
            "temperature": 0.1,
        }

        try:
            req_bytes = json.dumps(req_body).encode("utf-8")
            req = urllib.request.Request(
                endpoint + "/v1/chat/completions",
                data=req_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
        except urllib.error.URLError as exc:
            return "\n".join(parts), exc

        try:
            chat_resp = json.loads(body)
        except json.JSONDecodeError as exc:
            return "\n".join(parts), exc

        choices = chat_resp.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            parts.append(f"=== {ve.intent} / {ve.rule} ===\n{content}")

    result = "\n\n".join(parts).rstrip("\n")
    return result, None
