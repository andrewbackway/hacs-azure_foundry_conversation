"""Tests for the speech-to-text entity."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.azure_foundry_conversation.stt import AzureFoundrySTTEntity
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResultState,
)
from homeassistant.core import HomeAssistant


def _stt_subentry(entry: MockConfigEntry):
    return next(s for s in entry.subentries.values() if s.subentry_type == "stt")


async def _audio() -> AsyncIterator[bytes]:
    yield b"chunk"


def _metadata() -> SpeechMetadata:
    return SpeechMetadata(
        language="en-US",
        format=AudioFormats.WAV,
        codec=AudioCodecs.PCM,
        bit_rate=AudioBitRates.BITRATE_16,
        sample_rate=AudioSampleRates.SAMPLERATE_16000,
        channel=AudioChannels.CHANNEL_MONO,
    )


async def test_stt_success(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A successful recognition returns the display text."""
    entity = AzureFoundrySTTEntity(init_integration, _stt_subentry(init_integration))
    entity.hass = hass

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(
        return_value={
            "RecognitionStatus": "Success",
            "DisplayText": "turn on the light",
        }
    )
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch(
        "custom_components.azure_foundry_conversation.stt.get_async_client",
        return_value=client,
    ):
        result = await entity.async_process_audio_stream(_metadata(), _audio())

    assert result.result is SpeechResultState.SUCCESS
    assert result.text == "turn on the light"


async def test_stt_no_match_is_error(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A non-success recognition status yields an error result."""
    entity = AzureFoundrySTTEntity(init_integration, _stt_subentry(init_integration))
    entity.hass = hass

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"RecognitionStatus": "NoMatch"})
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch(
        "custom_components.azure_foundry_conversation.stt.get_async_client",
        return_value=client,
    ):
        result = await entity.async_process_audio_stream(_metadata(), _audio())

    assert result.result is SpeechResultState.ERROR
