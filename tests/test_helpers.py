"""Tests for pure helper logic (URL builders, SSML, reasoning options)."""

from __future__ import annotations

import pytest

from custom_components.azure_foundry_conversation.client import (
    build_stt_url,
    build_tts_url,
    build_tts_voices_url,
    endpoint_host,
    normalize_foundry_base_url,
)
from custom_components.azure_foundry_conversation.const import reasoning_effort_options
from custom_components.azure_foundry_conversation.tts import _build_ssml


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "https://r.services.ai.azure.com",
            "https://r.services.ai.azure.com/openai/v1/",
        ),
        (
            "https://r.services.ai.azure.com/",
            "https://r.services.ai.azure.com/openai/v1/",
        ),
        (
            "https://r.services.ai.azure.com/openai/v1",
            "https://r.services.ai.azure.com/openai/v1/",
        ),
        (
            "https://r.services.ai.azure.com/openai/v1/",
            "https://r.services.ai.azure.com/openai/v1/",
        ),
    ],
)
def test_normalize_base_url(value: str, expected: str) -> None:
    assert normalize_foundry_base_url(value) == expected


def test_endpoint_host() -> None:
    host = endpoint_host("https://r.services.ai.azure.com/x")
    assert host == "r.services.ai.azure.com"


def test_stt_url_custom_subdomain() -> None:
    url = build_stt_url(
        "https://r.cognitiveservices.azure.com/", "en-US", "simple", "masked"
    )
    assert url == (
        "https://r.cognitiveservices.azure.com"
        "/stt/speech/recognition/conversation/cognitiveservices/v1"
        "?language=en-US&format=simple&profanity=masked"
    )


def test_stt_url_regional() -> None:
    url = build_stt_url(
        "https://eastus.stt.speech.microsoft.com/", "de-DE", "detailed", "raw"
    )
    assert url == (
        "https://eastus.stt.speech.microsoft.com"
        "/speech/recognition/conversation/cognitiveservices/v1"
        "?language=de-DE&format=detailed&profanity=raw"
    )


def test_tts_url_forms() -> None:
    assert build_tts_url("https://r.cognitiveservices.azure.com/") == (
        "https://r.cognitiveservices.azure.com/tts/cognitiveservices/v1"
    )
    assert build_tts_url("https://eastus.tts.speech.microsoft.com/") == (
        "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"
    )


def test_tts_voices_url_forms() -> None:
    assert build_tts_voices_url("https://r.cognitiveservices.azure.com/") == (
        "https://r.cognitiveservices.azure.com/tts/cognitiveservices/voices/list"
    )
    assert build_tts_voices_url("https://eastus.tts.speech.microsoft.com/") == (
        "https://eastus.tts.speech.microsoft.com/cognitiveservices/voices/list"
    )


def test_speech_url_rewrites_foundry_host() -> None:
    """Foundry ``services.ai.azure.com`` hosts map to the Speech subdomain."""
    assert build_tts_voices_url("https://r.services.ai.azure.com/") == (
        "https://r.cognitiveservices.azure.com/tts/cognitiveservices/voices/list"
    )
    assert build_tts_url("https://r.services.ai.azure.com/") == (
        "https://r.cognitiveservices.azure.com/tts/cognitiveservices/v1"
    )
    assert build_stt_url(
        "https://r.services.ai.azure.com/", "en-US", "simple", "masked"
    ) == (
        "https://r.cognitiveservices.azure.com"
        "/stt/speech/recognition/conversation/cognitiveservices/v1"
        "?language=en-US&format=simple&profanity=masked"
    )


def test_reasoning_effort_options() -> None:
    assert reasoning_effort_options("gpt-5.6-sol") == [
        "none",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    ]
    assert reasoning_effort_options("gpt-5-mini") == [
        "minimal",
        "low",
        "medium",
        "high",
    ]
    assert reasoning_effort_options("gpt-4o") is None


def test_build_ssml_escapes_and_wraps() -> None:
    ssml = _build_ssml(
        "Tom & Jerry",
        "en-US",
        "en-US-JennyNeural",
        rate="+10%",
        pitch=None,
        volume=None,
        style="cheerful",
        style_degree="1.5",
        role=None,
    )
    assert 'name="en-US-JennyNeural"' in ssml
    assert "Tom &amp; Jerry" in ssml
    assert 'rate="+10%"' in ssml
    assert 'style="cheerful"' in ssml
    assert 'styledegree="1.5"' in ssml
    assert "mstts:express-as" in ssml
