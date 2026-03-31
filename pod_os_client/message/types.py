"""Pod-OS message types and structures."""

from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "DateTimeObject",
    "Envelope",
    "EventFields",
    "PayloadFields",
    "NeuralMemoryFields",
    "GetEventOptions",
    "GetEventsForTagsOptions",
    "SearchOptions",
    "LinkFields",
    "ResponseFields",
    "StoreBatchEventRecord",
    "StoreLinkBatchEventRecord",
    "BriefHitRecord",
    "Message",
    "BatchEventSpec",
    "BatchLinkEventSpec",
    "Tag",
    "TagList",
    "TagOutput",
    "SearchProgram",
]


@dataclass(slots=True)
class DateTimeObject:
    """AIP date time object."""

    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0
    microsecond: int = 0


@dataclass(slots=True)
class Envelope:
    """Core routing fields required for all Actor messages."""

    to: str = ""  # Recipient: <Actor Name>@<Gateway Name>
    from_: str = ""  # Sender: <Actor Name>@<Gateway Name>
    intent: str = ""  # Message intent type
    client_name: str = ""  # Unique client identifier; required for GatewayId
    message_id: str = ""  # Unique message identifier for request/response correlation
    passcode: str = ""  # Optional passcode for authentication
    user_name: str = ""  # Optional user name for authentication


@dataclass(slots=True)
class EventFields:
    """Fields describing an Event Object.

    Used for StoreEvent, GetEvent, and other event-related operations.
    """

    unique_id: str = ""  # Developer-provided unique ID
    id: str = ""  # AIP-generated unique ID with time and location
    local_id: str = ""  # Local machine ID
    owner: str = ""  # Owner ID (default is "$sys")
    owner_unique_id: str = ""  # Owner unique ID
    timestamp: str = ""  # POSIX timestamp in microseconds
    date_time: DateTimeObject | None = None  # Parsed datetime
    location: str = ""  # Location specification (e.g., "TERRA|47.6|-122.5")
    location_separator: str = "|"  # Location delimiter
    type: str = ""  # Developer-defined event type
    tags: list["TagOutput"] = field(default_factory=list)  # Tags for the event
    links: list["LinkFields"] = field(default_factory=list)  # Links for the event
    payload_data: Optional["PayloadFields"] = None  # Payload data
    status: str = ""  # Status of the event; used in StoreBatchEvents response
    hits: int = 0  # Total search term match hits (from GetEventsForTags response)


@dataclass(slots=True)
class PayloadFields:
    """Message payload data and metadata."""

    data: Any = None  # Payload data (string, bytes, or structured data)
    data_type: int = 0  # Bitmap indicating data format/compression
    mime_type: str = ""  # MIME type (e.g., "application/json", "text/plain")
    data_size: int = 0  # Data size in bytes


@dataclass(slots=True)
class GetEventOptions:
    """Options for the GetEvent intent."""

    send_data: bool = False  # Return payload data with MIME type
    local_id_only: bool = False  # Return only local ID
    tag_format: int | None = None  # Tag output format (0 or 1)
    request_format: int = 0  # Output format
    first_link: int = 0  # First link index to retrieve
    link_count: int = 0  # Number of links to return
    get_tags: bool = False  # Return tags for event
    get_links: bool = False  # Send link information in payload
    get_link_tags: bool = False  # Return tags for links
    get_target_tags: bool = False  # Return tags for link targets
    event_facet_filter: str = ""  # Filter event tags by prefix
    link_facet_filter: str = ""  # Filter link tags by prefix
    target_facet_filter: str = ""  # Filter target tags by prefix
    category_filter: str = ""  # Filter by link category
    tag_filter: str = ""  # Regex filter for tags


@dataclass(slots=True)
class GetEventsForTagsOptions:
    """Options for the GetEventsForTags intent."""

    event_pattern: str = ""  # Event key filter (FASTPATTERN)
    event_pattern_high: str = ""  # Event key filter high range
    include_brief_hits: bool = False  # Include only event ID and unique ID
    get_all_data: bool = False  # Get all tag and link data
    first_link: int = 0  # First link to retrieve
    link_count: int = 0  # Number of links to retrieve
    events_per_message: int = 0  # Events per reply message
    start_result: int = 0  # Paging: first result index
    end_result: int = 0  # Paging: last result index
    min_event_hits: int = 0  # Minimum tag matches required
    count_only: bool = False  # Return only match count
    get_match_links: bool = False  # Include number of links
    count_match_links: bool = False  # Return total links per event
    get_link_tags: bool = False  # Return tags for links
    get_target_tags: bool = False  # Return tags for link targets
    link_tag_filter: str = ""  # Filter for link tags
    linked_events_filter: str = ""  # Regex filter for target tags
    link_category: str = ""  # Restrict link results to category
    owner: str = ""  # Filter by owner
    owner_unique_id: str = ""  # Filter by owner unique ID
    get_event_object_count: bool = False  # Request total event count
    buffer_results: bool = False  # Send all results in single message
    include_tag_stats: bool = False  # Include tag statistics
    invert_hit_tag_filter: bool = False  # Invert the hit tag filter
    hit_tag_filter: str = ""  # Filter for result tags
    buffer_format: str = ""  # Output format


@dataclass(slots=True)
class SearchOptions:
    """Programmable search configuration."""

    clause: str = ""  # Search clause specification
    parameters: str = ""  # Search parameters
    buffer_results: bool = False  # Buffer all results in single reply
    include_tag_stats: bool = False  # Include tag statistics
    invert_hit_tag_filter: bool = False  # Invert the hit tag filter
    hit_tag_filter: str = ""  # Filter for result tags
    buffer_format: str = ""  # Output format


@dataclass(slots=True)
class LinkFields:
    """Fields for link operations between events."""

    unique_id: str = ""  # Developer-provided unique ID
    id: str = ""  # AIP-generated unique ID
    local_id: str = ""  # Local machine ID
    owner: str = ""  # Owner ID
    timestamp: str = ""  # Event timestamp
    date_time: DateTimeObject | None = None  # Parsed datetime
    location: str = ""  # Location specification
    location_separator: str = "|"  # Location delimiter
    event_a: str = ""  # Event A ID
    event_b: str = ""  # Event B ID
    unique_id_a: str = ""  # Event A unique ID
    unique_id_b: str = ""  # Event B unique ID
    strength_a: float = 0.0  # Link strength A->B
    strength_b: float = 0.0  # Link strength B->A
    category: str = ""  # Link category
    type: str = ""  # Developer-defined event type
    owner_event_id: str = ""  # Owner event ID (internal Evolutionary Neural Memory ID)
    owner_unique_id: str = ""  # Owner unique ID (developer-provided unique ID)
    tags: list["TagOutput"] = field(default_factory=list)  # Tags for this link
    target_tags: list["TagOutput"] = field(default_factory=list)  # Tags for target
    status: str = ""  # Status of the link; used in StoreBatchLinks response
    message: str = ""  # Message of the link; used in StoreBatchLinks response
    link_error_code: int | None = None  # Error code for link operations; used in StoreBatchLinks response


@dataclass(slots=True)
class NeuralMemoryFields:
    """Evolutionary Neural Memory Actor-specific operations.

    Set only the field relevant to your Intent; others should be None.
    """

    get_event: GetEventOptions | None = None  # Options for GetEvent intent
    get_events_for_tags: GetEventsForTagsOptions | None = None  # Options for GetEventsForTags
    search: SearchOptions | None = None  # Search configuration
    link: LinkFields | None = None  # Single link operation
    batch_links: list["BatchLinkEventSpec"] = field(default_factory=list)  # Batch links
    tags: list["Tag"] = field(default_factory=list)  # Tags to store with an event
    batch_events: list["BatchEventSpec"] = field(default_factory=list)  # Batch events


@dataclass(slots=True)
class ResponseFields:
    """Data populated when decoding response messages.

    These fields are never set by the caller; they are filled by decoder.
    """

    status: str = ""  # Processing status: "OK" or "ERROR"
    message: str = ""  # Status description or error message
    type: str = ""  # Response type (for ActorResponse, Status intents)
    tag_count: int = 0  # Number of tags in response
    link_count: int = 0  # Total number of links found
    link_id: str = ""  # Link ID returned by LinkEventResponse
    date_time: DateTimeObject | None = None  # Parsed event datetime
    total_events: int = 0  # Total number of events found or stored
    returned_events: int = 0  # Number of events returned in response
    start_result: int = -1  # Paging: first result index (-1 if not set)
    end_result: int = -1  # Paging: last result index (-1 if not set)
    storage_error_count: int = 0  # Number of storage errors
    storage_success_count: int = 0  # Number of successfully stored events
    event_records: list["EventFields"] = field(default_factory=list)  # Parsed events
    store_link_batch_event_record: Optional["StoreLinkBatchEventRecord"] = None  # Link batch results
    store_batch_event_record: Optional["StoreBatchEventRecord"] = None  # Batch event results
    match_term_count: int = 0  # Number of matching tag values
    is_buffered: bool = False  # Whether response is buffered
    brief_hits: list["BriefHitRecord"] = field(default_factory=list)  # Brief hit records


@dataclass(slots=True)
class StoreBatchEventRecord:
    """Batch event storage result."""

    status: str = ""
    message: str = ""
    event_count: int = 0  # Total number of Events stored
    event_results: list["EventFields"] = field(default_factory=list)  # Event results


@dataclass(slots=True)
class StoreLinkBatchEventRecord:
    """Batch link storage result."""

    status: str = ""
    message: str = ""
    total_link_requests_found: int = 0  # Total link requests found
    links_ok: int = 0  # Number of links successfully stored
    links_with_errors: int = 0  # Number of links with errors
    link_results: list["LinkFields"] = field(default_factory=list)  # Link results


@dataclass(slots=True)
class BriefHitRecord:
    """Brief hit result from GetEventsForTags."""

    event_id: str = ""  # Event ID
    total_hits: int = 0  # Total number of search term match hits


@dataclass(slots=True)
class Message:
    """Actor message using composition for clarity.

    The Message struct represents two use cases:
    (1) sending a message to an Actor
    (2) processing a response message from an Actor

    The envelope is embedded for convenient access to core routing fields.
    """

    # Core routing fields (embedded from Envelope)
    to: str = ""
    from_: str = ""
    intent: str = ""
    client_name: str = ""
    message_id: str = ""
    passcode: str = ""
    user_name: str = ""

    # Event metadata (None for non-event operations)
    event: EventFields | None = None

    # Payload data (None if no payload)
    payload: PayloadFields | None = None

    # Evolutionary Neural Memory Actor operations (None for Gateway-only messages)
    neural_memory: NeuralMemoryFields | None = None

    # Response data (populated by decoder, None for requests)
    response: ResponseFields | None = None

    def event_id(self) -> str:
        """Return the Event.id or empty string if Event is None."""
        return self.event.id if self.event else ""

    def event_unique_id(self) -> str:
        """Return the Event.unique_id or empty string if Event is None."""
        return self.event.unique_id if self.event else ""

    def payload_data(self) -> Any:
        """Return the Payload.data or None if Payload is None."""
        return self.payload.data if self.payload else None

    def payload_mime_type(self) -> str:
        """Return the Payload.mime_type or empty string if Payload is None."""
        return self.payload.mime_type if self.payload else ""

    def processing_status(self) -> str:
        """Return the Response.status or empty string if Response is None."""
        return self.response.status if self.response else ""

    def processing_message(self) -> str:
        """Return the Response.message or empty string if Response is None."""
        return self.response.message if self.response else ""


@dataclass(slots=True)
class BatchEventSpec:
    """Single event specification for batch storage."""

    event: EventFields
    tags: list["Tag"] = field(default_factory=list)


@dataclass(slots=True)
class BatchLinkEventSpec:
    """Single link specification for batch linking."""

    event: EventFields
    link: LinkFields


@dataclass(slots=True)
class Tag:
    """Piece of important data for an Event Object.

    This is a Facet construction extending tagvalue into key/value structure.
    """

    frequency: int = 0  # Count of occurrences
    key: str = ""  # Tag key/category
    value: Any = None  # Supports string, int, float, bool, map, slice, JSON objects
    timestamp: str = ""  # Event timestamp POSIX timestamp
    id: str = ""  # Tag's Event Object ID
    owner: str = ""  # Owner ID
    owner_unique_id: str = ""  # Owner unique ID (e.g. backing Observation Event Object)

    def string_value(self) -> tuple[str, bool]:
        """Return the Value as a string."""
        if isinstance(self.value, str):
            return self.value, True
        if self.value is None:
            return "", False
        return str(self.value), False

    def int_value(self) -> tuple[int, bool]:
        """Return the Value as an int."""
        if isinstance(self.value, (int, float)):
            return int(self.value), True
        return 0, False

    def float_value(self) -> tuple[float, bool]:
        """Return the Value as a float."""
        if isinstance(self.value, (int, float)):
            return float(self.value), True
        return 0.0, False

    def bool_value(self) -> tuple[bool, bool]:
        """Return the Value as a bool."""
        if isinstance(self.value, bool):
            return self.value, True
        return False, False


# Type aliases
TagList = list[Tag]


@dataclass(slots=True)
class TagOutput:
    """Parsed tag from response payload."""

    frequency: int = 0
    category: str = ""
    key: str = ""
    value: str = ""
    owner: str = ""
    timestamp: str = ""
    target_tag_id: str = ""  # ID of the target tag


@dataclass(slots=True)
class SearchProgram:
    """Search program configuration."""

    search_clause: list[Any] = field(default_factory=list)
    search_parameters: str = ""
    search_results: str = ""
    buffer_results: bool = False
    include_tag_stats: bool = False
    invert_hit_tag_filter: bool = False
    hit_tag_filter: str = ""
