"""Tag version history helpers.

Field and facet names are caller-defined. Version order is storage timestamp, then tag number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pod_os_client.message.types import TagOutput


@dataclass(slots=True)
class TagSighting:
    """One version index across the facets of a field."""

    index: int = 0
    facets: dict[str, TagOutput] = field(default_factory=dict)


@dataclass(slots=True)
class TagTerm:
    """One search term. key is the full tag key; value may contain '='."""

    key: str = ""
    value: str = ""


def _tag_before(a: TagOutput, b: TagOutput) -> bool:
    """True when a is strictly earlier than b (timestamp, then tag number)."""
    if a.timestamp != b.timestamp:
        return a.timestamp < b.timestamp
    return a.tag_number < b.tag_number


def latest_by_key(tags: list[TagOutput]) -> dict[str, TagOutput]:
    """Latest row for each full tag key.

    The winner is the greatest storage timestamp, then the greatest tag number.
    When both are equal, the later input row wins.
    """
    out: dict[str, TagOutput] = {}
    for tag in tags:
        prev = out.get(tag.key)
        if prev is None or not _tag_before(tag, prev):
            out[tag.key] = tag
    return out


def field_history(tags: list[TagOutput], field_name: str) -> list[TagSighting]:
    """Zip versions of keys that start with ``field_name + '.'``.

    Each key is sorted by storage timestamp, then tag number. A facet added in a
    later batch is absent from earlier sightings. An empty field returns no sightings.
    """
    if not field_name:
        return []
    prefix = field_name + "."
    groups: dict[str, list[TagOutput]] = {}
    order: list[str] = []
    for tag in tags:
        if not tag.key.startswith(prefix) or len(tag.key) == len(prefix):
            continue
        facet = tag.key[len(prefix):]
        if facet not in groups:
            order.append(facet)
            groups[facet] = []
        groups[facet].append(tag)
    if not groups:
        return []
    max_n = 0
    for facet in order:
        rows = sorted(groups[facet], key=lambda row: (row.timestamp, row.tag_number))
        groups[facet] = rows
        max_n = max(max_n, len(rows))
    sightings = [TagSighting(index=i) for i in range(max_n)]
    for facet in order:
        rows = groups[facet]
        offset = max_n - len(rows)
        for i, row in enumerate(rows):
            sightings[offset + i].facets[facet] = row
    return sightings


def suggest_delta(has_previous: bool, previous: str, next_value: str) -> str:
    """Classify a new value. AppendTags does not call this."""
    if not has_previous:
        return "initial"
    if previous == next_value:
        return "confirmed"
    return "modified"


def tag_search_clauses(terms: list[TagTerm]) -> str:
    """One clause per term. The first line is boolean:or; later lines are boolean:and."""
    lines: list[str] = []
    for i, term in enumerate(terms):
        op = "or" if i == 0 else "and"
        lines.append(f"clause_type:S\tboolean:{op}\tlow:{term.key}={term.value}")
    return "\n".join(lines)
