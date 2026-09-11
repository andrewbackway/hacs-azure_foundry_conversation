"""Live smoke test for the Azure AI Foundry + Azure Speech endpoints.

Reads credentials from a git-ignored .env at the repo root and exercises the
same endpoints the integration uses, with the standard library only (no HA, no
openai, no httpx). It never prints secrets.

Checks:
  1. Responses API  - basic text generation with reasoning.
  2. Responses API  - function tool + reasoning (the combination that fails on
     Chat Completions for gpt-5.6 models).
  3. TTS voices/list - lists available Azure Speech voices.
  4. TTS synthesis   - synthesizes a phrase to 16 kHz PCM WAV.
  5. STT round-trip  - feeds that audio back to STT and checks the text.

Run: python scripts/smoketest.py
Exits non-zero if any check fails. Audio is written to smoketest-output/.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
OUT_DIR = ROOT / "smoketest-output"


def load_env() -> dict[str, str]:
    """Parse simple KEY=VALUE lines from the .env file."""
    if not ENV_PATH.exists():
        print(f"FAIL: {ENV_PATH} not found")
        sys.exit(2)
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def _request(
    url: str, *, method: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def _speech_path(endpoint: str, custom: str, regional: str) -> str:
    host = endpoint.split("//", 1)[-1].lower()
    base = endpoint.rstrip("/")
    marker = ".services.ai.azure.com"
    if marker in host:
        base = base[: base.lower().index(marker)] + ".cognitiveservices.azure.com"
        host = base.split("//", 1)[-1].lower()
    return base + (custom if "cognitiveservices" in host else regional)


def _extract_output(payload: dict) -> tuple[str, bool]:
    """Return (text, has_function_call) from a Responses payload."""
    text_parts: list[str] = []
    has_tool = False
    for item in payload.get("output", []):
        itype = item.get("type")
        if itype == "function_call":
            has_tool = True
        elif itype == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text_parts.append(part.get("text", ""))
    return "".join(text_parts), has_tool


def check_responses_basic(env: dict[str, str]) -> bool:
    endpoint = env["AZURE_FOUNDRY_ENDPOINT"].rstrip("/")
    model = env.get("AZURE_FOUNDRY_DEPLOYMENT", "gpt-5.6-sol")
    url = f"{endpoint}/openai/v1/responses"
    body = json.dumps(
        {
            "model": model,
            "input": "Reply with exactly one word: pong.",
            "max_output_tokens": 2000,
            "reasoning": {"effort": "low"},
        }
    ).encode()
    status, raw = _request(
        url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-key": env["AZURE_FOUNDRY_API_KEY"],
        },
        body=body,
    )
    if status != 200:
        snippet = raw[:400].decode(errors="replace")
        print(f"FAIL responses(basic): HTTP {status}: {snippet}")
        return False
    text, _ = _extract_output(json.loads(raw))
    print(f"PASS responses(basic): status={status} text={text.strip()!r}")
    return True


def check_responses_tools(env: dict[str, str]) -> bool:
    endpoint = env["AZURE_FOUNDRY_ENDPOINT"].rstrip("/")
    model = env.get("AZURE_FOUNDRY_DEPLOYMENT", "gpt-5.6-sol")
    url = f"{endpoint}/openai/v1/responses"
    body = json.dumps(
        {
            "model": model,
            "input": "What is the weather in Seattle? Call the tool to find out.",
            "reasoning": {"effort": "low"},
            "max_output_tokens": 2000,
            "tools": [
                {
                    "type": "function",
                    "name": "get_weather",
                    "description": "Get the current weather for a city.",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                }
            ],
        }
    ).encode()
    status, raw = _request(
        url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-key": env["AZURE_FOUNDRY_API_KEY"],
        },
        body=body,
    )
    if status != 200:
        snippet = raw[:400].decode(errors="replace")
        print(f"FAIL responses(tools): HTTP {status}: {snippet}")
        return False
    _text, has_tool = _extract_output(json.loads(raw))
    if not has_tool:
        print("FAIL responses(tools): no function_call in output")
        return False
    print("PASS responses(tools): tools + reasoning accepted; function_call returned")
    return True


def check_voices(env: dict[str, str]) -> list[str]:
    endpoint = env.get("AZURE_SPEECH_ENDPOINT")
    key = env.get("AZURE_SPEECH_API_KEY")
    if not endpoint or not key:
        print("SKIP voices: AZURE_SPEECH_ENDPOINT/API_KEY not set")
        return []
    url = _speech_path(
        endpoint,
        "/tts/cognitiveservices/voices/list",
        "/cognitiveservices/voices/list",
    )
    status, raw = _request(
        url, method="GET", headers={"Ocp-Apim-Subscription-Key": key}, body=None
    )
    if status != 200:
        print(f"FAIL voices: HTTP {status}: {raw[:300].decode(errors='replace')}")
        return []
    voices = json.loads(raw)
    en = [v["ShortName"] for v in voices if v.get("Locale", "").startswith("en")]
    print(f"PASS voices: {len(voices)} total, {len(en)} en-*; sample={en[:3]}")
    return [v["ShortName"] for v in voices]


def check_tts(env: dict[str, str], voice: str) -> bytes | None:
    endpoint = env.get("AZURE_SPEECH_ENDPOINT")
    key = env.get("AZURE_SPEECH_API_KEY")
    if not endpoint or not key:
        print("SKIP tts: AZURE_SPEECH_ENDPOINT/API_KEY not set")
        return None
    url = _speech_path(endpoint, "/tts/cognitiveservices/v1", "/cognitiveservices/v1")
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="en-US"><voice name="{voice}">'
        "Home Assistant smoke test.</voice></speak>"
    )
    status, raw = _request(
        url,
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
            "User-Agent": "azure-foundry-smoketest",
        },
        body=ssml.encode("utf-8"),
    )
    if status != 200:
        print(f"FAIL tts: HTTP {status}: {raw[:300].decode(errors='replace')}")
        return None
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "tts.wav").write_bytes(raw)
    print(f"PASS tts: {len(raw)} bytes WAV written to smoketest-output/tts.wav")
    return raw


def check_stt(env: dict[str, str], wav: bytes) -> bool:
    endpoint = env.get("AZURE_SPEECH_ENDPOINT")
    key = env.get("AZURE_SPEECH_API_KEY")
    if not endpoint or not key:
        print("SKIP stt: AZURE_SPEECH_ENDPOINT/API_KEY not set")
        return True
    base = _speech_path(
        endpoint,
        "/stt/speech/recognition/conversation/cognitiveservices/v1",
        "/speech/recognition/conversation/cognitiveservices/v1",
    )
    url = f"{base}?language=en-US&format=simple&profanity=masked"
    status, raw = _request(
        url,
        method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
        },
        body=wav,
    )
    if status != 200:
        print(f"FAIL stt: HTTP {status}: {raw[:300].decode(errors='replace')}")
        return False
    body = json.loads(raw)
    text = body.get("DisplayText", "")
    reco = body.get("RecognitionStatus")
    ok = reco == "Success"
    label = "PASS" if ok else "FAIL"
    print(f"{label} stt: status={reco} text={text!r}")
    return ok


def main() -> int:
    env = load_env()
    results: list[bool] = []

    results.append(check_responses_basic(env))
    results.append(check_responses_tools(env))

    voices = check_voices(env)
    wav = None
    if voices:
        voice = "en-US-JennyNeural" if "en-US-JennyNeural" in voices else voices[0]
        wav = check_tts(env, voice)
    if wav:
        results.append(check_stt(env, wav))

    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
