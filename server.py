import base64
import json
import os
import uuid
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402

from core import asr, coach  # noqa: E402
from core.score import validate_bank  # noqa: E402
from core.session import MAX_ATTEMPTS, Session  # noqa: E402
from core.speech import CONFIG_LINE, SPEAKER  # noqa: E402
from rime_tts.synthesize import AUDIO_FORMAT, LANGUAGE, MODEL_ID  # noqa: E402

BANK_PATH = Path(__file__).parent / "data" / "words.json"

MAX_SESSIONS = 500
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
CORS(app, origins=[r"http://localhost:*", r"http://127.0.0.1:*"])

_bank: list[dict] | None = None
_by_id: dict[str, dict] = {}
_sessions: "OrderedDict[tuple[str, str], Session]" = OrderedDict()


def load_bank() -> list[dict]:
    global _bank
    if _bank is None:
        bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
        validate_bank(bank)
        _bank = bank
        _by_id.clear()
        _by_id.update({e["id"]: e for e in bank})
    return _bank


def entry_or_404(word_id: str):
    load_bank()
    return _by_id.get(word_id)


def get_session(client_id: str, word_id: str, entry: dict) -> Session:
    key = (client_id, word_id)
    sess = _sessions.get(key)
    if sess is None:
        sess = Session(entry)
        _sessions[key] = sess
        while len(_sessions) > MAX_SESSIONS:
            _sessions.popitem(last=False)
    _sessions.move_to_end(key)
    return sess


def clear_session(client_id: str, word_id: str) -> None:
    _sessions.pop((client_id, word_id), None)


def client_id() -> str:
    return request.headers.get("X-Client-Id") or request.form.get("client_id") or "anon"


def data_url(audio: bytes) -> str:
    return "data:audio/wav;base64," + base64.b64encode(audio).decode("ascii")


def speech_fields(spoken) -> dict:
    if spoken is None:
        return {"audioUrl": None, "provider": None, "providerError": None}
    return {
        "audioUrl": data_url(spoken.audio) if spoken.ok else None,
        "provider": spoken.provider,
        "providerError": spoken.reason,
    }


def summarize(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "display": entry["display"],
        "trap": entry["trap"],
        "tier": entry["tier"],
        "difficultyScore": entry["difficulty_score"],
        "syllableCount": entry["syllable_count"],
    }


@app.get("/api/config")
def get_config():
    load_bank()
    return jsonify(
        {
            "speech": CONFIG_LINE,
            "modelId": MODEL_ID,
            "speaker": SPEAKER,
            "language": LANGUAGE,
            "audioFormat": AUDIO_FORMAT,
            "transport": "https request/response, wav data url",
            "asrModel": asr.MODEL_ID,
            "maxAttempts": MAX_ATTEMPTS,
            "words": len(_bank or []),
            "clientId": uuid.uuid4().hex,
        }
    )


@app.get("/api/words")
def get_words():
    bank = load_bank()
    q = (request.args.get("q") or "").strip().lower()
    try:
        limit = min(int(request.args.get("limit", 60)), 200)
    except ValueError:
        limit = 60

    if not q:
        matches = bank[:limit]
    else:
        prefix = [e for e in bank if e["id"].startswith(q)]
        inner = [e for e in bank if q in e["id"] and not e["id"].startswith(q)]
        matches = (prefix + inner)[:limit]

    return jsonify({"words": [summarize(e) for e in matches], "total": len(bank)})


@app.get("/api/words/<word_id>")
def get_word(word_id):
    entry = entry_or_404(word_id)
    if entry is None:
        return jsonify({"error": "unknown word id"}), 404
    detail = summarize(entry)
    detail["ipaSyllables"] = ["".join(s) for s in entry["ipa_syllables"]]
    return jsonify(detail)


@app.get("/api/prompt/<word_id>")
def get_prompt(word_id):
    entry = entry_or_404(word_id)
    if entry is None:
        return jsonify({"error": "unknown word id"}), 404
    return jsonify(speech_fields(coach.prompt(entry)))


@app.post("/api/attempt")
def submit_attempt():
    word_id = request.form.get("word_id")
    audio_file = request.files.get("audio")
    if not word_id or audio_file is None:
        return jsonify({"error": "word_id and audio are required"}), 400

    entry = entry_or_404(word_id)
    if entry is None:
        return jsonify({"error": "unknown word id"}), 404

    raw = audio_file.read()
    if not raw:
        return jsonify({"error": "empty audio upload"}), 400

    cid = client_id()
    sess = get_session(cid, word_id, entry)

    inspect_upload(raw)

    try:
        heard = asr.transcribe_bytes(raw)
        print(
            f"[attempt] word={word_id} bytes={len(raw)} "
            f"phones={len(heard)} heard={''.join(heard) or '(nothing)'}",
            flush=True,
        )
    except Exception as exc:
        return jsonify({"error": f"could not decode the recording: {exc}"}), 415

    turn = coach.take_turn(entry, heard, sess)

    if turn.state in ("pass", "give_up"):
        clear_session(cid, word_id)

    response = {
        "state": turn.state,
        "attempts": turn.attempts,
        "maxAttempts": sess.max_attempts,
        "changedSyllable": turn.changed_syllable,
        "coaching": turn.coaching,
        "result": {
            "score": turn.result["score"],
            "passed": turn.result.get("passed", False),
            "wrongSyllables": sorted(turn.wrong),
            "syllableCosts": turn.result.get("syllable_costs", []),
            "worstSyllable": turn.result.get("worst_syllable"),
            "heardPhones": turn.result.get("heard", []),
            "diff": turn.diff if turn.result.get("ops") else "",
        },
        "ipaSyllables": ["".join(s) for s in entry["ipa_syllables"]],
    }
    response.update(speech_fields(turn.spoken))
    return jsonify(response)


@app.errorhandler(413)
def too_large(_exc):
    return jsonify({"error": "recording too large"}), 413


def inspect_upload(raw: bytes) -> None:
    try:
        import io

        import numpy as np
        import soundfile as sf

        audio, rate = sf.read(io.BytesIO(raw), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        peak = float(np.abs(audio).max()) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(audio**2))) if audio.size else 0.0

        path = Path(__file__).parent / "debug_last_attempt.wav"
        path.write_bytes(raw)

        print(
            f"[audio] rate={rate} samples={audio.size} "
            f"seconds={audio.size / rate:.2f} peak={peak:.4f} rms={rms:.4f} "
            f"-> saved {path.name}",
            flush=True,
        )
    except Exception as exc:
        print(f"[audio] could not inspect the upload: {exc}", flush=True)


def warm() -> None:
    load_bank()
    print(f"word bank loaded: {len(_bank)} entries")
    asr._load()
    print(f"asr ready (HF Inference API: {asr.MODEL_ID})")


if __name__ == "__main__":
    warm()
    app.run(port=8000, debug=False)
