"""Tests for the text-to-speech entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.azure_foundry_conversation.tts import AzureFoundryTTSEntity
from homeassistant.core import HomeAssistant


def _tts_subentry(entry: MockConfigEntry):
    return next(s for s in entry.subentries.values() if s.subentry_type == "tts")


async def test_tts_synthesizes_audio(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Synthesis posts SSML and returns the audio bytes + extension."""
    entity = AzureFoundryTTSEntity(init_integration, _tts_subentry(init_integration))
    entity.hass = hass

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.content = b"AUDIO"
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch(
        "custom_components.azure_foundry_conversation.tts.get_async_client",
        return_value=client,
    ):
        extension, audio = await entity.async_get_tts_audio("hello", "en-US", {})

    assert extension == "mp3"
    assert audio == b"AUDIO"
    assert client.post.await_count == 1


async def test_tts_supported_voices(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Voices are loaded from the API and returned per locale."""
    entity = AzureFoundryTTSEntity(init_integration, _tts_subentry(init_integration))
    entity.hass = hass

    voices_payload = [
        {"Locale": "en-US", "ShortName": "en-US-JennyNeural", "DisplayName": "Jenny"},
        {"Locale": "en-GB", "ShortName": "en-GB-SoniaNeural", "DisplayName": "Sonia"},
    ]
    with patch(
        "custom_components.azure_foundry_conversation.tts.async_list_voices",
        AsyncMock(return_value=voices_payload),
    ):
        await entity._async_load_voices()

    voices = entity.async_get_supported_voices("en-US")
    assert voices is not None
    assert voices[0].voice_id == "en-US-JennyNeural"
    assert entity.async_get_supported_voices("xx-XX") is None
