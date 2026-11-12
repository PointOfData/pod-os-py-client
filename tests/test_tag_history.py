"""Tag version history helpers and Get link/target tag timestamps."""

from pod_os_client.message.decoder import decode_message
from pod_os_client.message.tag_history import (
    TagTerm,
    field_history,
    latest_by_key,
    suggest_delta,
    tag_search_clauses,
)
from pod_os_client.message.types import TagOutput


def _tag(key: str, value: str, ts: str, n: int) -> TagOutput:
    return TagOutput(key=key, value=value, timestamp=ts, tag_number=n, frequency=1)


def _frame(header: str, payload: str) -> bytes:
    to_b = b"mem@gateway.example.com"
    from_b = b"client@gateway.example.com"
    header_b = header.encode("ascii")
    payload_b = payload.encode("ascii")
    payload_len = f"x{len(payload_b):08x}"
    to_len = f"x{len(to_b):08x}"
    from_len = f"x{len(from_b):08x}"
    header_len = f"x{len(header_b):08x}"
    msg_type = f"{1001:09d}"
    dt = f"{0:09d}"
    total = (
        len(to_b) + 9 + len(from_b) + 9 + len(header_b) + 9
        + len(msg_type) + len(dt) + len(payload_b) + 9 + 9
    )
    prefix = (
        f"x{total:08x}" + to_len + from_len + header_len + msg_type + dt + payload_len
    )
    return prefix.encode("ascii") + to_b + from_b + header_b + payload_b


def test_latest_by_key_timestamp_then_tag_number():
    tags = [
        _tag("hue.alpha", "old", "0000000001.000000", 9),
        _tag("hue.alpha", "mid", "0000000002.000000", 1),
        _tag("hue.alpha", "tie-low", "0000000002.000000", 4),
        _tag("hue.beta", "only", "0000000001.000000", 1),
        _tag("hue.alpha", "tie-high", "0000000002.000000", 4),
    ]
    got = latest_by_key(tags)
    assert got["hue.alpha"].value == "tie-high"
    assert got["hue.beta"].value == "only"
    later = latest_by_key([
        _tag("k", "low-number", "0000000005.000000", 1),
        _tag("k", "high-number", "0000000005.000000", 8),
    ])
    assert later["k"].value == "high-number"
    earlier_ts = latest_by_key([
        _tag("k", "new-ts", "0000000009.000000", 1),
        _tag("k", "old-ts", "0000000001.000000", 99),
    ])
    assert earlier_ts["k"].value == "new-ts"


def test_field_history_zip_and_edges():
    tags = [
        _tag("paint.beta", "b0", "0000000002.000000", 1),
        _tag("paint.alpha", "a-low", "0000000002.000000", 2),
        _tag("paint.alpha", "a-tie", "0000000002.000000", 9),
        _tag("other.alpha", "nope", "0000000009.000000", 1),
        _tag("paint", "bare", "0000000009.000000", 1),
    ]
    got = field_history(tags, "paint")
    assert len(got) == 2
    assert got[0].index == 0
    assert got[0].facets["alpha"].value == "a-low"
    assert "beta" not in got[0].facets
    assert got[1].facets["alpha"].value == "a-tie"
    assert got[1].facets["beta"].value == "b0"
    assert field_history(tags, "") == []
    assert field_history(tags, "pai") == []

    dotted = field_history([
        _tag("a.b.c", "yes", "0000000001.000000", 1),
        _tag("a.bc", "no", "0000000001.000000", 1),
        _tag("a.b", "bare", "0000000001.000000", 1),
    ], "a.b")
    assert len(dotted) == 1
    assert dotted[0].facets["c"].value == "yes"
    assert len(dotted[0].facets) == 1


def test_field_history_conventional_names_are_ordinary_keys():
    tags = [
        _tag("stage.value", "seed", "0000000001.000000", 1),
        _tag("stage.event_timestamp", "2020", "0000000001.000001", 2),
        _tag("stage.delta_type", "initial", "0000000001.000002", 3),
        _tag("stage.confidence", "0.5", "0000000001.000003", 4),
        _tag("stage.evidence", "", "0000000001.000004", 5),
        _tag("stage.source", "doc-1", "0000000001.000005", 6),
        _tag("stage.value", "series-a", "0000000002.000000", 7),
        _tag("stage.source", "doc-2", "0000000002.000005", 12),
    ]
    got = field_history(tags, "stage")
    assert got[0].facets["value"].value == "seed"
    assert got[1].facets["source"].value == "doc-2"


def test_suggest_delta_and_search_clauses():
    assert suggest_delta(False, "", "seed") == "initial"
    assert suggest_delta(True, "seed", "seed") == "confirmed"
    assert suggest_delta(True, "seed", "series-a") == "modified"
    got = tag_search_clauses([
        TagTerm(key="hue.alpha", value="red=blue"),
        TagTerm(key="hue.beta", value="1"),
    ])
    lines = got.split("\n")
    assert lines[0] == "clause_type:S\tboolean:or\tlow:hue.alpha=red=blue"
    assert lines[1] == "clause_type:S\tboolean:and\tlow:hue.beta=1"


def test_decode_get_event_link_and_target_tag_history():
    header = "_type=get\t_status=OK\t_event_id=evt_a\t_unique_id=eo_seed"
    payload = "\n".join([
        "_link=link1\tunique_id=lk_1\ttarget_event=evt_n\ttarget_unique_id=eo_nbr\tstrength=0.5\tcategory=rel",
        "_linktag\tevent_id=link1\tunique=lk_1\tfreq=1\ttimestamp=0000000002.000000\tvalue=paint.alpha=later",
        "_linktag\tevent_id=link1\tunique=lk_1\tfreq=1\ttimestamp=0000000001.000000\tvalue=paint.alpha=earlier",
        "_target_event_tag\tevent_id=evt_n\tfreq=1\ttimestamp=0000000002.000000\tvalue=paint.alpha=n-later",
        "_target_event_tag\tevent_id=evt_n\tfreq=1\ttimestamp=0000000001.000000\tvalue=paint.alpha=n-earlier",
    ])
    decoded = decode_message(_frame(header, payload))
    assert decoded.event is not None
    assert len(decoded.event.links) == 1
    link = decoded.event.links[0]
    assert len(link.tags) == 2
    assert link.tags[0].timestamp and link.tags[1].timestamp
    assert len(link.target_tags) == 2
    assert link.target_tags[0].timestamp and link.target_tags[1].timestamp
    link_hist = field_history(link.tags, "paint")
    assert link_hist[0].facets["alpha"].value == "earlier"
    assert link_hist[1].facets["alpha"].value == "later"
    target_hist = field_history(link.target_tags, "paint")
    assert target_hist[0].facets["alpha"].value == "n-earlier"
    assert target_hist[1].facets["alpha"].value == "n-later"
