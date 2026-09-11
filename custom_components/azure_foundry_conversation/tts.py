"""Text-to-speech platform (Azure AI Speech) for Azure AI Foundry."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape, quoteattr

import httpx

from homeassistant.components import tts
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from . import AzureFoundryConfigEntry
from .client import async_list_voices, build_tts_url
from .const import (
    CONF_TTS_API_KEY,
    CONF_TTS_ENDPOINT,
    CONF_TTS_LANGUAGE,
    CONF_TTS_OUTPUT_FORMAT,
    CONF_TTS_PITCH,
    CONF_TTS_RATE,
    CONF_TTS_ROLE,
    CONF_TTS_STYLE,
    CONF_TTS_STYLE_DEGREE,
    CONF_TTS_VOICE,
    CONF_TTS_VOLUME,
    DEFAULT_TTS_OUTPUT_FORMAT,
    DEFAULT_TTS_VOICE,
    LOGGER,
    SPEECH_LANGUAGES,
    TTS_OUTPUT_FORMATS,
)
from .entity import AzureFoundrySpeechEntity

_DEFAULT_LANGUAGE = "en-US"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AzureFoundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Publish a text-to-speech entity per tts subentry."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue
        async_add_entities(
            [AzureFoundryTTSEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


def _build_ssml(
    text: str,
    language: str,
    voice: str,
    *,
    rate: str | None,
    pitch: str | None,
    volume: str | None,
    style: str | None,
    style_degree: str | None,
    role: str | None,
) -> str:
    """Build an SSML document for the Azure Speech synthesis endpoint."""
    inner = escape(text)

    if style or role:
        attrs = ""
        if style:
            attrs += f" style={quoteattr(style)}"
        if style_degree:
            attrs += f" styledegree={quoteattr(style_degree)}"
        if role:
            attrs += f" role={quoteattr(role)}"
        inner = f"<mstts:express-as{attrs}>{inner}</mstts:express-as>"

    prosody_attrs = ""
    if rate:
        prosody_attrs += f" rate={quoteattr(rate)}"
    if pitch:
        prosody_attrs += f" pitch={quoteattr(pitch)}"
    if volume:
        prosody_attrs += f" volume={quoteattr(volume)}"
    if prosody_attrs:
        inner = f"<prosody{prosody_attrs}>{inner}</prosody>"

    return (
        '<speak version="1.0" '
        'xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" '
        f"xml:lang={quoteattr(language)}>"
        f"<voice name={quoteattr(voice)}>{inner}</voice></speak>"
    )


class AzureFoundryTTSEntity(tts.TextToSpeechEntity, AzureFoundrySpeechEntity):
    """Azure AI Speech neural text-to-speech entity."""

    _attr_name = "Text-to-speech"

    # Populated per instance from the Speech voices/list endpoint.
    _voices: dict[str, list[tts.Voice]] = {}

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self.subentry.data.get(CONF_TTS_LANGUAGE) or _DEFAULT_LANGUAGE

    @property
    def supported_languages(self) -> list[str]:
        """Return the supported languages."""
        return SPEECH_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return the supported per-call options."""
        return [tts.ATTR_VOICE]

    async def async_added_to_hass(self) -> None:
        """Load the available voices when the entity is added."""
        await super().async_added_to_hass()
        await self._async_load_voices()

    async def _async_load_voices(self) -> None:
        """Fetch and cache the available voices grouped by locale."""
        endpoint, api_key = self._resolve_speech_credentials(
            CONF_TTS_ENDPOINT, CONF_TTS_API_KEY
        )
        if not endpoint or not api_key:
            LOGGER.warning(
                "Azure Speech TTS endpoint or API key not configured; "
                "skipping voice list. Reconfigure the TTS entry to enable it"
            )
            return
        try:
            raw = await async_list_voices(self.hass, endpoint, api_key)
        except httpx.HTTPError as err:
            LOGGER.warning("Could not fetch Azure Speech voices: %s", err)
            return

        voices: dict[str, list[tts.Voice]] = {}
        for item in raw:
            locale = item.get("Locale")
            short_name = item.get("ShortName")
            if not locale or not short_name:
                continue
            display = item.get("DisplayName") or short_name
            voices.setdefault(locale, []).append(tts.Voice(short_name, display))
        self._voices = voices
        LOGGER.debug("Loaded Azure Speech voices for %d locales", len(voices))

    @callback
    def async_get_supported_voices(self, language: str) -> list[tts.Voice] | None:
        """Return the voices available for a locale, if known."""
        return self._voices.get(language)

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Synthesize speech via the Azure Speech REST API."""
        data = self.subentry.data
        endpoint, api_key = self._resolve_speech_credentials(
            CONF_TTS_ENDPOINT, CONF_TTS_API_KEY
        )
        if not endpoint or not api_key:
            raise HomeAssistantError(
                "Azure Speech TTS is not configured; "
                "reconfigure the TTS entry with an endpoint and API key"
            )
        voice = options.get(tts.ATTR_VOICE) or data.get(
            CONF_TTS_VOICE, DEFAULT_TTS_VOICE
        )
        output_format = data.get(CONF_TTS_OUTPUT_FORMAT, DEFAULT_TTS_OUTPUT_FORMAT)
        extension, _content_type = TTS_OUTPUT_FORMATS.get(
            output_format, ("mp3", "audio/mpeg")
        )

        ssml = _build_ssml(
            message,
            language or data.get(CONF_TTS_LANGUAGE) or _DEFAULT_LANGUAGE,
            voice,
            rate=data.get(CONF_TTS_RATE),
            pitch=data.get(CONF_TTS_PITCH),
            volume=data.get(CONF_TTS_VOLUME),
            style=data.get(CONF_TTS_STYLE),
            style_degree=data.get(CONF_TTS_STYLE_DEGREE),
            role=data.get(CONF_TTS_ROLE),
        )

        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": output_format,
            "User-Agent": "home-assistant-azure-foundry",
        }
        url = build_tts_url(endpoint)

        client = get_async_client(self.hass)
        try:
            response = await client.post(
                url, headers=headers, content=ssml.encode("utf-8"), timeout=30.0
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            LOGGER.error(
                "Azure Speech TTS failed (status=%s): %s",
                err.response.status_code,
                err,
            )
            raise HomeAssistantError("Azure Speech TTS request failed") from err
        except httpx.HTTPError as err:
            LOGGER.error("Azure Speech TTS connection error: %s", err)
            raise HomeAssistantError("Azure Speech TTS request failed") from err

        return extension, response.content
