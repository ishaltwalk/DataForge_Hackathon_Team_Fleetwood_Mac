"""One speech entry point, used by both the Flask API and the Streamlit app.

Why this file exists at all: the two front ends each had their own speak()
helper, and they had drifted. One passed inline_speed, the other did not, so
the same word came out slowed in Streamlit and at full speed in the web app.
A correction that is not slowed is not a correction, and nothing in the UI
said which one was right. There is one speak() now and both call it.

PROVIDER OBSERVABILITY
----------------------
The brief requires the active speech provider to be observable and any
fallback to be disclosed. So speak() never raises for a Rime outage and never
silently substitutes anything. It returns a Spoken record that always says
which provider produced the audio:

    provider "rime"        Rime mistv3 produced the WAV. The judged path.
    provider "unavailable" Rime failed. audio is None and reason says why.

There is deliberately no server-side second TTS. A different engine cannot
speak an RPA string, so a "fallback correction" would be the model guessing at
the exact word whose pronunciation is in question, which is the failure this
product exists to prevent. The browser can read the plain word aloud as a
degraded fallback, but only behind a visible banner that names it as such.
See src/components/ProviderBadge.jsx.
"""

from dataclasses import dataclass

from rime_tts.synthesize import (
    AUDIO_FORMAT,
    DEFAULT_SPEAKER,
    LANGUAGE,
    MODEL_ID,
    RimeError,
    synthesize,
)

SPEAKER = DEFAULT_SPEAKER

CONFIG_LINE = f"Rime {MODEL_ID} / {SPEAKER} / {LANGUAGE} / {AUDIO_FORMAT}"


@dataclass
class Spoken:
    audio: bytes | None
    provider: str
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.audio is not None


def speak(**payload) -> Spoken:
    """Take a payload from core.correct and turn it into audio.

    Accepts exactly the keys core.correct.build_prompt and build_correction
    produce. Anything else is a caller bug and should fail loudly here rather
    than be dropped into a Rime request that quietly ignores it.
    """
    allowed = {"text", "phonemize_brackets", "pause_brackets", "inline_speed"}
    unknown = set(payload) - allowed
    assert not unknown, f"unknown speak() keys: {sorted(unknown)}"

    try:
        audio = synthesize(
            payload["text"],
            speaker=SPEAKER,
            phonemize_brackets=payload.get("phonemize_brackets", False),
            pause_brackets=payload.get("pause_brackets", False),
            inline_speed=payload.get("inline_speed"),
        )
    except RimeError as exc:
        return Spoken(audio=None, provider="unavailable", reason=str(exc))

    return Spoken(audio=audio, provider="rime")
