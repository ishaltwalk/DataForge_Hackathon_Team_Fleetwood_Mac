# Submission checklist

Every requirement in the DataForge x Rime brief, mapped to where it is
satisfied. Kept in the repo so a judge can check the mapping rather than take
our word for it.

---

## Eligibility, pass or fail

A submission is not eligible if any of these fail, so they come first.

| Rule | Status | Where |
|---|---|---|
| Verifiable Rime integration in the submitted code | done | `rime_tts/synthesize.py`, `core/speech.py`, `core/correct.py` |
| Rime is not merely a welcome message or optional playback | done | every correction is a Rime call; nothing is ever rendered as readable IPA, so removing speech removes the product |
| A working product path, not static screens or a scripted mock | done | React app on `:5173` plus Flask API on `:8000`; a second front end in `app.py` |
| Demo recorded | done | 4 to 5 minutes, see below |
| No live credential exposed anywhere | done | full `git log --all -p` scanned for key patterns, clean; `.env.example` holds placeholders only |
| Model, voice and language pass the event preflight | **verify at submission time** | `mistv3` / `falcon` / `eng`, checked against Rime's live catalog |

The last row is the only one that can go stale. The brief says to use the
current catalog at submission time rather than a speaker list copied earlier,
so re-check `falcon` on `mistv3` before the deadline.

---

## What to submit

### Demo, 4 to 5 minutes

Six things the brief requires the recording to show:

| Required | Where in the demo |
|---|---|
| Target user and problem | opening, before any clicking |
| Normal end-to-end flow | first word, hear it, say it, get corrected |
| The selected hard voice problem | syllable-level attribution plus guaranteed phonemes |
| **One deliberate stress or failure case** | the overcorrection turn, where fixing one syllable breaks another |
| The result or measurement | the attribution numbers from `evidence/attribution.md` |
| **Which speech provider is active** | the badge, visible in every frame of the practice screen |

The two most commonly missed are bolded. Confirm both are actually on screen
before submitting, and that the runtime does not exceed 5:00.

### Working code

Repository builds from a clean clone. Verified by cloning to a fresh directory
and running the four commands in the README, not by assuming.

```bash
pytest                              # 39 passed
npm run build                       # clean
npx eslint .                        # clean
python scripts/attribution_study.py # regenerates evidence/attribution.md
```

The brief says judges may ask teams to reproduce the demonstrated behaviour, so
everything shown in the recording exists in the repository and runs.

### README

| Required section | Present |
|---|---|
| Setup instructions | yes, including the Python 3.10 to 3.12 constraint and the espeak-ng system dependency |
| Architecture | yes, both the scoring pipeline and the web app request path |
| Third-party services | yes, table with what each is used for and which credential it needs |
| Known limitations | yes, and they are specific rather than hedged |
| Failure behavior | yes, a table of what happens for each failure mode |
| Exact Rime model ID, speaker, language, endpoint, audio format, transport | yes, in the configuration table |

Rime configuration, stated in one place and read from
`rime_tts/synthesize.py` by everything that needs it:

| | |
|---|---|
| Model ID | `mistv3` |
| Speaker | `falcon` |
| Language | `eng` |
| Endpoint | `https://users.rime.ai/v1/rime-tts` |
| Audio format | WAV, `Accept: audio/wav` |
| Transport | HTTPS POST, non-streaming, played back as a data URL |

### Evidence, `evidence/RIME_EVIDENCE.md`

| Required | Section |
|---|---|
| The hard voice claim | 1 |
| Acceptance test, defined before the demo | 2 |
| Procedure | 3 |
| Result | 4.1 to 4.6 |
| Limitations | 5 |
| A repeatable command, script or fixture | throughout: `attribution_study.py`, `acceptance.py`, `ab_clips.py` |

Sections 4.1 to 4.3 need no audio, no network and no key. Sections 4.4 to 4.6
are listening comparisons and need a Rime key plus headphones.

### Configuration hygiene

`.env.example` contains placeholders only:

```
RIME_API_KEY=your_rime_api_key_here
HF_API_TOKEN=your_huggingface_token_here
```

Both keys are read server side. `RIME_API_KEY` is read at call time rather than
import time, deliberately, so importing the module cannot take down routes that
never speak. `.gitignore` excludes `.env` and every `.env.*` except the example.

---

## How judging works, and where each criterion is answered

### Problem and necessity of voice, 25%

The correction is a sound the learner has not yet produced. Printing `θ` is not
a correction; hearing the syllable isolated and slowed is. No correction is
rendered as readable text anywhere in the app, and `rpa_syllables` are never
sent to the browser at all, so this is enforced by the API shape rather than by
front end discipline. Remove speech and there is no product left.

### Hard voice engineering, 25%

Pronunciation, which the brief lists explicitly. The hard part is not detecting
an error, it is locating it precisely enough to act on, then producing
corrective speech that is definitely correct for a word the TTS may never have
seen. Two phonetic alphabets are carried on purpose: espeak phones for scoring,
because the recognition side is espeak too, and Rime's own alphabet for the
correction, because that is what Rime speaks. Both split into the same
syllables in the same order, so no translation table is needed.

### Rime integration and voice experience, 20%

Two Rime endpoints doing different jobs. `/rime-tts` produces every correction,
and the bracket controls are the correction rather than playback bolted onto
the end. `/phonemize` built the reference library the corrections are generated
from. `phonemizeBetweenBrackets` removes the model's G2P guess on words outside
its dictionary; `inlineSpeedAlpha` carries one value per bracketed span, so a
badly mispronounced word with several syllables flagged still slows all of them
rather than only the first.

### Evidence and reproducibility, 20%

`evidence/attribution.md`, regenerated by one deterministic command with no
audio, no network and no key: 19,229 sabotages, 10,190 detected, **10,190 of
10,190 blamed the correct syllable**, zero misattributions, zero false alarms
across 5000 words. The 47% undetected rate is reported rather than hidden,
along with why raising sensitivity would trade against the false-alarm figure
in the wrong direction for this product.

The brief notes that unverified performance numbers receive no credit and that
judges score shipped code and demonstrated behaviour rather than README claims.
Every number above regenerates from the repository.

### Demo clarity, 10%

See the demo table above.

---

## Open items before the deadline

1. **Record and commit the acceptance clips.** `evidence/clips/acceptance/` is
   empty, so `python tests/acceptance.py` reports `0 clips, 0 failures` and
   exits successfully. Naming is `clean/<word>.wav` and
   `wrong/<word>__<n>.wav`, where `n` is the zero-based syllable deliberately
   broken. `.gitignore` re-includes `evidence/clips/**` past the `*.wav` rule,
   so they will commit; confirm with `git status`.
2. **Run `python scripts/ab_clips.py`**, listen, and fill the last column of
   sections 4.4 to 4.6. The clips are the evidence; the words written next to
   them are the finding.
3. **Re-check `falcon` on `mistv3`** against Rime's live catalog at submission
   time.
