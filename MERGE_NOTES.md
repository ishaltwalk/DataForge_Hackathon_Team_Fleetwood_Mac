# Merge notes

Two branches were merged into this tree: the repo branch (scoring core,
evidence, offline scripts) and a second branch that had added a React front end
and a Flask server on top of an older copy of the same core.

They were not two products. They were forks of one base that had drifted, so
the merge is repo core plus the second branch's front end, not a blend.

Every item below is a defect that existed in one of the two branches and is
fixed here. Ordered by how badly it would have broken a live demo.

---

## 1. Credential exposure

The second branch shipped a committed `.env` containing a live
`RIME_API_KEY`.

**Rotate that key.** The eligibility list in the brief disqualifies a
submission that exposes a live credential. The file is not in this tree,
`.gitignore` already excludes `.env` and `.env.*`, and `.env.example` carries a
placeholder only.

## 2. Server crashed on every scored attempt

`server.py` called `correct.build_correction(entry, result["worst_syllable"], sess.attempts)`,
three positional arguments against a two-argument signature. The current
`build_correction(entry, wrong_indices: set[int])` takes a SET of syllable
indices, because a badly mispronounced word can have more than one syllable
over threshold and each one needs its own bracketed span.

Every `/api/attempt` would have raised `TypeError`.

## 3. Word bank had no RPA

The second branch's `data/words.json` had `rpa_syllables: []` on all 5000
entries. `validate_bank()` asserts the IPA and RPA syllable arrays are the same
length, so the server would have died at startup, and had it not, every
correction would have been an empty `{}` chunk.

The repo bank is used. Verified: 5000 entries, zero length mismatches, zero
empty chunks.

## 4. Uploaded audio the server could not open

`src/lib/recorder.js` uploaded the raw `MediaRecorder` blob, which in Chrome is
webm/opus. Scoring uses `librosa`, which opens WAV and FLAC through `soundfile`
and shells out to `ffmpeg` for anything else. On a machine without ffmpeg every
attempt failed to decode; on a machine with it, scoring silently depended on an
undeclared binary.

The browser now decodes with `decodeAudioData` and resamples through an
`OfflineAudioContext` to the exact 16 kHz mono the wav2vec2 model wants, then
uploads 16-bit PCM WAV. No server-side ffmpeg, and the resample happens before
quality is lost rather than after.

## 5. Importing the TTS module could take down the whole server

`RIME_API_KEY = os.environ["RIME_API_KEY"]` ran at module import, so
`import rime_tts.synthesize` raised `KeyError` on any machine without the
variable set. That killed the entire Flask app, including routes that never
speak. Same bug in `rime_tts/phonemize.py`.

The key is read at call time now, through `api_key()`, which raises a
`RimeError` with an instruction instead of a bare `KeyError`.

## 6. Concurrent requests overwrote each other's audio

`synthesize()` wrote to a fixed `output_path`, defaulting to a single
`temp_correction.wav`. Two overlapping requests wrote the same file and one
user could hear the other user's correction.

`synthesize()` returns bytes. `save(audio, path)` exists for the offline
scripts that genuinely want a file.

## 7. Sessions were shared between users

`_sessions` was keyed on `word_id` alone, so two people practising the same word
shared one give-up counter. The dict also grew without bound and was never
cleared, so a word that had been passed stayed at attempt four forever.

Keyed on `(client_id, word_id)` now, capped at 500 with LRU eviction, cleared
after a pass or a give-up so the next attempt on that word starts a fresh loop.

## 8. The whole word bank was bundled into the front end

`src/lib/api.js` imported `data/words.json` directly. That is 3.3 MB shipped on
first paint, 5000 tiles rendered before the user typed anything, and, worse, a
second copy of the bank in the browser that could drift from the copy the
server scores against.

`/api/words?q=` filters server side and returns a light summary.
`/api/words/<id>` returns one entry. The `rpa_syllables` are never sent to the
browser at all: a correction that can be read is a correction that did not need
voice, which is the eligibility line the product is built around.

Bundle went from 3.3 MB plus code to 204 KB.

## 9. The front end did not render

`App.jsx` read `item.word` and `item.difficulty`. The bank fields are `display`
and a LIST. Every tile rendered a blank name with an `[object Object]` badge.

`PracticeScreen` took a `currentWord` prop while `App` passed `word`, had no
recording UI at all, and called a `/api/tts` route that did not exist.
`RecordButton`, `StateIndicator`, `ProviderBadge` and `ResultPanel` were written
but never mounted.

The screen is rewritten and wired to the real API.

## 10. The acceptance test asserted on the wrong thing

`tests/acceptance.py` asserted `worst_syllable == expected`. `worst_syllable` is
the argmax; the product highlights and slows the THRESHOLD SET from
`core.correct.wrong_syllables`. Those two disagree whenever a second syllable is
also over threshold, so the test could pass while the learner heard a different
syllable corrected.

It now asserts the expected syllable is in the set that actually shipped.

## 11. The README described a flow that does not exist

The README claimed `pauseBetweenBrackets` isolates the syllable. The revision
note at the top of `core/correct.py` records that pauses were tested at several
gap values, made the correction sound worse, and were dropped. The README was
describing an earlier design.

Corrected, and the unused-but-supported status of `pauseBetweenBrackets` is now
stated explicitly in both the README and `RIME_EVIDENCE.md`.

---

## Structural changes

### `core/coach.py` (new)

The Streamlit app and the Flask API each had their own copy of the same four
steps: score, decide which syllables were wrong, build a payload, speak it. They
had already diverged on step two, one using `worst_syllable` and the other using
the threshold set.

That produces the worst bug this product can have: the screen highlights one
syllable while Rime enunciates another. It is invisible in code review and
obvious to a judge wearing headphones.

`take_turn()` runs the sequence once. A front end may decide how to draw a
`Turn`. It may not decide what a `Turn` contains.

### `core/speech.py` (new)

One `speak()` for both front ends, and the place provider observability lives.
Returns a `Spoken` record that always names the provider: `rime` when Rime
produced the WAV, `unavailable` with a reason when it did not.

There is deliberately no server-side second TTS. A different engine cannot speak
an RPA string, so a "fallback correction" would be a model guessing at the exact
word whose pronunciation is in question, which is the failure this product
exists to prevent. The browser voice can read the plain word, but only behind a
visible banner naming it degraded, and only when the user clicks it.

### Vite proxy

`vite.config.js` proxies `/api` to port 8000. The front end had
`http://localhost:8000` hardcoded, which broke CORS preflight on the multipart
upload and broke entirely off localhost. Paths are relative now and the browser
sees one origin.

### `rime_tts/test_*.py` renamed to `manual_check_*.py`

These are interactive listening scripts, not tests. `pytest` collected them from
the repo root and tried to hit the Rime API during a unit test run.

---

## Verification

```
pytest              39 passed, offline, no network
npx vite build      clean, 204 KB
npx eslint .        0 problems
```

API smoke tested end to end with the ASR stubbed: pass, retry, retry, retry,
give-up on the fourth, session reset after give-up, two clients isolated on the
same word, silence not counted as an attempt, 400 on a missing file, 404 on an
unknown word id, and no `rpa_syllables` in any response body.

### New tests

| Test | What it protects |
|---|---|
| `test_coach.py::test_highlighted_syllables_are_the_spoken_ones` | Parses the bracketed chunk indices back out of the text actually sent to Rime and asserts they equal the set the UI was told to highlight |
| `test_coach.py::test_provider_failure_is_reported_not_swallowed` | A Rime outage surfaces as `unavailable` with a reason, never a silent substitution |
| `test_coach.py::test_silence_is_not_an_attempt` | A mic failure does not burn a retry |
| `test_payload.py::test_one_speed_value_per_bracketed_span` | `inlineSpeedAlpha` carries one value per bracketed span; a single value leaves every span after the first at full speed |
| `test_payload.py::test_brackets_force_phonemization_even_if_caller_forgets` | `phonemizeBetweenBrackets` goes on whenever `{}` is present |

---

## Still open

Not bugs, but decide on these before the demo.

* `PASS_THRESHOLD` 0.90 and `SYL_THRESHOLD` 0.05 are the informed starting
  points from `core/score.py`, not calibrated numbers. `scripts/calibrate.py`
  exists to replace them from real clips and has not been run against any.
* `evidence/clips/` is empty. `tests/acceptance.py` needs clean, wrong and noisy
  recordings before it reports anything, and the wrong clips have to be named
  `<word>__<syllable index>.wav` by whoever deliberately broke that syllable.
* `RIME_EVIDENCE.md` still has FILL markers where the recorded numbers go.
* Nothing measures latency, and nothing should claim any until it does.
  Unverified performance numbers get no credit.
