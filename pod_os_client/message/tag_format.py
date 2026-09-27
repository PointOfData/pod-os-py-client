"""Extended tag formats: GetEvent tag_format=1 and GetEventsForTags buffer_format=1.

Both formats add a storage timestamp to each tag and, when requested, the tag's owner.
"""

from pod_os_client.message.types import Message, TagOutput, TagOwnerOutput

__all__ = [
    "apply_tag_owner_output",
]

# Event key Pod-OS reports as the owner of tags that have no owning event (e.g. tags
# created under the $sys owner).
_NULL_OWNER_KEY_PREFIX = "+0000000000.000000"

_OWNER_MARKER = "\towner="


def parse_event_tag_header(name: str, value: str) -> TagOutput | None:
    """Parse one GetEvent response header field carrying a tag.

    tag_format=0: ``event_tag:nnnnnnnnn:fffffffff=key=value``
    tag_format=1: ``event_tag:nnnnnnnnn:fffffffff:ssssssssss.uuuuuu[:owner_id]=key=value``

    The name is split at most three times so owner IDs containing ':' stay intact.
    Returns None when ``name`` is not a tag header.
    """
    if not name.startswith("event_tag:"):
        return None
    parts = name[len("event_tag:"):].split(":", 3)
    if len(parts) < 2:
        return None

    tag = TagOutput(frequency=1)
    try:
        tag.tag_number = int(parts[0])
    except ValueError:
        pass
    try:
        tag.frequency = int(parts[1])
    except ValueError:
        pass
    if len(parts) >= 3:
        tag.timestamp = parts[2]
    if len(parts) == 4:
        tag.owner = normalize_tag_owner(parts[3])
    tag.key, tag.value = split_tag_key_value(value)
    return tag


def split_tag_key_value(s: str) -> tuple[str, str]:
    """Split a ``key=value`` tag string. A string without a key keeps the whole text as the value."""
    eq_idx = s.find("=")
    if eq_idx > 0:
        return s[:eq_idx], s[eq_idx + 1:]
    return "", s


def normalize_tag_owner(owner: str) -> str:
    """Map Pod-OS "no owner" markers to an empty string."""
    if owner == "NULL" or owner.startswith(_NULL_OWNER_KEY_PREFIX):
        return ""
    return owner


def normalize_tag_owner_lines(payload: str) -> str:
    """Repair buffer_format=1 payloads requested with get_tag_owner or get_tag_owner_unique_id.

    Pod-OS writes each tag's owner after the tag line's newline, so it runs into the next record::

        _event_tag=K\\t...\\ttag_timestamp=T\\n\\towner=O_event_tag=K\\t...

    Each owner is rejoined to the tag line it belongs to and the record break is restored.
    Payloads already in the documented form (owner before the newline) are unchanged.
    """
    if "\n\towner=" not in payload:
        return payload
    payload = payload.replace("\n\towner=", _OWNER_MARKER)

    out: list[str] = []
    pos = 0
    while True:
        i = payload.find(_OWNER_MARKER, pos)
        if i < 0:
            out.append(payload[pos:])
            break
        start = i + len(_OWNER_MARKER)
        out.append(payload[pos:start])
        pos = start

        end = len(payload)
        for sep in ("\t", "\n"):
            j = payload.find(sep, start)
            if 0 <= j < end:
                end = j
        j = payload.find("_event_tag=", start, end)
        if j >= 0:
            out.append(payload[start:j])
            out.append("\n")
            pos = j
    return "".join(out)


def _tag_owner_output_of(msg: Message) -> TagOwnerOutput | str:
    nm = msg.neural_memory
    if nm is None:
        return TagOwnerOutput.NONE
    if msg.intent == "GetEvent" and nm.get_event is not None:
        return nm.get_event.tag_owner_output
    if msg.intent == "GetEventsForTags" and nm.get_events_for_tags is not None:
        return nm.get_events_for_tags.tag_owner_output
    return TagOwnerOutput.NONE


def apply_tag_owner_output(request: Message | None, response: Message | None) -> None:
    """Move decoded tag owners from ``TagOutput.owner`` to ``TagOutput.owner_unique_id``.

    Applies only when ``request`` asked for owners by unique ID (``TagOwnerOutput.UNIQUE_ID``).
    Pod-OS responses do not say which owner form they carry, so ``decode_message`` always
    fills ``owner``. ``Client.send_message`` applies this automatically; call it yourself
    when decoding raw responses with ``decode_message``.
    """
    if request is None or response is None or _tag_owner_output_of(request) != TagOwnerOutput.UNIQUE_ID:
        return

    def move(tags: list[TagOutput]) -> None:
        for tag in tags:
            if tag.owner:
                tag.owner_unique_id = tag.owner
                tag.owner = ""

    if response.event is not None:
        move(response.event.tags)
    if response.response is not None:
        for event in response.response.event_records:
            move(event.tags)
