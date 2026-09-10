"""Phoneme-level ASR via Whisper (HF Inference API) + espeak phonemization.

Architecture:
  1. Audio -> Whisper (via router.huggingface.co) -> word-level transcript
  2. Transcript -> espeak-ng (local) -> IPA phone sequence
  3. Phone sequence -> scorer (unchanged)

This avoids the 1.2 GB wav2vec2 model download entirely. The trade-off is
that word-level ASR normalizes pronunciation before we see it: if someone
says "think" with a slightly wrong vowel, Whisper still transcribes "think"
and espeak gives the canonical phones. Phone-level ASR would have caught
the vowel. But the errors this app targets -- th/s, r/l, v/w, dropped
syllables -- all change the word Whisper hears, so they are still caught.

LANGUAGE CANNOT BE PINNED HERE. Whisper itself supports task="transcribe"
and language="en", but those are Transformers-level generation controls. The
Inference Providers router this module posts to accepts audio bytes and
nothing else; sending them as parameters comes back as an unexpected keyword
argument. So Whisper auto-detects the language on every request.

That matters because the input this app sends is, by design, badly
mispronounced English. That is exactly the input that makes auto-detection
guess wrong, and a wrong guess comes back as another script or a
translation. Phonemizing that as en-us produces a phone sequence that has
nothing to do with what was said, and the scorer then blames a syllable for
it. _looks_english() below rejects those before they reach the scorer.

Set HF_API_TOKEN in .env with a free Hugging Face token.
"""

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
    """Validate the token is set. No local model to load."""
    if not _HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN is not set. Add it to your .env file. "
            "Get a free token at https://huggingface.co/settings/tokens"
        )


def _whisper_transcribe(wav_bytes: bytes) -> str:
    """Send audio to Whisper via HF router, return the word-level transcript."""
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
    """Convert a word-level transcript to IPA phones using espeak-ng.

    Uses the phonemizer library (already a project dependency) which wraps
    espeak-ng -- the same engine that generated the reference phones in
    data/words.json. This keeps both sides of the comparison on the same
    phonetic yardstick.
    """
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
    """Audio file -> list of phone segments, same inventory as the reference."""
    with open(wav_path, "rb") as f:
        return transcribe_bytes(f.read())


def _looks_english(text: str) -> bool:
    """Reject a transcript that is not an attempt at an English word.

    Deliberately crude: one Latin letter is enough. The job is to catch the
    detection failures (Cyrillic, CJK, Arabic script, a translated sentence in
    another alphabet), not to police spelling. Anything stricter would start
    rejecting real attempts, and a learner being told they said nothing when
    they did is a worse failure than a rare bad transcript getting through.

    An empty transcript is already handled upstream and is not this check's
    business.
    """
    return bool(_LATIN.search(text))


def transcribe_bytes(wav_bytes: bytes) -> list[str]:
    """Same, for audio held in memory (Streamlit's recorder returns bytes)."""
    transcript = _whisper_transcribe(wav_bytes)
    print(f"[asr] Whisper heard: {transcript!r}", flush=True)

    if transcript and not _looks_english(transcript):
        # Returning [] routes this into the existing no_speech branch, which
        # does not consume a retry. That is the honest classification: the
        # recogniser failed, the learner did not. Charging them an attempt for
        # a language-detection miss would be punishing them for our stack.
        print(
            f"[asr] transcript is not English, treating as no speech: {transcript!r}",
            flush=True,
        )
        return []

    return _words_to_phones(transcript)
