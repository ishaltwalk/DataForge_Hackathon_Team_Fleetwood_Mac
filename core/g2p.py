"""espeak-ng grapheme-to-phoneme, used to build the scoring reference.

This runs offline, once per word, while building data/words.json. It is NOT
called at runtime; runtime reads the committed word bank. That is deliberate:
the reference is then a committed artifact anyone can diff and reproduce,
which is what the evidence rubric asks for.

Why espeak specifically: the ASR model (facebook/wav2vec2-lv-60-espeak-cv-ft)
was fine-tuned on espeak-labelled data, so its output lives in espeak's phone
inventory. Generating the reference with the same engine means both sides of
the comparison use one phonetic yardstick, and a distance reflects a real
pronunciation difference rather than two tagsets disagreeing.

Windows note: phonemizer is a wrapper, the espeak-ng binary must be installed
separately. If the DLL is not found, set PHONEMIZER_ESPEAK_LIBRARY to
C:\\Program Files\\eSpeak NG\\libespeak-ng.dll before importing.
"""

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
    """Canonical phone sequence for a written word."""
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
    """Recorded in the evidence file so the reference is reproducible."""
    from phonemizer.backend import EspeakBackend

    return str(EspeakBackend.version())
