# Pod-OS Python Client — Knowledge Base

This directory contains knowledge base articles for **humans and GenAI agents** to understand and use the Pod-OS Python client (`pod_os_client`). The content is aligned with the Pod-OS Evolutionary Neural Memory and messaging model and uses **Python** examples throughout.

## Contents

| Document | Description |
|----------|-------------|
| [docs/Pod-OS-Communication-Prompts.md](docs/Pod-OS-Communication-Prompts.md) | Gateway, messaging model, and Python client connection/send usage |
| [docs/Pod-OS-Message-Handling-Prompts.md](docs/Pod-OS-Message-Handling-Prompts.md) | Message structure, connection sequence, and send/response handling in Python |
| [docs/Pod-OS-Neural-Memory-Event-Prompts.md](docs/Pod-OS-Neural-Memory-Event-Prompts.md) | Evolutionary Neural Memory events, tags, links; storing events/tags/links with Python examples |
| [docs/Pod-OS-Neural-Memory-Retrieval-Prompts.md](docs/Pod-OS-Neural-Memory-Retrieval-Prompts.md) | Retrieval, pattern search, GetEvent and GetEventsForTags with Python examples |

## Use

- **Humans**: Read the markdown files for concepts, rules, and copy-pasteable Python snippets.
- **AI agents**: Use these docs as context when answering questions or generating code that uses the Pod-OS Python client (e.g. `Client`, `Config`, `Message`, `EventFields`, intents, Evolutionary Neural Memory operations).

All code samples assume the `pod_os_client` package is installed and use types from `pod_os_client.message.types`, `pod_os_client.message.intents`, and helpers from `pod_os_client.message.encoder` where applicable.
