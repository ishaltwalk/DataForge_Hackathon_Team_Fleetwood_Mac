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
