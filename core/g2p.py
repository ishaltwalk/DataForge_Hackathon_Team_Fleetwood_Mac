import os
import sys

_WINDOWS_DEFAULT = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"

if sys.platform == "win32" and "PHONEMIZER_ESPEAK_LIBRARY" not in os.environ:
    if os.path.exists(_WINDOWS_DEFAULT):
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = _WINDOWS_DEFAULT

from phonemizer import phonemize as _phonemize  # noqa: E402

from core.phones import normalize  # noqa: E402

LANGUAGE = "en-us"


def espeak_phones(word: str) -> list[str]:
    raw = _phonemize(
        word,
        language=LANGUAGE,
        backend="espeak",
        strip=True,
        with_stress=False,
        preserve_punctuation=False,
    )
    return normalize(raw)


def espeak_version() -> str:
    from phonemizer.backend import EspeakBackend

    return str(EspeakBackend.version())
