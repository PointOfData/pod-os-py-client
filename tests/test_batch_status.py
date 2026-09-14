"""Tests for batch record status helpers."""

from pod_os_client.message.batch_status import batch_events_failed, batch_links_failed
from pod_os_client.message.types import Message, ResponseFields, StoreBatchEventRecord, StoreLinkBatchEventRecord


def test_batch_links_failed() -> None:
    msg = Message(
        response=ResponseFields(
            store_link_batch_event_record=StoreLinkBatchEventRecord(
                status="ERROR",
                message="OWNER EVENT NOT FOUND",
                links_with_errors=2,
            )
        )
    )
    assert batch_links_failed(msg) == "OWNER EVENT NOT FOUND"


def test_batch_events_failed() -> None:
    msg = Message(
        response=ResponseFields(
            store_batch_event_record=StoreBatchEventRecord(
                status="ERROR",
                message="missing owner",
            )
        )
    )
    assert batch_events_failed(msg) == "missing owner"
