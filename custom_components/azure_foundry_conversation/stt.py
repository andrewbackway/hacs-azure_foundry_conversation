"""Speech-to-text platform (Azure AI Speech) for Azure AI Foundry."""

from __future__ import annotations

from collections.abc import AsyncIterable

import httpx

from homeassistant.components import stt
from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from . import AzureFoundryConfigEntry
from .client import build_stt_url
from .const import (
    CONF_STT_API_KEY,
    CONF_STT_ENDPOINT,
    CONF_STT_FORMAT,
    CONF_STT_LANGUAGE,
    CONF_STT_PROFANITY,
    DEFAULT_STT_FORMAT,
    DEFAULT_STT_LANGUAGE,
    DEFAULT_STT_PROFANITY,
    LOGGER,
    SPEECH_LANGUAGES,
)
from .entity import AzureFoundrySpeechEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AzureFoundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Publish a speech-to-text entity per stt subentry."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "stt":
            continue
        async_add_entities(
            [AzureFoundrySTTEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class AzureFoundrySTTEntity(stt.SpeechToTextEntity, AzureFoundrySpeechEntity):
    """Azure AI Speech short-audio recognition entity."""

    @property
    def supported_languages(self) -> list[str]:
        """Return the supported recognition languages."""
        configured = self.subentry.data.get(CONF_STT_LANGUAGE, DEFAULT_STT_LANGUAGE)
        if configured in SPEECH_LANGUAGES:
            return SPEECH_LANGUAGES
        return [configured, *SPEECH_LANGUAGES]

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return the supported audio formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return the supported audio codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return the supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return the supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return the supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Recognize audio via the Azure Speech short-audio REST API."""
        options = self.subentry.data
        audio = bytearray()
        async for chunk in stream:
            audio.extend(chunk)

        result_format = options.get(CONF_STT_FORMAT, DEFAULT_STT_FORMAT)
        url = build_stt_url(
            options[CONF_STT_ENDPOINT],
            options.get(CONF_STT_LANGUAGE, DEFAULT_STT_LANGUAGE),
            result_format,
            options.get(CONF_STT_PROFANITY, DEFAULT_STT_PROFANITY),
        )

        if metadata.format == AudioFormats.OGG or metadata.codec == AudioCodecs.OPUS:
            content_type = "audio/ogg; codecs=opus"
        else:
            content_type = (
                f"audio/wav; codecs=audio/pcm; samplerate={int(metadata.sample_rate)}"
            )

        headers = {
            "Ocp-Apim-Subscription-Key": options[CONF_STT_API_KEY],
            "Content-Type": content_type,
            "Accept": "application/json",
        }

        client = get_async_client(self.hass)
        try:
            response = await client.post(
                url, headers=headers, content=bytes(audio), timeout=30.0
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            LOGGER.error(
                "Azure Speech STT failed (status=%s): %s",
                err.response.status_code,
                err,
            )
            return SpeechResult(None, SpeechResultState.ERROR)
        except httpx.HTTPError as err:
            LOGGER.error("Azure Speech STT connection error: %s", err)
            return SpeechResult(None, SpeechResultState.ERROR)

        body = response.json()
        if body.get("RecognitionStatus") != "Success":
            LOGGER.warning(
                "Azure Speech STT returned status %s",
                body.get("RecognitionStatus"),
            )
            return SpeechResult(None, SpeechResultState.ERROR)

        if result_format == "detailed":
            nbest = body.get("NBest") or []
            text = nbest[0].get("Display", "") if nbest else body.get("DisplayText", "")
        else:
            text = body.get("DisplayText", "")

        return SpeechResult(text, SpeechResultState.SUCCESS)
