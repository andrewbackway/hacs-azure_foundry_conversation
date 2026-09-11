"""Tests for the AI Task entity."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeStream


def _ai_task_entity_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    return next(
        entry.entity_id
        for entry in ent_reg.entities.values()
        if entry.domain == "ai_task"
    )


async def test_generate_data_returns_text(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """generate_data returns the model's text when no structure is requested."""
    client = init_integration.runtime_data
    client.responses.create = AsyncMock(
        return_value=FakeStream(
            [
                SimpleNamespace(type="response.output_text.delta", delta="the answer"),
                SimpleNamespace(type="response.completed"),
            ]
        )
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="test",
        entity_id=_ai_task_entity_id(hass),
        instructions="give me an answer",
    )

    assert result.data == "the answer"
