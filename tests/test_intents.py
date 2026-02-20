"""Tests for intent types."""

from pod_os_client.message.intents import (
    IntentType,
    intent_from_command,
    intent_from_message_type,
    intent_from_message_type_and_command,
)


def test_intent_types() -> None:
    """Test intent type constants."""
    assert IntentType.GatewayId.name == "GatewayId"
    assert IntentType.GatewayId.message_type == 5
    assert IntentType.StoreEvent.name == "StoreEvent"
    assert IntentType.StoreEvent.neural_memory_command == "store"


def test_intent_from_command() -> None:
    """Test intent lookup from command."""
    intent = intent_from_command("store")
    assert intent is not None
    assert intent.name == "StoreEvent"

    intent = intent_from_command("get")
    assert intent is not None
    assert intent.name == "GetEvent"

    intent = intent_from_command("invalid")
    assert intent is None


def test_intent_from_message_type() -> None:
    """Test intent lookup from message type."""
    intent = intent_from_message_type(5)
    assert intent is not None
    assert intent.name == "GatewayId"

    intent = intent_from_message_type(2)
    assert intent is not None
    assert intent.name == "ActorEcho"

    intent = intent_from_message_type("store")
    assert intent is not None
    assert intent.name == "StoreEvent"


def test_intent_from_message_type_and_command() -> None:
    """Test intent lookup from message type and command."""
    # MEM_REQ (1000) with store command
    intent = intent_from_message_type_and_command(1000, "store")
    assert intent is not None
    assert intent.name == "StoreEvent"

    # MEM_REPLY (1001) with get command
    intent = intent_from_message_type_and_command(1001, "get")
    assert intent is not None
    assert intent.name == "GetEventResponse"

    # Non-memory intent
    intent = intent_from_message_type_and_command(5, "")
    assert intent is not None
    assert intent.name == "GatewayId"
