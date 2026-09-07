"""Pronunciation coach.

Deliberately small. The brief warns against building a real-time duplex agent
for this track, and nothing here needs interruption handling: the user records,
gets scored, hears a correction, tries again.

Two things on screen are requirements rather than decoration:

  * the active provider line, because fallback behavior has to be observable
  * corrections as audio only, never as readable IPA, because if the fix can be
    read then removing the voice leaves the product intact

Run:  streamlit run app.py
"""

import json
from pathlib import Path

import streamlit as st

from core import correct, session
from core.align import describe
from core.score import score, validate_bank

BANK_PATH = Path(__file__).parent / "data" / "words.json"

MODEL_ID = "mistv3"
SPEAKER = "falcon"
LANGUAGE = "eng"

st.set_page_config(page_title="Pronunciation coach", page_icon="🗣")


@st.cache_resource
def warm_asr():
    """Loaded once. A 1.2 GB model load inside a request wrecks the demo."""
    from core import asr

    asr._load()
    return asr


@st.cache_data
def load_bank():
    bank = json.loads(BANK_PATH.read_text())
    validate_bank(bank)
    return bank


def speak(**kwargs):
    """Route to the Rime module, reporting which provider actually answered."""
    from rime_tts.synthesize import synthesize

    audio = synthesize(
        kwargs["text"],
        speaker=SPEAKER,
        phonemize_brackets=kwargs.get("phonemize_brackets", False),
        pause_brackets=kwargs.get("pause_brackets", False),
        inline_speed=kwargs.get("inline_speed"),
    )
    return audio


bank = load_bank()
by_id = {e["id"]: e for e in bank}

st.title("Pronunciation coach")
st.caption(
    f"Speech: Rime {MODEL_ID} / {SPEAKER} / {LANGUAGE} · "
    f"correction mode: {'syllable isolation' if correct.NEST_SPEED_IN_PHONEME else 'whole word'}"
)

word_id = st.selectbox(
    "Word", [e["id"] for e in bank], format_func=lambda w: by_id[w]["display"]
)
entry = by_id[word_id]

if st.session_state.get("word") != word_id:
    st.session_state["word"] = word_id
    st.session_state["session"] = session.Session(entry)

sess = st.session_state["session"]

st.write(f"Trap: {entry['trap']}")

if st.button("Hear it"):
    st.audio(speak(**correct.build_prompt(entry)), format="audio/wav")

clip = st.audio_input("Now say it")

if clip is not None and st.button("Score my attempt"):
    asr = warm_asr()
    heard = asr.transcribe_bytes(clip.getvalue())
    result = score(entry, heard)
    state = sess.submit(result)

    if state == "no_speech":
        st.warning("I did not hear anything. Check the mic and try again.")
    else:
        st.metric("Score", result["score"])

        cols = st.columns(len(entry["ipa_syllables"]))
        for i, (col, syl) in enumerate(zip(cols, entry["ipa_syllables"])):
            text = "".join(syl)
            if i == result["worst_syllable"] and not result["passed"]:
                col.error(text)
            else:
                col.success(text)

        with st.expander("Phone-level diff"):
            st.code(describe(result["ops"]))

        if state == "pass":
            st.success("That one is right. Pick another word.")
        elif state == "give_up":
            st.info("Let's move on. Here it is once more at normal speed.")
            st.audio(speak(**correct.build_prompt(entry)), format="audio/wav")
        else:
            if sess.moved_on() and sess.attempts > 1:
                st.caption("Different syllable this time.")
            payload = correct.build_correction(
                entry, result["worst_syllable"], sess.attempts
            )
            st.audio(speak(**payload), format="audio/wav")

if sess.attempts:
    st.divider()
    st.caption(f"Attempts on this word: {sess.attempts}")
