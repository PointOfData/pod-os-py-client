"""Pod-OS intent types and intent mapping."""

from dataclasses import dataclass

__all__ = ["Intent", "IntentType", "intent_from_command", "intent_from_message_type"]


@dataclass(frozen=True, slots=True)
class Intent:
    """Represents an intent type for the Pod-OS system."""

    name: str  # Friendly Pod-OS name for the intent
    routing_message_type: str  # Defines message_type name for routing
    neural_memory_command: str = ""  # Command to send to Evolutionary Neural Memory Actor
    message_type: int = 0  # Message type integer set in message header


class _IntentTypes:
    """Container for all Pod-OS intent types."""

    # Evolutionary Neural Memory Request intents
    StoreEvent = Intent(
        # StoreEvent is used to store a single Event Object in a Evolutionary Neural Memory database.
        name="StoreEvent",
        neural_memory_command="store",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    StoreData = Intent(
        #StoreData is used to update a new Payload data in an *existing* Event Object identified by UniqueId or Id. When invoked, the previous Data Payload is overwritten.
        name="StoreData",
        neural_memory_command="store_data",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    StoreBatchEvents = Intent(
        # StoreBatchEvents is used to store a batch of Event Objects (including tags) in a Evolutionary Neural Memory database.
        name="StoreBatchEvents",
        neural_memory_command="store_batch",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    StoreBatchTags = Intent(
        #StoreBatchTags is used to store a batch of tag objects in an existing Event Object in a Evolutionary Neural Memory database. Also covers the update use case.
        name="StoreBatchTags",
        neural_memory_command="tag_store_batch",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    GetEvent = Intent(
        # GetEvent is used to retrieve a single Event Object from a Evolutionary Neural Memory database. Use GetTags=true to retrieve tags for the event.
        name="GetEvent",
        neural_memory_command="get",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    GetEventsForTags = Intent(
        # GetEventsForTags is used to retrieve a batch of Event Objects from a Evolutionary Neural Memory database by searching for Tags matching the specified pattern.
        name="GetEventsForTags",
        neural_memory_command="events_for_tag",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    LinkEvent = Intent(
        # LinkEvent is used to link two Event Objects in a Evolutionary Neural Memory database. It is also an Event Object itself.
        name="LinkEvent",
        neural_memory_command="link",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    UnlinkEvent = Intent(
        # UnlinkEvent is used to unlink two Event Objects in a Evolutionary Neural Memory database.
        name="UnlinkEvent",
        neural_memory_command="unlink",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    StoreBatchLinks = Intent(
        # StoreBatchLinks is used to store a batch of Link Objects in a Evolutionary Neural Memory database.
        name="StoreBatchLinks",
        neural_memory_command="link_batch",
        message_type=1000,
        routing_message_type="MEM_REQ",
    )
    # Evolutionary Neural Memory Response intents
    StoreEventResponse = Intent(
        # StoreEventResponse is used to confirm the storage of a single Event Object in a Evolutionary Neural Memory database.
        name="StoreEventResponse",
        neural_memory_command="store",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    StoreDataResponse = Intent(
        # StoreDataResponse is used to confirm the storage of a new Payload data in an *existing* Event Object identified by UniqueId or Id. When invoked, the previous Data Payload is overwritten.
        name="StoreDataResponse",
        neural_memory_command="store_data",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    StoreBatchEventsResponse = Intent(
        # StoreBatchEventsResponse is used to confirm the storage of a batch of Event Objects (including tags) in a Evolutionary Neural Memory database.
        name="StoreBatchEventsResponse",
        neural_memory_command="store_batch",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    StoreBatchTagsResponse = Intent(
        # StoreBatchTagsResponse is used to confirm the storage of a batch of tag objects (associated with an existing Event Object) in a Evolutionary Neural Memory database.
        name="StoreBatchTagsResponse",
        neural_memory_command="tag_store_batch",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    GetEventResponse = Intent(
        # GetEventResponse is used to confirm the retrieval of a single Event Object from a Evolutionary Neural Memory database
        name="GetEventResponse",
        neural_memory_command="get",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    GetEventsForTagsResponse = Intent(
        # GetEventsForTagsResponse is used to confirm the retrieval of a batch of Event Objects from a Evolutionary Neural Memory database by searching for Tags.
        name="GetEventsForTagsResponse",
        neural_memory_command="events_for_tag",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    LinkEventResponse = Intent(
        # LinkEventResponse is used to link two Event Objects in a Evolutionary Neural Memory database. It is also an Event Object itself.
        name="LinkEventResponse",
        neural_memory_command="link",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    UnlinkEventResponse = Intent(
        # UnlinkEventResponse is used to unlink two Event Objects in a Evolutionary Neural Memory database.
        name="UnlinkEventResponse",
        neural_memory_command="unlink",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )
    StoreBatchLinksResponse = Intent(
        # StoreBatchLinksResponse is used to store a batch of link objects in a Evolutionary Neural Memory database.
        name="StoreBatchLinksResponse",
        neural_memory_command="link_batch",
        message_type=1001,
        routing_message_type="MEM_REPLY",
    )

    # Gateway/Actor intents
    # ActorEcho is used to echo a message from the Actor to the client.
    ActorEcho = Intent(name="ActorEcho", message_type=2, routing_message_type="ECHO")
    # ActorHalt is used to halt the Actor.
    ActorHalt = Intent(name="ActorHalt", message_type=99, routing_message_type="HALT")
    # ActorStart is used to start an Actor.
    ActorStart = Intent(name="ActorStart", message_type=1, routing_message_type="START")
    # Status is used to communicate status; optionally rely on MessageId to identify the status.
    Status = Intent(name="Status", message_type=3, routing_message_type="STATUS")
    # StatusRequest is used to request the status of an Actor.
    StatusRequest = Intent(
        name="StatusRequest", message_type=110, routing_message_type="STATUS_REQ"
    )
    # ActorRequest is a request sent to an Actor.
    ActorRequest = Intent(name="ActorRequest", message_type=4, routing_message_type="REQUEST")
    # ActorResponse is a response sent from an Actor in response to an ActorRequest.
    ActorResponse = Intent(name="ActorResponse", message_type=30, routing_message_type="REPLY")
    # GatewayId is used by a client to identify the connection (required for all messages and connections) and establish client authentication and authorization.
    GatewayId = Intent(name="GatewayId", message_type=5, routing_message_type="ID")
    # GatewayDisconnect is used to disconnect a client from a Gateway.
    GatewayDisconnect = Intent(
        name="GatewayDisconnect", message_type=6, routing_message_type="DISCONNECT"
    )
    # GatewaySendNext is used to send the next message from the Actor to the client.
    GatewaySendNext = Intent(name="GatewaySendNext", message_type=7, routing_message_type="NEXT")
    # GatewayNoSend is used to tell the Actor to not send the next message to the client.
    GatewayNoSend = Intent(name="GatewayNoSend", message_type=8, routing_message_type="NO_SEND")
    # GatewayStreamOff is used to turn off the streaming of messages from the Actor to the client.
    GatewayStreamOff = Intent(
        name="GatewayStreamOff", message_type=9, routing_message_type="STREAM_OFF"
    )
    # GatewayStreamOn is used to turn on the streaming of messages from the Actor to the client.
    GatewayStreamOn = Intent(
        name="GatewayStreamOn", message_type=10, routing_message_type="STREAM_ON"
    )
    # ActorRecord is used to record a message from the client to the Actor.
    ActorRecord = Intent(name="ActorRecord", message_type=11, routing_message_type="RECORD")
    # GatewayBatchStart is used to start a batch of messages from the client to the Actor.
    GatewayBatchStart = Intent(
        name="GatewayBatchStart", message_type=12, routing_message_type="BATCH_START"
    )
    # GatewayBatchEnd is used to end a batch of messages from the client to the Actor.
    GatewayBatchEnd = Intent(
        name="GatewayBatchEnd", message_type=13, routing_message_type="BATCH_END"
    )

    # Queue intents
    # QueueNextRequest is a request for the next queued message.
    QueueNextRequest = Intent(
        name="QueueNextRequest", message_type=14, routing_message_type="QUEUE_NEXT"
    )
    # QueueAllRequest is a request for all queued messages.
    QueueAllRequest = Intent(
        name="QueueAllRequest", message_type=15, routing_message_type="QUEUE_ALL"
    )
    # QueueCountRequest is a request for the count of queued messages.
    QueueCountRequest = Intent(
        name="QueueCountRequest", message_type=16, routing_message_type="QUEUE_COUNT"
    )
    # QueueEmpty is sent in response to next message if the queue is empty (no more messages).
    QueueEmpty = Intent(name="QueueEmpty", message_type=17, routing_message_type="QUEUE_EMPTY")
    # Keepalive is used for connection keepalive.
    Keepalive = Intent(name="Keepalive", message_type=18, routing_message_type="KEEPALIVE")

    # Report intents
    # ActorReport is used to report the status of an Actor.
    ActorReport = Intent(name="ActorReport", message_type=19, routing_message_type="REPORT")
    # ReportRequest is used to request a report.
    ReportRequest = Intent(
        name="ReportRequest", message_type=20, routing_message_type="REPORT_REQUEST"
    )
    # InformationReport is an information report response.
    InformationReport = Intent(
        name="InformationReport", message_type=21, routing_message_type="INFO_REPORT"
    )

    # Auth intents
    # AuthAddUser is used to add a user to the auth database.
    AuthAddUser = Intent(name="AuthAddUser", message_type=100, routing_message_type="AUTH_ADD_USER")
    # AuthUpdateUser is used to update a user in the auth database.
    AuthUpdateUser = Intent(
        name="AuthUpdateUser", message_type=101, routing_message_type="AUTH_UPDATE_USER"
    )
    # AuthUserList is used to request the user list from the auth database.
    AuthUserList = Intent(
        name="AuthUserList", message_type=102, routing_message_type="AUTH_USER_LIST"
    )
    # AuthDisableUser is used to disable a user in the auth database.
    AuthDisableUser = Intent(
        name="AuthDisableUser", message_type=103, routing_message_type="AUTH_DISABLE_USER"
    )

    # User intent
    # ActorUser is used for user-defined intents and messages. Any value at or above 65536 is a user intent.
    ActorUser = Intent(name="ActorUser", message_type=65536, routing_message_type="USER")

    # Routing intents
    # RouteAnyMessage is used to match any kind of message.
    RouteAnyMessage = Intent(name="RouteAnyMessage", routing_message_type="ANY")
    # RouteUserOnlyMessage is used to match only user-level messages.
    RouteUserOnlyMessage = Intent(name="RouteUserOnlyMessage", routing_message_type="USERONLY")


# Singleton instance
IntentType = _IntentTypes()

# Mapping: NeuralMemoryCommand -> Request Intent
_COMMAND_TO_INTENT: dict[str, Intent] = {
    "store": IntentType.StoreEvent,
    "store_data": IntentType.StoreData,
    "store_batch": IntentType.StoreBatchEvents,
    "tag_store_batch": IntentType.StoreBatchTags,
    "get": IntentType.GetEvent,
    "events_for_tag": IntentType.GetEventsForTags,
    "link": IntentType.LinkEvent,
    "unlink": IntentType.UnlinkEvent,
    "link_batch": IntentType.StoreBatchLinks,
}

# Mapping: NeuralMemoryCommand -> Response Intent
_COMMAND_TO_RESPONSE_INTENT: dict[str, Intent] = {
    "store": IntentType.StoreEventResponse,
    "store_data": IntentType.StoreDataResponse,
    "store_batch": IntentType.StoreBatchEventsResponse,
    "tag_store_batch": IntentType.StoreBatchTagsResponse,
    "get": IntentType.GetEventResponse,
    "events_for_tag": IntentType.GetEventsForTagsResponse,
    "events_for_tags": IntentType.GetEventsForTagsResponse,  # Handle both variants
    "link": IntentType.LinkEventResponse,
    "unlink": IntentType.UnlinkEventResponse,
    "link_batch": IntentType.StoreBatchLinksResponse,
}

# Mapping: MessageType -> Intent (for non-Evolutionary Neural Memory intents)
_MESSAGE_TYPE_TO_INTENT: dict[int, Intent] = {
    1: IntentType.ActorStart,
    2: IntentType.ActorEcho,
    3: IntentType.Status,
    4: IntentType.ActorRequest,
    5: IntentType.GatewayId,
    6: IntentType.GatewayDisconnect,
    7: IntentType.GatewaySendNext,
    8: IntentType.GatewayNoSend,
    9: IntentType.GatewayStreamOff,
    10: IntentType.GatewayStreamOn,
    11: IntentType.ActorRecord,
    12: IntentType.GatewayBatchStart,
    13: IntentType.GatewayBatchEnd,
    14: IntentType.QueueNextRequest,
    15: IntentType.QueueAllRequest,
    16: IntentType.QueueCountRequest,
    17: IntentType.QueueEmpty,
    18: IntentType.Keepalive,
    19: IntentType.ActorReport,
    20: IntentType.ReportRequest,
    21: IntentType.InformationReport,
    30: IntentType.ActorResponse,
    99: IntentType.ActorHalt,
    100: IntentType.AuthAddUser,
    101: IntentType.AuthUpdateUser,
    102: IntentType.AuthUserList,
    103: IntentType.AuthDisableUser,
    110: IntentType.StatusRequest,
    65536: IntentType.ActorUser,
}

# Mapping: Intent name -> Intent object
_NAME_TO_INTENT: dict[str, Intent] = {
    intent.name: intent
    for intent in vars(_IntentTypes).values()
    if isinstance(intent, Intent)
}


def intent_from_command(command: str) -> Intent | None:
    """Return the Intent corresponding to the given command string (request).

    Args:
        command: Evolutionary Neural Memory command string (e.g., "store", "get")

    Returns:
        The matching Intent or None if not found
    """
    return _COMMAND_TO_INTENT.get(command)


def intent_from_response_command(command: str) -> Intent | None:
    """Return the Response Intent corresponding to the given command string.

    Args:
        command: Evolutionary Neural Memory command string (e.g., "store", "get")

    Returns:
        The matching Response Intent or None if not found
    """
    return _COMMAND_TO_RESPONSE_INTENT.get(command)


def intent_from_message_type_and_command(message_type: int, command: str) -> Intent | None:
    """Return the correct Intent based on MessageType and command.

    For MEM_REQ (1000), returns request intents.
    For MEM_REPLY (1001), returns response intents.
    For other message types, falls back to message type lookup.

    Args:
        message_type: Message type integer
        command: Evolutionary Neural Memory command string

    Returns:
        The matching Intent or None if not found
    """
    if message_type == 1000:  # MEM_REQ
        return intent_from_command(command)
    elif message_type == 1001:  # MEM_REPLY
        return intent_from_response_command(command)
    elif message_type == 11:  # RECORD
        intent = intent_from_response_command(command)
        if intent:
            return intent
        return _MESSAGE_TYPE_TO_INTENT.get(message_type)
    else:
        return _MESSAGE_TYPE_TO_INTENT.get(message_type)


def intent_from_message_type(message_type: int | str) -> Intent | None:
    """Return the Intent corresponding to the given messageType.

    Accepts either an int (MessageType) or a string (NeuralMemoryCommand or Intent name).

    Args:
        message_type: Either an integer message type, command string, or intent name

    Returns:
        The matching Intent or None if not found
    """
    if isinstance(message_type, str):
        # Check if it's an intent name first
        if intent := _NAME_TO_INTENT.get(message_type):
            return intent
        # Fall back to command lookup
        return intent_from_command(message_type)
    elif isinstance(message_type, int):
        return _MESSAGE_TYPE_TO_INTENT.get(message_type)
    return None


# Routing Test Types
class RoutingTestType:
    """Routing test type constants."""

    NONE = "NONE"
    EQ = "EQ"
    NE = "NE"
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"
    RANGE = "range"
    EXCL = "excl"
    REGEXP = "regexp"
    NUM_EQ = "#EQ"
    NUM_NE = "#NE"
    NUM_LT = "#LT"
    NUM_LE = "#LE"
    NUM_GT = "#GT"
    NUM_GE = "#GE"
    NUM_RANGE = "#RANGE"
    NUM_EXCL = "#EXCL"


# Routing Action Types
class RoutingActionType:
    """Routing action type constants."""

    NONE = "NONE"
    ROUTE = "ROUTE"
    DISCARD = "DISCARD"
    CHANGE = "CHANGE"
    DUPLICATE = "DUPLICATE"
