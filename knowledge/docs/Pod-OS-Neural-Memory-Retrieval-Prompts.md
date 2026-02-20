# Neural Memory Database Information Retrieval

Pod-OS, uniquely, provides a Neural Memory Database that has the following behavioral characteristics: acquiring (encoding), stabilizing (consolidation), and retrieving information, and forming engrams (memory traces) within groups of Events. Key characteristics include its large storage capacity with decreasing marginal storage volume, native version management learning and ease, and ability to inter-link and describe any and all Event Objects using weights or activation functions, action policies, or other objective function methods. The Neural Memory DB's central thesis is that each moment in time captures, and processes important context that software, and the most advanced, complex and adaptive AIs and robotics require. Including LLMs, RAG, robotics, World Models, and other advanced AI and robotics applications.

The Neural Memory Database uses three primitives:
1. **Event Objects**: An Event Object is a uniquely identified datum (from any source) which is used as a base reference for a set of versioned attributes and context bound weighted links to other event objects. Event Objects carry crucial context information including time and location, owner, encryption, message source as actor@gateway, message destination actor@gateway, and payload MIME and binary data.
2. **Tags**: Tags are values that describe important information about the Event. There are multiple design options. The simplest design option is to use frequency=tagvalue. Frequency is an integer that describes the number of times the Tag has been applied to the Event. Tagvalue is a string or integer or float or embedding or binary data or other type that describes the value of the Tag. A powerful design option is to use Facets which are key/value pairs of any type in the format of frequency=key_name=key_value. More complex designs are possible. For example, a tag value can be a hash of the Event Object, a pointer to the Event Object, a binary data blob or a hierarchical string or integers or floats or embeddings or other type that describes the value of the Tag. What is required is that the Tag value can be searched for and retrieved using the Tag value following the guidance in the Retrieval/Search Guidance section.
3. **Link Objects**: Links connect any two Events (including Link Event), but as Links are Events themselves, also carry the Event Object and Tag descriptions along with weights (integer or continuous function).

Neural Memory uses Tags to implicitly associate events by Tag name, time, and location. Neural Memory uses links to explicitly associate events.

By combining Links and Tags, complex data structures and sets of related events can be created depending on the objective. For example, the Neural Memory Database can capture neural memories and semantic memories; can use Tags and Links to form short and long-term memories; and can use Links and Tags to form short and long-term relationships between events. In other data storage examples, the Neural Memory Database can be used to create a knowledge graph, a semantic network, or a graph of related events; the Neural Memory Database can also be used to mimic the behavior of a relational database such as SQL, a document database, or a graph database. In other examples, the Neural Memory Database can be used to encode in data structures a neural network (e.g., FNN, CNN, RNN, LSTM, GRU), transformers, a genetic algorithm, or a reinforcement learning model.

Links and tags can be defined independently of the database actually containing the original event definition, permitting the distribution of data across servers or database files. Retrieval of the actual event may require a request to other database handlers (or a router which understands that event requests need to be distributed to a given set of handlers), but there is no requirement for the actual event to be recorded within a database in which tags are placed. While this can cause data concurrency challenges, it also permits explicit segregation where it is required (such as a security application, or private analytical data associated with public information).

Pod-OS uses specific types (`pod_os_client.message.types`) to manage communication with the Actor. All Event Message interactions use a Request/Response pair either in synchronous (STREAMING ON) or asynchronous mode (STREAMING OFF). The Actor always returns a Response to the client's request. Depending on the implementation, the client may choose to use the synchronous or asynchronous mode; and needs to handle Message management accordingly.

The Actor Response carries crucial information that may be remembered depending on the operation.

### Ownership Guidance

[To be completed]

### Reference Guidance

- Internally, all communication about Event Objects and Link Objects uses the EventId field for reference. The EventId is created by the Actor when the Event Object is stored. As such, the EventId is the primary reference for all Event Objects and Link Objects. EventUniqueId is a useful developer-set customer ID for external reference by the developer.
- MessageId can be used by client applications to track the message and conversation flow.

## Retrieval

Central to Pod-OS is the concept of "pattern search", which permits searching for whole symbols or symbols that match a certain description as opposed to searching for rigidly-defined values such as keywords. For example, "any number" is a pattern, while a list of numbers is a limited set (a list of numbers is also a synonym list). Known sets are always finite, while patterns may be infinite. It is far more efficient to search for all matches of a pattern rather than all matches of a set, since matching a set requires at least N searches, where N is the number of elements in the set. It is also easier to do exclusionary searches such that the returned set of objects or versions contain no symbols matching a given pattern. Using pattern search the entire location and time specification can be stored as a single symbol, and a search can then be done efficiently for symbols containing certain subsets or ranges of values occurring at certain positions within the symbols. Symbols may be grouped into indexes, and any number of indexes may be defined.

Pod-OS encourages the builder to describe stored information as completely as possible rather than deciding what subset of information is to be stored. Since symbols may be added at any time to existing data, the use of background post-processing of data is a good way to better define the type and content of data stored.

### Programmable Searches

Pod-OS provides a series of predefined search capabilities for event objects. Searches consist of one or more search clauses, where each clause contains the data to be searched for, constraints that are to be applied to the search and the type of search to be performed. Once a search is performed, the Response returned is a series of result specifications that identify events containing the requested data. As a result, highly complex searches can be performed without requiring low-level programming, but the option of allowing for novel ways of processing search data is available. As an example, "compound searches" may be performed. Compound searches are somewhat like a join in an SQL system except that the objects retrieved via the results of a symbol search can then be used to create new searches based on symbols associated with event objects found as part of the original search request.

For example, consider a search which returns a single Event based on a keyword. In a typical search engine or SQL system, this would be the terminus of the search. Using Pod-OS, a set of Tags can be retrieved (or heuristics synthesized) from the Event, revealing that the Event had been previously tagged with a series of concepts (stored as Tags) based on a previous analysis by a semantic network. Using these Tags, a second set of searches is performed where all Events containing concept Tags matching those in the original event object are found; the event objects found need not even be parsed documents – they may be media files or other non-text data. This search methodology can also be called an "n-dimensional" or "tiered" search as opposed to a "search within a search", the latter simply being an exclusionary search within a previously retrieved set.

### Buffered Results

Queries sent to the Neural Memory DB may return more than one message. There is an option to return results either as a single message where the payload contains the list of results, or as a series of individual result messages.

In the series individual result messages case, the replies will be sent after a "BATCH START" type message. Individual results are returned in subsequent "RECORD" type messages. After the last "RECORD" message, a record set "BATCH END" message will be sent, indicating that no more results are to be sent.

### Pattern Matching Specification

A pattern is specified by:
- **Type**: The type of pattern matching operation (e.g. fastpattern, regexp, eq, int_eq, dbl_range_eq).
- **LowValue**: Used for single operation patterns (equality, comparison) or lower bound for ranges.
- **HighValue**: Used for range and exclusion operations (optional).

#### Pattern Matching Types

| Pattern Type Name | Description | Low Value | High Value |
|-------------------|-------------|-----------|------------|
| fastpattern | A fast, character-based pattern match similar to regular expressions. The native pattern matching system for the Pod-OS. | The low or minimum value to match. If the high value is not specified, then match only this pattern. | If specified, match all values between the low and high values. |
| regexp | A standard (non-extended) regular expression | The regular expression to be used. | Not used |
| eq | Match strings equal to the low value | String to be matched | - |
| ne | Match strings not equal to the low value | String to be matched | - |
| le | Match strings less than or equal to the low value | String to be matched | - |
| lt | Match strings less than the low value | String to be matched | - |
| ge | Match strings greater than or equal to the low value | String to be matched | - |
| gt | Match strings greater than the low value | String to be matched | - |
| distance | Match strings against the string in Low with an edit distance LE to the value supplied in High | Comparison string | Maximum distance allowed |
| range_eq | Match strings inclusive within the low and high values (ge AND le) | Lower limit of matches | High limit of matches |
| range_ne | Match strings exclusive that are not within the low and high values (lt OR gt) | Upper limit of low range | Lower limit of high range |
| int_eq | Integer equality | Integer to be matched | - |
| int_ne | Integer non-equality | Integer to be matched | - |
| int_le | Integer less than or equal | Integer to be matched | - |
| int_lt | Integer less than | Integer to be matched | - |
| int_ge | Integer greater than or equal | Integer to be matched | - |
| int_gt | Integer greater than | Integer to be matched | - |
| int_range_eq | Integer range | Bottom of range | Top of range |
| int_range_ne | Integer range exclusion | Bottom of range | Top of range |
| dbl_eq | Double-precision float equality | Floating point value to be matched | - |
| dbl_ne | Double-precision float non-equality | Floating point value to be matched | - |
| dbl_le | Double-precision float less than or equal | Floating point value to be matched | - |
| dbl_lt | Double-precision float less than | Floating point value to be matched | - |
| dbl_ge | Double-precision float greater than or equal | Floating point value to be matched | - |
| dbl_gt | Double-precision float greater than | Floating point value to be matched | - |
| dbl_range_eq | Double-precision float range | Bottom of range | Top of range |
| dbl_range_ne | Double-precision float range exclusion | Bottom of range | Top of range |

#### Search Clause Components

A search clause is used to find events that match the search, and to alter the overall results based on the boolean operation of the clause.

| Field Name | Description | Content |
|------------|-------------|---------|
| clause_type | The type of clause | Required, must be the letter "S" |
| boolean | The boolean operation to apply between results from previous clauses and the current clause | Required. A boolean operator name: "and", "or", "not" or "xor". The system will always force an "OR" operation for the first clause in any search operation. |
| low | Low or match pattern for tag values | Required. Defines either a match pattern or the low pattern for a range using the FASTPATTERN method. |
| high | High match pattern for tag values | Optional. If present, defines the upper range of values for a FASTPATTERN applied to tags. |
| filter_type | Tag value filter type | Optional. The type of filter to be applied to tag values that match the tag pattern. |
| filter_low | Low or singular match value for tag value filter | Required if "filter_type" is used. Filter pattern low match value specification. |
| filter_high | High limit or match value for tag value filter range | Optional. Filter pattern high match value specification. |
| owner_event_id | The event key of the tag owner | Optional. If present, then only tags owned by the specified owner will be part of the results. |
| event_id | The event key of the event associated with the tag | Optional. If present, then only matching tag values associated with a specific event will be part of the results. |
| clause_name | Name of the clause | Optional. Used for branching. |

#### Branch Clause Components

A branch clause causes the Neural Memory to test a value and based on the value of the test and the boolean operator, jump to a named clause based on whether the test is true or false.

| Field Name | Description | Content |
|------------|-------------|---------|
| clause_type | The type of clause | Required. Must be the letter "B" |
| boolean | The boolean operation to apply to the branch pattern | Required. May be one of "OR" or "NOT" |
| source | Source of the data to be used to test against the branch pattern | Named data source (see Data Source table) |
| filter_type | Tag value filter type | The type of filter to be applied to the data source |
| filter_low | Low or singular match value for tag value filter | Required if "filter_type" is used. Filter pattern low match value specification. |
| filter_high | High limit or match value for tag value filter range | Optional. Filter pattern high match value specification. |
| target | Target clause name | The name of the target clause |
| value | Segment number | The segment number (1 to 99) |

##### Branch Boolean Operations

| Boolean | Action |
|---------|--------|
| OR | Jump to the named clause if the branch pattern matches the data source |
| NOT | Jump to the named clause if the branch pattern does NOT match the data source |

##### Branch Source Options

| Name | Description |
|------|-------------|
| $total_events | The total number of events currently in the result set |
| $total_hits | The total number of event hits for all events in the result set |
| $average_hits | The average number of hits per event in the result set |
| $average_terms | Average number of terms per event |
| $mean_hits | The mean number of event hits for all events in the result set |
| $mean_terms | The mean number of terms per event |
| $tags | The set of tag values in the result set (pattern matches against tags found during matches) |
| $event | The set of event keys for events in the result set (pattern matches against event key components) |
| $event_time | Time of the event, as seconds past UTC epoch |
| $event_year | Year of the event |
| $event_month | Month of the event |
| $event_day | Day of the event |
| $event_hour | Hour of the event |
| $event_minute | Minute of the event |
| $event_sec | Second of the event |
| $event_usec | The microsecond of the event |
| $event_coord | Event coordinate segment; the segment number is found in value field |
| $last_count | The number of matches found for the last clause, regardless of type |
| $last_branch_count | The number of matches found for the last branch clause. This will either be one of the system values, or a result of matches against a data source |
| $last_search_count | The number of matches found for the last search clause. The number of matches represents different things depending on the boolean for the clause (see Branch Last Search Count Boolean Behaviors) |
| `<variable>` | The value of the named variable |

###### Branch Last Search Count Boolean Behaviors

| Boolean | Result Count Represents |
|---------|------------------------|
| OR | Number of new events added to results |
| AND | Number of events found in existing results |
| NOT | Number of events removed from results |
| XOR | Number of new events added to results |

#### Action Clause Components

An action clause alters the result set, saves data, or takes an action based on a pattern and a data source.

| Field Name | Description | Content |
|------------|-------------|---------|
| clause_type | The type of clause | Required, must be the letter "A" |
| action_type | Type of action to perform | See Action Types table |
| source | Source of the data to be used for action | Named data source (see Data Source table) |
| name | Variable or script name | The target for the SET, TEST or SCRIPT action |
| value | Literal value | Possible source for SET operation |
| equation | Equation to be evaluated | Used by the MATH operation |
| filter_type | Tag value filter type | Optional. The type of filter to be applied to data source |
| filter_low | Low or singular match value for tag value filter | Required if "filter_type" is used |
| filter_high | High limit or match value for tag value filter range | Optional. Filter pattern high match value specification |
| clause_name | Name of the clause | Optional. Used for branching; if a script returns TRUE, then branch to this clause |
| target | The term to jump to on success | Optional. If the boolean is OR, this will always be returned as evaluated by the action |

##### Action Types

| Type | Description |
|------|-------------|
| CLR | Clear all search results |
| JUMP | Jump to a named clause |
| CLRMATCH | Clear all matches found as part of previous search clause |
| CLRSET | Clear set of matches where the data source matches the pattern |
| CLRVAR | Clear variable value |
| SET | Set variable value using data source |
| SCRIPT | Run a script against the result set |
| TEST | Test variable value against pattern |
| JUMPVAR | Jump to named clause using the name stored in a variable |
| MATCH_SIM | Match for similar events. The "equation" variable contains the match percentage, upper and lower bounds separated by commas |
| NOT_MATCH_SIM | Inverse of MATCH_SIM; only those events which do NOT match by at least N percent of the terms in the subset are valid |
| MATH | Store results of an equation into the named variable |

##### Action Source Options

| Name | Description |
|------|-------------|
| $total_events | The total number of events currently in the result set |
| $total_hits | The total number of event hits for all events in the result set |
| $average_hits | The average number of hits per event in the result set |
| $tags | The set of tag values in the result set (pattern matches against tags found during matches) |
| $event | The set of event keys for events in the result set (pattern matches against event key components) |
| $last_count | The number of matches found for the last clause, regardless of clause type |
| $last_action_count | The number of matches found for the last action clause |
| $last_branch_count | The number of matches found for the last branch clause. This will either be one of the system values, or a result of matches against a data source |
| $last_search_count | The number of matches found for the last search clause. The number of matches represents different things depending on the boolean for the clause (see table below) |
| $literal | Literal value from the specification "value" field |
| $match_owner | Number of event owners in set matching filter pattern |
| $most_freq_tags | For MATCH_SIM, find events with tag sets where at least N percent of the most frequent tags in the entire set are present in the events found. The minimum and maximum event hit counts for the set (the range of hits to compare to) are in "equation", the format of which is "matchcount,low,high", where "matchcount" is N. Low and high are integers, where a negative value indicates a relative position from the start or end of the list |
| `<variable>` | The value of the named variable |

## Retrieval Messages with Examples

### Get Event

Use to retrieve a single Event Object [GetEvent Intent type].

#### Rules

- Use get when Event.id, Event.unique_id, or Time and Location are known.
- If GetEventOptions.get_links=True and GetEventOptions.send_data=True, Pod-OS returns links rather than the data blob.

#### Example 1: Basic GetEvent Request (by EventId) — Python

```python
from uuid import uuid4
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    Message,
    EventFields,
    NeuralMemoryFields,
    GetEventOptions,
)

msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEvent.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    event=EventFields(id="2024.01.15.14.30.45.123456@actor1|location1|segment1"),
    neural_memory=NeuralMemoryFields(
        get_event=GetEventOptions(
            send_data=True,
            get_tags=True,
            get_links=False,
        ),
    ),
)
# response = await client.send_message(msg)
```

#### Example 2: Advanced GetEvent Request (with filters and links) — Python

```python
msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEvent.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    event=EventFields(
        id="2024.01.15.14.30.45.123456@actor1|location1|segment1",
        unique_id="user-provided-unique-id-123",
        timestamp="1705327845123456",
        location_separator="|",
        location="TERRA|47.619463|-122.518691|100.5",
    ),
    neural_memory=NeuralMemoryFields(
        get_event=GetEventOptions(
            send_data=True,
            local_id_only=False,
            get_tags=True,
            tag_format=1,
            event_facet_filter="location*,action*",
            tag_filter="^user.*=",
            get_links=True,
            get_link_tags=True,
            get_target_tags=True,
            first_link=0,
            link_count=10,
            link_facet_filter="category*",
            target_facet_filter="type*",
            category_filter="related,similar",
            request_format=2,
        ),
    ),
)
```

#### Example 3: Minimal GetEvent Request (by UniqueId only) — Python

```python
msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEvent.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    event=EventFields(unique_id="user-provided-unique-id-123"),
)
```

#### Example Response

The response is populated in the `response` field of the Message and in `event` and `payload`:

```python
# After calling the Actor (response = await client.send_message(msg)):
# response.event contains the event (id, unique_id, owner, type, etc.)
# response.payload contains payload data if send_data=True
# response.response contains status, message, tag_count, date_time, etc.
# For GetEvent with get_tags=True, tags may be on response.event.tags or in response.response

event_id = response.event_id()
unique_id = response.event_unique_id() if response.event else ""
status = response.processing_status()
payload_bytes = response.payload_data()
```

### Get Events using Tag search (Events Matching Tags)

Used to retrieve Events [GetEventsForTags Intent type] that match the Tag search parameters.

Searches for matching events are performed using a series of match clauses. A clause may request a search match, branch to another clause based on a pattern and source value, or perform an action based on the current search results or system conditions. Each clause is formatted as a series of tab-separated fields, where the field format is "fieldname:value". A clause is terminated with a newline. Clauses may be given a name so that actions and branches may be used in the search processing.

#### Rules

There are three types of search clauses. The first is the "search clause", which causes the Neural Memory to find events associated with tags matching a value pattern, and then to apply that set of events using a boolean to the existing set of found events. The second is the "branch clause", which causes the Neural Memory to jump to a named clause based on a pattern and a data source. The third and last is the "action clause", which alters the result set, saves data, or takes an action based on a pattern and a data source. Action clauses also allow for the evaluation of math expressions to generate a value to be compared against a pattern. Action clauses further allow for the storage of values between clauses, so that data from the results of one clause can be used later in another clause.

Clauses are evaluated in the order they appear in the search specification.

#### Example 1: Basic GetEventsForTags Request — Python

```python
from uuid import uuid4
from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import (
    Message,
    NeuralMemoryFields,
    GetEventsForTagsOptions,
    SearchOptions,
)

msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEventsForTags.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    neural_memory=NeuralMemoryFields(
        search=SearchOptions(
            clause="clause_type:S\tboolean:or\tlow:action=click",
            buffer_results=True,
            buffer_format="0",
        ),
        get_events_for_tags=GetEventsForTagsOptions(
            buffer_results=True,
            include_tag_stats=True,
            buffer_format="0",
        ),
    ),
)
```

#### Example 2: Advanced GetEventsForTags Request (with filtering and paging) — Python

```python
from uuid import uuid4
# IntentType already imported above

msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEventsForTags.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    neural_memory=NeuralMemoryFields(
        search=SearchOptions(
            clause=(
                "clause_type:S\tboolean:or\tlow:action=click\n"
                "clause_type:S\tboolean:and\tlow:user=*"
            ),
            buffer_results=True,
            include_tag_stats=True,
            hit_tag_filter="^(action|user)=",
            buffer_format="0",
        ),
        get_events_for_tags=GetEventsForTagsOptions(
            event_pattern="2024.*",
            include_brief_hits=False,
            get_all_data=False,
            start_result=0,
            end_result=100,
            events_per_message=50,
            min_event_hits=1,
            first_link=0,
            link_count=10,
            get_match_links=True,
            count_match_links=False,
            get_link_tags=True,
            link_tag_filter="category=*",
            linked_events_filter="type=document",
            link_category="related",
            owner="",
            buffer_results=True,
            include_tag_stats=True,
            hit_tag_filter="",
            invert_hit_tag_filter=False,
            buffer_format="0",
        ),
    ),
)
```

#### Example Response

The response is populated in `response` and optionally `payload`. Use `response.event_records` for parsed events when the response is buffered:

```python
# response = await client.send_message(msg)
status = response.processing_status()
event_count = response.response.total_events if response.response else 0
event_records = response.response.event_records if response.response else []
for rec in event_records:
    eid = rec.id
    etype = rec.type
    tags = rec.tags
```

### Get Tags for Event

List all tags associated with a single event, where the tags optionally match a pattern.

#### Rules

Use `GetEvent` with `GetEventOptions.get_tags=True` to retrieve tags for an event. The payload or parsed event may contain tag data in the format: &lt;frequency&gt; &lt;tab&gt; &lt;tag category&gt; &lt;tab&gt; &lt;tag value&gt;. The "tag category" will be a single asterisk ("*") if there is no category associated with the tag.

#### Example 1: GetEvent with get_tags=True (Basic Request) — Python

```python
msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEvent.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    event=EventFields(id="2024.01.15.14.30.45.123456@actor1|location1|segment1"),
    neural_memory=NeuralMemoryFields(
        get_event=GetEventOptions(get_tags=True, request_format=2),
    ),
)
```

#### Example 2: GetEvent with Tag Filtering (event_facet_filter) — Python

```python
msg = Message(
    to="mem@zeroth.example.com",
    from_="MyClient@zeroth.example.com",
    intent=IntentType.GetEvent.name,
    client_name="MyClient",
    message_id=str(uuid4()),
    event=EventFields(id="2024.01.15.14.30.45.123456@actor1|location1|segment1"),
    neural_memory=NeuralMemoryFields(
        get_event=GetEventOptions(
            get_tags=True,
            event_facet_filter="category:*",
            request_format=2,
        ),
    ),
)
```

#### Example Response

Tags are returned on the response event or in the response payload. The decoder may populate `response.event.tags` or parse tag data from the payload. Use `response.response.tag_count` and the event's `tags` list (e.g. `TagOutput` with frequency, category, key, value) as provided by the decoder.
