"""Helpers for interpreting StoreBatchLinks / StoreBatchEvents batch record status."""

from __future__ import annotations

from pod_os_client.message.types import Message


def batch_links_failed(msg: Message) -> str | None:
    """Return an error message when StoreBatchLinks batch record reports failures.

    The envelope ``processing_status()`` can be ``OK`` while ``links_with_errors > 0``
    or the batch record status is ``ERROR``.
    """
    if msg.response is None:
        return None
    rec = msg.response.store_link_batch_event_record
    if rec is None:
        if msg.response.storage_error_count > 0:
            return "link store failed"
        return None
    if (rec.status or "").strip().upper() == "ERROR" or rec.links_with_errors > 0:
        text = (rec.message or "").strip()
        return text or "link store failed"
    return None


def batch_events_failed(msg: Message) -> str | None:
    """Return an error message when StoreBatchEvents batch record reports failures."""
    if msg.response is None:
        return None
    rec = msg.response.store_batch_event_record
    if rec is None:
        return None
    if (rec.status or "").strip().upper() == "ERROR":
        text = (rec.message or "").strip()
        return text or "batch event store failed"
    return None
