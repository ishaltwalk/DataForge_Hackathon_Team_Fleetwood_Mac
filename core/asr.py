"""Phoneme-level ASR.

facebook/wav2vec2-lv-60-espeak-cv-ft transcribes audio straight into espeak
phones, no training needed and no word-level step in between. That matters:
a word-level transcript would tell you the learner said "sink" instead of
"think", but not that the error was one feature away on a single phone.

The model is about 1.2 GB on first use. Warm it at app start, never inside a
request. In Streamlit wrap _load() in @st.cache_resource.
"""

import librosa
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from core.phones import normalize

MODEL_ID = "facebook/wav2vec2-lv-60-espeak-cv-ft"
SAMPLE_RATE = 16000

_processor = None
_model = None


def _load():
    global _processor, _model
    if _model is None:
        _processor = Wav2Vec2Processor.from_pretrained(MODEL_ID)
        _model = Wav2Vec2ForCTC.from_pretrained(MODEL_ID)
        _model.eval()
    return _processor, _model


def transcribe(wav_path: str) -> list[str]:
    """Audio file -> list of phone segments, same inventory as the reference."""
    processor, model = _load()

    # Resampled to 16 kHz mono regardless of what the recorder produced. An
    # 8 kHz phone-quality input degrades this model badly, and the failure
    # looks like bad pronunciation rather than bad audio.
    audio, _ = librosa.load(wav_path, sr=SAMPLE_RATE, mono=True)

    inputs = processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    ids = torch.argmax(logits, dim=-1)
    raw = processor.batch_decode(ids)[0]
    return normalize(raw)


def transcribe_bytes(wav_bytes: bytes) -> list[str]:
    """Same, for audio held in memory (Streamlit's recorder returns bytes)."""
    import io

    processor, model = _load()
    audio, _ = librosa.load(io.BytesIO(wav_bytes), sr=SAMPLE_RATE, mono=True)
    inputs = processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    ids = torch.argmax(logits, dim=-1)
    return normalize(processor.batch_decode(ids)[0])
