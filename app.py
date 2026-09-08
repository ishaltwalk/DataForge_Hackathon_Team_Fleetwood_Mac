"""Pronunciation coach, Streamlit build.

A second front end over the same core, kept because it is the fastest way to
reproduce a scoring result without a browser, and judges asked to reproduce
behaviour will reach for it. It renders core.coach.take_turn and decides
nothing on its own; if this file and the React app ever disagree about which
syllable was wrong, that is a bug in one of the two renderers, not a
difference of opinion between two pipelines.

Two things on screen are requirements rather than decoration:

  * the active provider line, because fallback behavior has to be observable
  * corrections as audio only, never as readable IPA, because if the fix can be
    read then removing the voice leaves the product intact

Run:  streamlit run app.py
"""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from core import coach, session  # noqa: E402
from core.score import validate_bank  # noqa: E402
from core.speech import CONFIG_LINE  # noqa: E402

BANK_PATH = Path(__file__).parent / "data" / "words.json"

st.set_page_config(page_title="Pronunciation coach", page_icon="\N{SPEAKING HEAD IN SILHOUETTE}")


@st.cache_resource
def warm_asr():
    """Loaded once. A 1.2 GB model load inside a request wrecks the demo."""
    from core import asr

    asr._load()
    return asr


@st.cache_data
def load_bank():
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    validate_bank(bank)
    return bank


def play(spoken, label):
    """Audio if Rime answered, a disclosed failure if it did not. Never a
    silent substitution: see core/speech.py."""
    if spoken is None:
        return
    if spoken.ok:
        st.audio(spoken.audio, format="audio/wav")
        st.caption(f"{label} - provider: {spoken.provider}")
    else:
        st.error(f"{label} unavailable. Provider: {spoken.provider}. {spoken.reason}")


bank = load_bank()
by_id = {e["id"]: e for e in bank}

st.title("Pronunciation coach")
st.caption(f"Speech: {CONFIG_LINE}")

# 5000 entries in a selectbox is slow and unusable. Filter first.
query = st.text_input("Find a word", "")
ids = [e["id"] for e in bank if query.lower() in e["id"]][:200]
if not ids:
    st.warning("No word matches that.")
    st.stop()

word_id = st.selectbox("Word", ids, format_func=lambda w: by_id[w]["display"])
entry = by_id[word_id]

if st.session_state.get("word") != word_id:
    st.session_state["word"] = word_id
    st.session_state["session"] = session.Session(entry)

sess = st.session_state["session"]

st.write(f"Trap: {entry['trap']}")

if st.button("Hear it"):
    play(coach.prompt(entry), "Model pronunciation")

clip = st.audio_input("Now say it")

if clip is not None and st.button("Score my attempt"):
    asr = warm_asr()
    heard = asr.transcribe_bytes(clip.getvalue())
    turn = coach.take_turn(entry, heard, sess)

    if turn.state == "no_speech":
        st.warning("I did not hear anything. Check the mic and try again.")
    else:
        st.metric("Score", turn.result["score"])

        cols = st.columns(len(entry["ipa_syllables"]))
        for i, (col, syl) in enumerate(zip(cols, entry["ipa_syllables"])):
            text = "".join(syl)
            (col.error if i in turn.wrong else col.success)(text)

        with st.expander("Phone-level diff"):
            st.code(turn.diff)

        if turn.state == "pass":
            st.success("That one is right. Pick another word.")
            st.session_state["session"] = session.Session(entry)
        elif turn.state == "give_up":
            st.info("Let's move on. Here it is once more at normal speed.")
            play(turn.spoken, "Model pronunciation")
            st.session_state["session"] = session.Session(entry)
        else:
            if turn.changed_syllable:
                st.caption("Different syllable this time.")
            if turn.coaching:
                st.caption(turn.coaching)
            play(turn.spoken, "Correction")

if sess.attempts:
    st.divider()
    st.caption(f"Attempts on this word: {sess.attempts} of {sess.max_attempts}")
