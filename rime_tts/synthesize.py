"""Rime text to speech. The only speech path in the judged flow.

Merged from two branches. Three things changed and each fixed a real failure:

  * The key is read at CALL time, not import time. Reading it at import made
    `import rime_tts.synthesize` raise KeyError on any machine without the
    variable set, which took down the whole Flask app including the routes
    that never speak.
  * synthesize() returns BYTES. It used to write to a fixed output path, so
    two overlapping requests wrote the same file and one user could hear the
    other user's correction. Callers that want a file use save().
  * Failures raise RimeError instead of leaking urllib exceptions, so the
    caller can label the active provider honestly when Rime is down.

Config used in the judged flow, kept in one place because the README and
RIME_EVIDENCE.md both have to state it exactly:

    endpoint  https://users.rime.ai/v1/rime-tts   (POST, JSON, non-streaming)
    modelId   mistv3
    speaker   falcon
    language  eng
    audio     audio/wav
    transport HTTPS request/response, played back as a data URL

Bracket controls, all three of which the correction depends on:

    phonemizeBetweenBrackets   {rpa} is spoken as those exact phones
    inlineSpeedAlpha           [chunk] is slowed, one value per bracketed span
    pauseBetweenBrackets       <300> gaps. Off by default, see core/correct.py
"""

import json
import os
import urllib.error
import urllib.request

SYNTH_URL = "https://users.rime.ai/v1/rime-tts"

MODEL_ID = "mistv3"
DEFAULT_SPEAKER = "falcon"
LANGUAGE = "eng"
AUDIO_FORMAT = "audio/wav"

TIMEOUT_SECONDS = 20


class RimeError(RuntimeError):
    """Rime did not return audio. Carries enough detail to show a user."""


def api_key() -> str:
    key = os.environ.get("RIME_API_KEY", "").strip()
    if not key:
        raise RimeError(
            "RIME_API_KEY is not set. Copy .env.example to .env and put the "
            "key there; it is read at call time and never committed."
        )
    return key


def build_payload(
    text: str,
    speaker: str = DEFAULT_SPEAKER,
    rpa: str | None = None,
    phonemize_brackets: bool = False,
    pause_brackets: bool = False,
    inline_speed: str | None = None,
) -> dict:
    """Separated from the network call so tests can assert on it offline.

    tests/test_payload.py checks the two rules that are easy to get wrong and
    impossible to notice by ear on a good clip:
      * phonemizeBetweenBrackets goes on whenever {} is present, even if the
        caller forgot to ask for it
      * inlineSpeedAlpha carries one value per bracketed span
    """
    payload_text = "{" + rpa + "}" if rpa else text

    payload: dict = {
        "text": payload_text,
        "speaker": speaker,
        "modelId": MODEL_ID,
        "lang": LANGUAGE,
    }

    if phonemize_brackets or ("{" in payload_text and "}" in payload_text):
        payload["phonemizeBetweenBrackets"] = True
    if pause_brackets:
        payload["pauseBetweenBrackets"] = True
    if inline_speed:
        payload["inlineSpeedAlpha"] = inline_speed

    return payload


def synthesize(
    text: str,
    speaker: str = DEFAULT_SPEAKER,
    rpa: str | None = None,
    phonemize_brackets: bool = False,
    pause_brackets: bool = False,
    inline_speed: str | None = None,
) -> bytes:
    """Text (or an RPA string) to WAV bytes. Raises RimeError on any failure."""
    payload = build_payload(
        text,
        speaker=speaker,
        rpa=rpa,
        phonemize_brackets=phonemize_brackets,
        pause_brackets=pause_brackets,
        inline_speed=inline_speed,
    )

    request = urllib.request.Request(
        SYNTH_URL,
        data=json.dumps(payload).encode("utf8"),
        headers={
            "Accept": AUDIO_FORMAT,
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            audio = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RimeError(f"Rime returned HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RimeError(f"Could not reach Rime: {exc}") from exc

    # A JSON error body served with a 200 is not audio. Catch it here rather
    # than letting the browser fail to decode a 40 byte "wav".
    if not audio.startswith(b"RIFF"):
        raise RimeError(
            "Rime response was not WAV audio: "
            + audio[:200].decode("utf-8", "replace")
        )

    return audio


def save(audio: bytes, output_path: str) -> str:
    """Write bytes to disk. Used by the offline scripts, not by the server."""
    with open(output_path, "wb") as f:
        f.write(audio)
    return output_path


if __name__ == "__main__":
    save(synthesize("Hello! This is Rime speaking."), "output.wav")
    print("Audio saved to output.wav")
