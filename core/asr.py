import os
import re

import requests

from core.phones import normalize

MODEL_ID = "openai/whisper-large-v3-turbo"
SAMPLE_RATE = 16000

_HF_API_TOKEN = os.environ.get("HF_API_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_ID}"
_LATIN = re.compile(r"[A-Za-z]")


def _load():
    if not _HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN is not set. Add it to your .env file. "
            "Get a free token at https://huggingface.co/settings/tokens"
        )


def _whisper_transcribe(wav_bytes: bytes) -> str:
    import time

    if not _HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN is not set. Add it to your .env file. "
            "Get a free token at https://huggingface.co/settings/tokens"
        )

    headers = {
        "Authorization": f"Bearer {_HF_API_TOKEN}",
        "Content-Type": "audio/wav",
        "x-wait-for-model": "true",
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                _API_URL,
                headers=headers,
                data=wav_bytes,
                timeout=90,
            )
        except requests.exceptions.ReadTimeout:
            if attempt < max_retries:
                wait = 10 * attempt
                print(f"[asr] Timeout on attempt {attempt}/{max_retries}, retrying in {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(
                "HuggingFace API timed out after 3 attempts. "
                "The Whisper model may be cold-starting — try again in a minute."
            )

        if response.status_code == 503:
            body = response.json()
            wait = min(body.get("estimated_time", 20), 60)
            print(f"[asr] Whisper model loading, waiting {wait:.0f}s...", flush=True)
            time.sleep(wait)
            continue

        break

    response.raise_for_status()
    result = response.json()

    if isinstance(result, dict):
        return result.get("text", "").strip()
    if isinstance(result, list) and result:
        return result[0].get("text", "").strip()
    return ""


def _words_to_phones(text: str) -> list[str]:
    if not text:
        return []

    from phonemizer import phonemize

    raw = phonemize(
        text.lower(),
        language="en-us",
        backend="espeak",
        strip=True,
        with_stress=False,
        preserve_punctuation=False,
    )
    return normalize(raw)


def transcribe(wav_path: str) -> list[str]:
    with open(wav_path, "rb") as f:
        return transcribe_bytes(f.read())


def _looks_english(text: str) -> bool:
    return bool(_LATIN.search(text))


def transcribe_bytes(wav_bytes: bytes) -> list[str]:
    transcript = _whisper_transcribe(wav_bytes)
    print(f"[asr] Whisper heard: {transcript!r}", flush=True)

    if transcript and not _looks_english(transcript):
        print(
            f"[asr] transcript is not English, treating as no speech: {transcript!r}",
            flush=True,
        )
        return []

    return _words_to_phones(transcript)
