"""Tests for response payload parsing."""

import pytest

from pod_os_client.message.encoder import serialize_tag_value
from pod_os_client.message.responses import (
    parse_get_event_response,
    parse_get_events_for_tags_payload,
    parse_link_event_batch_payload,
    parse_store_batch_events_payload,
    parse_tags_from_payload,
)
from pod_os_client.message.types import Message, PayloadFields, ResponseFields


def test_parse_tags_from_payload():
    """Test parsing tags from payload string."""
    payload = "1\t*\tword1\n2\tcategory\tword2\n3\t\tword3"
    tags = parse_tags_from_payload(payload)
    
    assert len(tags) == 3
    assert tags[0].frequency == 1
    assert tags[0].category == "*"
    assert tags[0].value == "word1"
    
    assert tags[1].frequency == 2
    assert tags[1].category == "category"
    assert tags[1].value == "word2"


def test_parse_get_events_for_tags_brief_hits():
    """Test parsing brief hit responses."""
    msg = Message()
    msg.payload = PayloadFields(
        data="_brief_hit=event123\t_hits=5\n_brief_hit=event456\t_hits=3"
    )
    msg.response = ResponseFields()
    
    events, ok = parse_get_events_for_tags_payload(msg)
    
    assert ok
    assert len(events) == 0  # Brief hits don't return event records
    assert len(msg.response.brief_hits) == 2
    assert msg.response.brief_hits[0].event_id == "event123"
    assert msg.response.brief_hits[0].total_hits == 5
    assert msg.response.brief_hits[1].event_id == "event456"
    assert msg.response.brief_hits[1].total_hits == 3


def test_parse_get_events_for_tags_with_events():
    """Test parsing event records with tags."""
    msg = Message()
    msg.payload = PayloadFields(
        data="_event_id=evt1\tunique_id=uuid1\ttype=test\ttag:1:category=value1"
    )
    msg.response = ResponseFields()
    
    events, ok = parse_get_events_for_tags_payload(msg)
    
    assert ok
    assert len(events) == 1
    assert events[0].id == "evt1"
    assert events[0].unique_id == "uuid1"
    assert events[0].type == "test"
    assert len(events[0].tags) == 1
    assert events[0].tags[0].key == "category"
    assert events[0].tags[0].value == "value1"


def test_parse_get_events_for_tags_with_links():
    """Test parsing events with links."""
    msg = Message()
    msg.payload = PayloadFields(
        data=(
            "_event_id=evt1\tunique_id=uuid1\n"
            "_link=link1\tsource=evt1\ttarget=evt2\tstrength=0.9\tcategory=related\n"
            "_linktag=link1\tfreq=1\tvalue=tag_key=tag_val"
        )
    )
    msg.response = ResponseFields()
    
    events, ok = parse_get_events_for_tags_payload(msg)
    
    assert ok
    assert len(events) == 1
    assert len(events[0].links) == 1
    link = events[0].links[0]
    assert link.id == "link1"
    assert link.event_a == "evt1"
    assert link.event_b == "evt2"
    assert link.strength_b == 0.9
    assert link.category == "related"
    assert len(link.tags) == 1
    assert link.tags[0].key == "tag_key"
    assert link.tags[0].value == "tag_val"


def test_parse_get_event_response():
    """Test parsing GetEvent response."""
    msg = Message()
    msg.payload = PayloadFields(
        data="_link=link1\ttarget_event=evt2\tunique_id=uuid_link\tstrength=1.0\tcategory=test"
    )
    msg.response = ResponseFields()
    
    header_map = {
        "event_tag:1:timestamp": "key1=value1",
        "event_id": "evt1",
    }
    
    tags, links, ok = parse_get_event_response(msg, header_map)
    
    assert ok
    assert len(tags) == 1
    assert tags[0].key == "key1"
    assert tags[0].value == "value1"
    assert len(links) == 1
    assert links[0].id == "link1"
    assert links[0].event_a == "evt1"
    assert links[0].event_b == "evt2"


def test_parse_store_batch_events_payload():
    """Test parsing StoreBatchEvents response."""
    msg = Message()
    msg.payload = PayloadFields(
        data=(
            "_status=OK\t_msg=Success\tevent_id=evt1\tunique_id=uuid1\n"
            "_status=ERROR\t_msg=Failed\tevent_id=evt2"
        )
    )
    
    records, ok = parse_store_batch_events_payload(msg)
    
    assert ok
    assert len(records) == 2
    assert records[0].status == "OK"
    assert records[0].message == "Success"
    assert records[0].event_fields.id == "evt1"
    assert records[1].status == "ERROR"
    assert records[1].message == "Failed"


def test_parse_link_event_batch_payload():
    """Test parsing StoreBatchLinks response."""
    msg = Message()
    msg.payload = PayloadFields(
        data=(
            "_status=OK\t_status_info=Success\tevent_id=link1\t"
            "event_id_a=evt1\tevent_id_b=evt2\tstrength_a=1.0\tstrength_b=0.5\tcategory=test"
        )
    )
    
    records, ok = parse_link_event_batch_payload(msg)
    
    assert ok
    assert len(records) == 1
    assert records[0].status == "OK"
    assert records[0].message == "Success"
    assert records[0].link_error_code is None
    assert records[0].link_fields.id == "link1"
    assert records[0].link_fields.event_a == "evt1"
    assert records[0].link_fields.event_b == "evt2"
    assert records[0].link_fields.strength_a == 1.0
    assert records[0].link_fields.strength_b == 0.5


def test_parse_link_event_batch_payload_with_error_code():
    """Test parsing StoreBatchLinks error response with _link_error_code."""
    msg = Message()
    msg.payload = PayloadFields(
        data=(
            "_status=ERROR\t_status_info=CANNOT CREATE LINK\t_link_error_code=-2\t"
            "unique_id=wikipedia:relation:wikipedia_entity_1_6935_wikipedia_entity_3_8175_2\t"
            "timestamp=+1771540588.541272\tloc=TERRA|47.61403266005673|-122.33532602857244\t"
            "type=wikipedia_relation\tunique_id_a=wikipedia:entity:wikipedia_entity_1_6935\t"
            "unique_id_b=wikipedia:entity:wikipedia_entity_3_8175\t"
            "strength_a=0.8\tstrength_b=0.0\tcategory=is listened to by\t"
            "owner_unique_id=b627d6f5-eeb9-4203-be19-552b9b9210b8"
        )
    )

    records, ok = parse_link_event_batch_payload(msg)

    assert ok
    assert len(records) == 1
    assert records[0].status == "ERROR"
    assert records[0].message == "CANNOT CREATE LINK"
    assert records[0].link_error_code == -2
    assert records[0].link_fields.unique_id == "wikipedia:relation:wikipedia_entity_1_6935_wikipedia_entity_3_8175_2"
    assert records[0].link_fields.unique_id_a == "wikipedia:entity:wikipedia_entity_1_6935"
    assert records[0].link_fields.unique_id_b == "wikipedia:entity:wikipedia_entity_3_8175"
    assert records[0].link_fields.strength_a == 0.8
    assert records[0].link_fields.strength_b == 0.0
    assert records[0].link_fields.category == "is listened to by"
    assert records[0].link_fields.owner_unique_id == "b627d6f5-eeb9-4203-be19-552b9b9210b8"


def test_parse_empty_payload():
    """Test parsing with empty payload returns False."""
    msg = Message()
    msg.payload = None
    
    events, ok = parse_get_events_for_tags_payload(msg)
    assert not ok
    assert len(events) == 0


def test_parse_malformed_payload():
    """Test parsing malformed payload handles gracefully."""
    msg = Message()
    msg.payload = PayloadFields(data="invalid\x00data\x0F")
    msg.response = ResponseFields()
    
    # Should not raise exception
    events, ok = parse_get_events_for_tags_payload(msg)
    assert ok  # Returns True even if no valid events found
    assert len(events) == 0
