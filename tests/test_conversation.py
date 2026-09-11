"""Tests for the conversation entity."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeStream


def _text_delta(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="response.output_text.delta", delta=text)


def _completed() -> SimpleNamespace:
    return SimpleNamespace(type="response.completed")


def _conversation_entity_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    return next(
        entry.entity_id
        for entry in ent_reg.entities.values()
        if entry.domain == "conversation"
    )


async def test_conversation_returns_streamed_text(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A plain turn streams the model's text back to the user."""
    client = init_integration.runtime_data
    client.responses.create = AsyncMock(
        return_value=FakeStream([_text_delta("Hello there"), _completed()])
    )

    result = await conversation.async_converse(
        hass,
        "hi",
        None,
        Context(),
        agent_id=_conversation_entity_id(hass),
    )

    assert result.response.speech["plain"]["speech"] == "Hello there"
    assert client.responses.create.await_count == 1
