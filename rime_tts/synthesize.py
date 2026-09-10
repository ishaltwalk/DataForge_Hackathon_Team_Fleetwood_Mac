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
    pass


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

    if not audio.startswith(b"RIFF"):
        raise RimeError(
            "Rime response was not WAV audio: "
            + audio[:200].decode("utf-8", "replace")
        )

    return audio


def save(audio: bytes, output_path: str) -> str:
    with open(output_path, "wb") as f:
        f.write(audio)
    return output_path


if __name__ == "__main__":
    save(synthesize("Hello! This is Rime speaking."), "output.wav")
    print("Audio saved to output.wav")
