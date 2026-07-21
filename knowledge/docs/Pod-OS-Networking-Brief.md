# Pod-OS Python Actor Networking Brief

Guide for updating Python Gateway actors to use `Config.external_receiver` (requires **pod-os-py-client >= 0.1.1**).

## Problem

If your actor runs its own `connection.receive()` loop **and** uses sync `send_message()` or client auto-reconnect, two coroutines call `receive()` on the same socket → `readexactly() already waiting` → connection loss → mesh timeouts.

## Requirement

Upgrade to **pod-os-py-client >= 0.1.1**.

---

## Config (every actor with an app-owned receive loop)

```python
Config(
    host=...,
    port=...,
    client_name="my-actor",          # must match PODOS_CLIENT_NAME / Gateway registration
    gateway_actor_name=...,
    enable_concurrent_mode=False,    # you own receive()
    external_receiver=True,          # required
    enable_streaming=True,
    enable_reconnection=True,        # explicit reconnect only
)
```

Env / INI equivalents:

- `PODOS_EXTERNAL_RECEIVER=1`
- INI: `external_receiver=true`

When `external_receiver=True`, the client:

- does **not** start its background receive loop
- rejects `send_message()` / `start_receiver()` (they would race `receive()`)
- exposes `send_no_wait(msg)` for fire-and-forget encode+send
- disables send-path auto-reconnect; pause your loop, then `await client.reconnect()`

---

## Send / receive rules

| Do | Don't |
|---|---|
| One coroutine owns `client._connection.receive()` | `client.send_message()` (calls `receive()`) |
| `await client.send_no_wait(msg)` for outbound | `client.start_receiver()` |
| Route inbound responses in your loop | Let client auto-reconnect during receive |
| `await client.reconnect()` after pausing receive | Encode+send via raw socket bypassing send lock |

---

## Minimal actor loop pattern

```python
client = Client(config)
await client.connect()

pending: dict[str, asyncio.Future] = {}

async def send_and_wait(msg: Message, timeout: float) -> Message:
    fut = asyncio.get_running_loop().create_future()
    pending[msg.message_id] = fut
    try:
        await client.send_no_wait(msg)
        return await asyncio.wait_for(fut, timeout)
    finally:
        pending.pop(msg.message_id, None)

while running:
    try:
        raw = await asyncio.wait_for(client._connection.receive(), timeout=1.0)
    except asyncio.TimeoutError:
        continue
    except ConnectionError:
        await client.reconnect()   # only when NOT inside receive()
        continue

    msg = decode_message(raw)

    # 1) Complete outbound mesh waits (ActorResponse, GetEvent, etc.)
    if msg.message_id in pending and not pending[msg.message_id].done():
        pending[msg.message_id].set_result(msg)
        continue

    # 2) Dispatch inbound work
    if msg.intent == "ActorRequest":
        asyncio.create_task(handle(client, msg))
```

For **fire-and-forget** replies (Status, ActorResponse): use `send_no_wait` only — no pending future needed.

Optional helper: `client.deliver_response(msg)` completes a pending future when `msg.message_id` matches.

---

## Reconnect protocol

On disconnect:

1. **Stop** the receive loop (or exit the `receive()` call via exception).
2. Fail all pending futures with `ConnectionError("reconnecting")`.
3. `await client.reconnect()` — runs ID handshake + `receive()` once (safe; loop is paused).
4. Resume receive loop.

Do **not** call `client.close()` + new `Client()` unless you also rebind every reference to the old client.

---

## Outbound mesh calls (orchestrator actors)

Actors like `ingest-worker` that call other actors:

- Register `message_id → Future` before send
- `await client.send_no_wait(ActorRequest(...))`
- Await future in your receive loop (not via `send_message`)
- On reconnect, fail pending futures — don't hang until timeout

---

## Inbound actor handlers

Handler pattern (unchanged semantics):

1. `send_no_wait(Status in_progress)`
2. Do work
3. `send_no_wait(ActorResponse success/error)`
4. `send_no_wait(Status completed/failed)`

All via `send_no_wait`, never `send_message`.

---

## Two actor archetypes

**A. Gateway shell actor** (receives `ActorRequest`, may call other actors)

→ `external_receiver=True`, app receive loop, `send_no_wait` everywhere.

**B. Request/response client** (only sends, waits for one reply, no long-lived loop)

→ `external_receiver=False`, `enable_concurrent_mode=True` or sync mode is fine.

→ Do **not** also run a manual receive loop.

Pick one model per process.

---

## Checklist per actor

- [ ] `pod-os-py-client >= 0.1.1` installed
- [ ] `external_receiver=True` if app owns `receive()`
- [ ] All sends use `send_no_wait` (or shared helper that delegates to it)
- [ ] No `send_message()` in actor/mesh code paths
- [ ] Pending-response map + routing in receive loop
- [ ] Reconnect fails pending futures, then `Client.reconnect()`
- [ ] Receive loop rebinds client after reconnect if client object can change
- [ ] `PODOS_CLIENT_NAME` matches Gateway registration

---

## Reference implementation

See **pod-os-evolutionary-knowledge-hypergraph**:

- `ekgg/service/gateway_shell.py` — receive loop, `send_no_wait`, response routing
- `ekgg/service/mesh_client.py` — outbound mesh `send_actor_request`
- `ekgg/service/actor_service.py` — `_build_podos_config`, `reconnect`

See also **README.md** § External receiver in this repo.
