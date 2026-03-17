## Neural Memory Database Manages Memory Events and Relationships

Pod-OS, uniquely, provides a Neural Memory Database that has the following behavioral characteristics: acquiring (encoding), stabilizing (consolidation), and retrieving information, and forming engrams (memory traces) within groups of Events. Key characteristics include its large storage capacity with decreasing marginal storage volume, native version management learning and ease, and ability to inter-link and describe any and all Event Objects using weights or activation functions, action policies, or other objective function methods. The Neural Memory DB's central thesis is that each moment in time captures, and processes important context that software, and the most advanced, complex and adaptive AIs and robotics require. Including LLMs, RAG, robotics, World Models, and other advanced AI and robotics applications. Neural Memory provides capture three memory behaviors that are interrelated: long-term memory (facts and experiences), short-term memory (actions, rewards, variables, policies, cognition, reasoning and beliefs), and real-time state (continuous snapshot of necessary info (for example, positions, sensor readings, game status) for decision-making). It is a natural fit for Neuro-Symbolic AI, and other memory structures.

The Neural Memory Database uses three primitives:
1. **Event Objects**: An Event Object is a uniquely identified datum (from any source) which is used as a base reference for a set of versioned attributes and context bound weighted links to other event objects. Event Objects carry crucial context information including time and location, owner, encryption, message source as actor@gateway, message destination actor@gateway, and payload MIME and binary data.
2. **Tags**: Tags are values that describe important information about the Event. There are multiple design options. The simplest design option is to use frequency=tagvalue. Frequency is an integer that describes the number of times the Tag has been applied to the Event. Tagvalue is a string or integer or float or embedding or binary data or other type that describes the value of the Tag. A powerful design option is to use Facets which are key/value pairs of any type in the format of frequency=key_name=key_value. More complex designs are possible. For example, a tag value can be a hash of the Event Object, a pointer to the Event Object, a binary data blob or a hierarchical string or integers or floats or embeddings or other type that describes the value of the Tag. What is required is that the Tag value can be searched for and retrieved using the Tag value following the guidance in the Retrieval/Search Guidance section.
3. **Link Objects**: Links connect any two Events (including Link Event), but as Links are Events themselves, also carry the Event Object and Tag descriptions along with weights (integer or continuous function).

Neural Memory uses Tags to implicitly associate events by Tag name, time, and location. Neural Memory uses links to explicitly associate events.

By combining Links and Tags, complex data structures and sets of related events can be created depending on the objective. For example, the Neural Memory Database can capture neural memories and semantic memories; can use Tags and Links to form short and long-term memories; and can use Links and Tags to form short and long-term relationships between events. In other data storage examples, the Neural Memory Database can be used to create a knowledge graph, a semantic network, or a graph of related events; the Neural Memory Database can also be used to mimic the behavior of a relational database such as SQL, a document database, or a graph database. In other examples, the Neural Memory Database can be used to encode in data structures a neural network (e.g., FNN, CNN, RNN, LSTM, GRU), transformers, a genetic algorithm, or a reinforcement learning model.

Links and tags can be defined independently of the database actually containing the original event definition, permitting the distribution of data across servers or database files. Retrieval of the actual event may require a request to other database handlers (or a router which understands that event requests need to be distributed to a given set of handlers), but there is no requirement for the actual event to be recorded within a database in which tags are placed. While this can cause data concurrency challenges, it also permits explicit segregation where it is required (such as a security application, or private analytical data associated with public information).

Pod-OS uses specific types (`pod_os_client.message.types`) to manage communication with the Actor. All Event Message interactions use a Request/Response pair either in synchronous (STREAMING ON) or asynchronous mode (STREAMING OFF). The Actor always returns a Response to the client's request. Depending on the implementation, the client may choose to use the synchronous or asynchronous mode; and needs to handle Message management accordingly.

The Actor Response carries crucial information that may be remembered depending on the operation.

### Store Event Object Efficiency Guidance

- When multiple Event Objects need to be created, strongly prefer to use StoreBatchEvents Intent as it is more efficient; this can also accept Tags as part of the batch.
- When using StoreBatchEvents, optimize batch size to minimize network overhead and latency; Neural Memory DB's storage performance does not increase linearly with batch size; storage performance is best with larger batch sizes (e.g., 10,000 - 100,000 events per batch). On a single board computer with 1GB of RAM, the optimal batch size is 10,000 events; setting a response timeout of 3 minutes.
- When a single Event Object is created, prefer to add the Tags in StoreEvent Intent as it is more efficient.
- When adding Tags prefer to use StoreBatchTags Intent.

### Retrieval/Search Guidance

See Pod-OS-Neural-Memory-Retrieval-Prompts.md.

### Ownership Guidance

Ownership is overloaded with two meanings:
1. The EventOwner is the EventId or EventUniqueId representing the entity that created the Event Object.
2. RBAC (Role-Based Access Control) ownership is defined elsewhere and is not part of the Event Owner.

### Reference Guidance

- Internally, all communication about Event Objects and Link Objects uses the EventId or EventUniqueId field for reference. The EventId is created by the Actor when the Event Object is stored. As such, the EventId is the primary reference for all Event Objects and Link Objects. EventUniqueId is a very useful developer-set customer ID for external reference by the developer.
- MessageId can be used by client applications to track the message and conversation flow.

### Design Patterns

These are optional design patterns that can be used to create complex data structures and sets of related events.
- **Sharding**: Separate Event Objects into each shard using Routing rules, retrieve by filtering on Tag values using GetEventsForTags Intent for each Service shard.
- **Replication**: Duplicate Event Objects by creating a Link Object to the original Event Object.
- **Relational data structure**: a relational database table can be simulated by creating a table Event Object, and an Event Object for each row, and for each row a series of column Event Objects. Associate all Event Objects together in a hierarchy using Link Objects. Create Links to the table from each row, and from the events making up the columns in a specific row to that row event. Since links are themselves a special type of event, they can be assigned tag values and linked to other events.
- Retrieval Augmented Generation: [to be completed]
- Knowledge Graph: [to be completed]

### Storing Events

Events are stored as a single Event Object [StoreEvent Intent type] or as a batch of Event Objects [StoreBatchEvents Intent type]. Data can also be stored directly using the StoreData Intent which omits tags and is intended for associating raw payload data with a unique identifier, timestamp, and location.

#### Rules

Event Creation must follow these rules.

- The Event object must exist in the Neural Memory database store before any associated StoreBatchTags Intents or LinkEvents Intents are created.
- The definition of exist: the Actor responded with status 'OK' when the Event Object is stored or the Event Object is retrieved.
- For any EventOwner other than '$sys' (representing system-level creation) the EventOwner EventId or EventUniqueId must exist in the Neural Memory database; the Event Owner is only the EventId provided in the Response.
- The EventOwner may be an internal EventID or an EventUniqueId returned by the Actor's response (found in the decoded Message). MessageId are not used. MessageId is used for tracking the message and conversation flow.
- EventUniqueId is a useful developer-set customer ID for external reference by the developer.

The EventId returned from the Actor is formatted using the system delimiter, which is ASCII character 1 (0x01). The format is always: "timestamp delim loc segment 1 delim loc segment 2 delim .... loc segment N"

The timestamp is always the number of seconds and microseconds since Jan 1, 1970 (a negative value indicates a time prior to this date). The location segments are always in the order supplied by the event creator.

When EventId is sent as part of a Request, the format is always the same as Actor's Response EventId. The time stamp is always formatted as a 16-position floating-point value, where there are ten digits to the left of the decimal and six to the right, and a sign indicator is always used (positive or negative). Both the decimal and whole number portions are prefixed with zeros as necessary.

The PayloadData may be any data to be stored as part of the event, up to 2 GB in size. This data may not be altered in the future.

#### Example Pod-OS Store Event (Python)

```python
from uuid import uuid4
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, EventFields, PayloadFields
from pod_os_client.message.constants import DataType

domain_name = "zeroth.example.com"
client_name = "PodOSDashboardNode"

msg = Message(
    to=f"administration@zeroth.{domain_name}",
    from_=f"{client_name}@zeroth.{domain_name}",
    client_name=client_name,
    message_id=str(uuid4()),
    intent=IntentType.StoreEvent.name,
    event=EventFields(
        owner="[EventID from the Base Event]",
        unique_id=str(uuid4()),
        timestamp="1705327845123456",  # or your timestamp
        location="TERRA|47.619463|-122.518691",
        location_separator="|",
        type="system log object",
    ),
    payload=PayloadFields(
        data="System initialization log",
        mime_type="text/plain",
        data_type=DataType.RAW,
    ),
)
```

#### Example Pod-OS StoreBatchEvents (Python)

Use `format_batch_events_payload` from the encoder and `BatchEventSpec` / `EventFields`:

```python
from uuid import uuid4
from pod_os_client.message.encoder import format_batch_events_payload
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    Message,
    EventFields,
    PayloadFields,
    BatchEventSpec,
)
from pod_os_client.message.constants import DataType

domain_name = "zeroth.example.com"
client_name = "PodOSDashboardNode"

batch_specs = [
    BatchEventSpec(
        event=EventFields(
            unique_id=str(uuid4()),
            owner="$sys",
            timestamp="1705327845123456",
            location="TERRA|47.619463|-122.518691",
            location_separator="|",
            type="system log object",
        ),
    ),
]
payload_str = format_batch_events_payload(batch_specs)

msg = Message(
    to=f"administration@zeroth.{domain_name}",
    from_=f"{client_name}@zeroth.{domain_name}",
    client_name=client_name,
    message_id=str(uuid4()),
    intent=IntentType.StoreBatchEvents.name,
    payload=PayloadFields(
        data=payload_str,
        mime_type="text/plain",
        data_type=DataType.RAW,
    ),
)
```

The formatted payload contains newline-terminated records. Each line is tab-separated fields. Required event fields: `unique_id`, `owner` (or `owner_unique_id`), `timestamp`, `loc` (location), `loc_delim` (location separator), `type`. Optionally append tags per line as `tag:frequency:key=value` or `tag:value`. Facets: `tag:frequency:key_name=key_value`.

### Storing Tags

New Tags are stored with the Event [StoreEvent Intent type] or as a batch of Tags [StoreBatchTags Intent type]. Tags can be applied to any Event including Linking Events. An indexed tag may be up to 1,000 bytes in length and must be terminated by a null (zero) byte for purposes of storage and retrieval (internally, the zero byte is discarded). Tags have an associated frequency which is a positive, non-zero 64-bit integer. If an existing tag is re-stored with a negative frequency, it is considered inactive and will not be returned in subsequent searches. If a tag is stored with a frequency of zero, the Neural Memory DB service stores it outside of the index just as an attached value. Tags have no specific formatting requirements aside from the null byte termination. Tags may be "owned" by an event, in which case they can be found only via searches where the owner event ID is provided. This permits for "private" sets of tags to be associated with an event. Event ID "$sys" indicates that the tags are associated with the "system", and are therefore accessible to public searches where no owner is specified.

#### Rules

- Frequency field (int) is used to track the number of instances of the Tag.
- Key field: can be any alphanumeric value used to identify the Tag. Examples include: text (e.g., topic:quantum_mechanics), dense or sparse embedding vectors, hash, and pointers (e.g., actor@gateway:EVENTID).
- Value field: can be any value as the Tag value. Examples include: text, dense or sparse embedding vector, hash, pointers or binary data.
- Values are automatically versioned; by default the most recent is returned during retrieval.
- There is no upper bound on the number of Tags an Event can have; however, the greater the number the slower the storage and retrieval latencies and therefore the maximum number of Tags is a tunable hyperparameter based on the use case and latency requirements.

#### Example: StoreEvent with Tags (Python)

```python
from uuid import uuid4
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, EventFields, PayloadFields, NeuralMemoryFields, Tag
from pod_os_client.message.constants import DataType

domain_name = "zeroth.example.com"
client_name = "PodOSDashboardNode"

system_log_tag_list = [
    Tag(frequency=1, key="domain", value=domain_name),
    Tag(frequency=1, key="log_type", value="system"),
    Tag(frequency=1, key="severity", value="INFO"),
    Tag(frequency=1, key="component", value="pod-os-core"),
    Tag(frequency=1, key="timestamp", value="1705327845123456"),
]

msg = Message(
    to=f"administration@zeroth.{domain_name}",
    from_=f"{client_name}@zeroth.{domain_name}",
    client_name=client_name,
    message_id=str(uuid4()),
    intent=IntentType.StoreEvent.name,
    event=EventFields(
        owner="[EventID from the Base Event]",
        unique_id=str(uuid4()),
        timestamp="1705327845123456",
        location="TERRA|47.619463|-122.518691",
        location_separator="|",
        type="system log object",
    ),
    payload=PayloadFields(
        data="System initialization log",
        mime_type="text/plain",
        data_type=DataType.RAW,
    ),
    neural_memory=NeuralMemoryFields(tags=system_log_tag_list),
)
```

#### Example: StoreBatchTags (Python)

Use `format_batch_tags_payload` and a payload of newline-terminated lines `frequency=tagvalue` or `frequency=key_name=key_value` for facets:

```python
from uuid import uuid4
from pod_os_client.message.encoder import format_batch_tags_payload
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import Message, PayloadFields, NeuralMemoryFields, Tag, EventFields
from pod_os_client.message.constants import DataType

domain_name = "zeroth.example.com"
client_name = "PodOSDashboardNode"

msg = Message(
    to=f"administration@zeroth.{domain_name}",
    from_=f"{client_name}@zeroth.{domain_name}",
    client_name=client_name,
    message_id=str(uuid4()),
    intent=IntentType.StoreBatchTags.name,
    event=EventFields(owner="[EventOwnerId]", id="[EventId]"),
    payload=PayloadFields(
        data=format_batch_tags_payload([
            Tag(frequency=10, value="the"),
            Tag(frequency=12, value="then"),
            Tag(frequency=100, value="and"),
        ]),
        mime_type="text/plain",
        data_type=DataType.RAW,
    ),
)
```

### Storing Data

Data is stored directly in the Neural Memory database [StoreData Intent type]. Unlike StoreEvent, StoreData does not include tags. It is used for associating raw payload data with a unique identifier, timestamp, and location.

#### Required fields:
- Envelope: To, From, Intent
- EventFields: unique_id OR id, timestamp, location, location_separator
- PayloadFields: data, mime_type

#### Example:
```python
from uuid import uuid4
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import EventFields, Message, PayloadFields
from pod_os_client.message.utils import get_timestamp

msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.StoreData.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    event=EventFields(
        unique_id=str(uuid4()),
        timestamp=get_timestamp(),
        location="TERRA|47.619463|-122.518691",
        location_separator="|",
    ),
    payload=PayloadFields(data=b"binary or text content", mime_type="application/octet-stream"),
)
response = await client.send_message(msg)
```

### Linking Events

Links are created [LinkEvent Intent type] between any two Event Objects. Links are intended to create networks of explicitly associated events, where the strength of an association (float value) can be set. Two strength values are used so that in cases where there is a many-to-many relationship, the link strength can be set differently depending on the direction of traversal. Links are Event Objects and may be treated as such, which means that Tags may be applied to the Links themselves for future use in Retrievals based on Tag values. It also means that Links can be used to create complex data structures and sets of related events including Links to Links.

All links are organized into sets, referred to as "categories" in Pod-OS. The intent of categories is to create groups of related links based on usage or type. There may be multiple links between the same events, so long as the links are in separate categories. A category is simply a name stored as a string of characters with a null (zero) byte terminator. There is no central directory or list of categories, though one can certainly be created within a database if desired.

#### Rules

- An Event may be a Storage Event or a Link Event; therefore linking between Links or Link to Store Event or any combination is a valid operation.
- There is no upper bound on the number of Links between Event Objects.
- Category value can be any null-terminated ASCII character string.

#### Example: LinkEvent (Python)

```python
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    Message,
    EventFields,
    NeuralMemoryFields,
    LinkFields,
)
from pod_os_client.message.constants import DataType

msg = Message(
    to=f"account@zeroth.{domain_name}",
    from_=f"{client_name}@zeroth.{domain_name}",
    client_name=client_name,
    message_id=str(uuid4()),
    intent=IntentType.LinkEvent.name,
    event=EventFields(
        owner="[EventOwnerId]",
        unique_id=str(uuid4()),
        timestamp="1705327845123456",
        location="TERRA|47.619463|-122.518691",
        location_separator="|",
        type="account link admin account to admin group",
    ),
    payload=PayloadFields(data=None, mime_type="", data_type=DataType.RAW),
    neural_memory=NeuralMemoryFields(
        link=LinkFields(
            event_a="[EventIdA]",
            event_b="[EventIdB]",
            unique_id_a="[EventIdA]",
            unique_id_b="[EventIdB]",
            strength_a=1.0,
            strength_b=1.0,
            owner_id="[EventOwnerId]",
            category="Account",
        ),
    ),
)
```

#### Unlink

Unlink two Events [UnlinkEvent Intent type].

- An Event may be a Storage Event or a Link Event; therefore linking between Links or Link to Store Event or any combination is a valid operation.
- There is no upper bound on the number of Links between Events.

Example: send a Message with `intent=IntentType.UnlinkEvent.name`, and `event=EventFields(id="[EventId of the Link Event]", timestamp=..., location=..., location_separator="|")`.

### Store Batch Links

Store a batch of Links [StoreBatchLinks Intent type]. Use `format_batch_link_events_payload` and `BatchLinkEventSpec` with `EventFields` and `LinkFields`. Payload lines use fields such as `unique_id`, `event_id_a`, `event_id_b`, `strength_a`, `strength_b`, `category`, `owner`, `timestamp`, `loc`, `loc_delim`, `type`.

```python
from pod_os_client.message.encoder import format_batch_link_events_payload
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    Message,
    EventFields,
    PayloadFields,
    NeuralMemoryFields,
    BatchLinkEventSpec,
    LinkFields,
)
from pod_os_client.message.constants import DataType

specs = [
    BatchLinkEventSpec(
        event=EventFields(
            unique_id="1234567890",
            owner="$sys",
            timestamp="2024-01-15T10:30:00Z",
            location="TERRA|47.619463|-122.518691",
            location_separator="|",
            type="account link admin account to admin group",
        ),
        link=LinkFields(
            unique_id_a="1234567890",
            unique_id_b="1234567891",
            event_a="...",
            event_b="...",
            strength_a=1.0,
            strength_b=1.0,
            category="Account",
        ),
    ),
]
payload_str = format_batch_link_events_payload(specs)

msg = Message(
    to=f"account@zeroth.{domain_name}",
    from_=f"{client_name}@zeroth.{domain_name}",
    client_name=client_name,
    message_id=str(uuid4()),
    intent=IntentType.StoreBatchLinks.name,
    payload=PayloadFields(data=payload_str, data_type=DataType.RAW),
)
```
