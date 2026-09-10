# Pronunciation coach

A learner picks a word with a known trap sound. Rime says it. They say it back.
The system identifies **which syllable** was wrong, and Rime re-speaks the word
with that syllable slowed down while the rest stays at normal speed. Repeat
until correct.

Built for DataForge x Rime. Team Fleetwood Mac.

---

## Why voice is not optional here

Removing speech does not degrade this product, it removes it.

1. **The correction cannot be read.** The output is a sound the learner has not
   yet produced. Printing `θ` on screen is not a correction, hearing the
   syllable isolated and slowed is. No correction is ever rendered as readable
   IPA, deliberately.
2. **Rime specifically, not TTS generally.** `phonemizeBetweenBrackets`
   guarantees the model says the phoneme we specify rather than its own G2P
   guess, which matters because half the word bank is out of Rime's dictionary.
   `inlineSpeedAlpha` slows one syllable without slowing the word around it,
   which is the whole correction: the learner hears the same word, at the same
   pace, with one part stretched. Remove those controls and the corrective
   loop has nothing to say.

   `pauseBetweenBrackets` is supported in `rime_tts/synthesize.py` and is NOT
   used in the judged flow. It was tested at several gap values and made the
   correction sound worse, not clearer, so it was dropped rather than tuned.
   See the revision note at the top of `core/correct.py`.
3. **A second Rime endpoint does structural work.** `/phonemize` builds the
   reference library that the correction is generated from. It is not a
   playback call at the end of somebody else's pipeline.

---

## Architecture

```
  user audio
      |
      v
  Whisper large-v3-turbo (HF API)      core/asr.py
      |  word-level transcript
      v
  espeak-ng phonemization (local)      core/asr.py (_words_to_phones)
      |  phone sequence
      v
  weighted alignment vs reference      core/align.py
      |  per-phoneme diff              (panphon articulatory distance)
      v
  syllable attribution + gates         core/score.py
      |  worst_syllable
      v
  correction payload                   core/correct.py
      |
      v
  Rime mistv3                          rime_tts/synthesize.py
      |  isolated, slowed syllable
      v
  user hears the fix, tries again      core/session.py
```

The reference side runs offline, once:

```
  word -> espeak-ng G2P -> phone sequence -> data/words.json   core/g2p.py
  clean recording -> Rime /phonemize -> RPA string -> data/words.json
```

**Why two references.** The scoring reference is espeak phones, because both the
ASR pipeline (Whisper → espeak) and the reference generation use espeak, keeping
both sides of the distance measurement on one phonetic yardstick. The correction
reference is Rime's own alphabet, because that is what Rime speaks. They are
different alphabets doing different jobs, and no symbol-level translation table
between them is needed: both are split into the same number of syllables in the
same order, so "syllable 2 was wrong" indexes into either one.

---

## Configuration

| | |
|---|---|
| Model ID | `mistv3` |
| Speaker | `falcon` |
| Language | English (`eng`) |
| Endpoint | `https://users.rime.ai/v1/rime-tts` |
| Audio format | WAV (`Accept: audio/wav`) |
| Transport | HTTP POST, non-streaming |
| ASR | `openai/whisper-large-v3-turbo` via HuggingFace Inference API |
| G2P | espeak-ng, local |

**Why non-streaming HTTP.** Utterances are single words, and latency is not the
claim this project makes. WebSocket streaming would add reconnection and
buffering surface for no user-visible gain.

Credentials live in `.env`, server side, never in client code. `.env.example`
ships with placeholders only. Two keys are needed:

* `RIME_API_KEY` — for TTS (Rime)
* `HF_API_TOKEN` — for ASR (HuggingFace Inference API, free tier)

---

## Setup

```bash
git clone <repo>
cd <repo>
pip install -r requirements.txt
cp .env.example .env      # then put your real keys in .env
```

`.env` needs BOTH keys before anything runs. `server.py` validates them at
startup rather than on the first attempt, so a missing key is a refusal to
boot, not a 500 halfway through a demo:

```
RIME_API_KEY=...          # TTS
HF_API_TOKEN=...          # ASR, free tier at huggingface.co/settings/tokens
```

Windows PowerShell equivalent of the copy step:

```powershell
Copy-Item .env.example .env
```

**Python 3.10 to 3.12.** On 3.13 and later, `editdistance` (pulled in by
`panphon`) has no prebuilt wheel, so pip falls back to compiling it from C
source and fails with `Microsoft Visual C++ 14.0 or greater is required`.

**espeak-ng must be installed separately.** `phonemizer` is only a wrapper.

* Linux: `sudo apt install espeak-ng`
* macOS: `brew install espeak-ng`
* Windows: installer from `github.com/espeak-ng/espeak-ng/releases`

On Windows `phonemizer` often cannot find the DLL. `core/g2p.py` sets the path
automatically if espeak is in the default location; otherwise set it yourself
before running:

```powershell
$env:PHONEMIZER_ESPEAK_LIBRARY="C:\Program Files\eSpeak NG\libespeak-ng.dll"
```

Verify:

```bash
python -c "from core.g2p import espeak_phones; print(espeak_phones('thoroughly'))"
```

Standalone `python -c` checks that touch Rime need `load_dotenv()` first.
`rime_tts/synthesize.py` reads `os.environ` at call time and does not load
`.env` itself; only `server.py` and `app.py` do that.

### Run the web app (the judged flow)

Two processes.

```bash
npm install          # once, before anything else

python server.py     # terminal 1, scoring API on :8000
npm run dev          # terminal 2, vite on :5173, proxies /api to :8000
```

Open `http://localhost:5173`. Start `server.py` first: vite proxies `/api` to
`:8000` and the front end fetches `/api/config` on mount, so a cold vite with
no server behind it shows the "cannot reach the scoring server" banner.

`server.py` validates the word bank and `HF_API_TOKEN` before the port opens.
It does NOT check `RIME_API_KEY`: that key is read at call time in
`rime_tts/synthesize.py`, deliberately, so importing the module cannot take
down routes that never speak. The cost is that a missing or expired Rime key
lets the server start clean and then surfaces as `provider: unavailable` on
the first "Hear it". Before a demo, confirm speech separately:

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); from rime_tts.synthesize import synthesize; print(len(synthesize('test')), 'bytes')"
```

If `npm run build` fails with `Module not found: ./lib/api`, `src/lib/` is
missing from your checkout. See the note in `.gitignore` about anchoring
`/lib/`; an unanchored `lib/` matches at any depth and excludes it silently.

### Run the Streamlit app (same core, no browser)

```bash
streamlit run app.py
```

Both front ends call `core/coach.py` and nothing else. They render the same
`Turn`; neither one decides which syllable was wrong. If they ever disagree,
one of the two renderers is broken, not the pipeline.

---

## Reproducing the claims

```bash
pytest                             # 45 unit tests, no audio and no network
npm run build                      # front end compiles
python tests/acceptance.py         # full pipeline against committed clips
python scripts/calibrate.py        # regenerates evidence/calibration.md
```

`pytest.ini` scopes collection to `tests/`. Without it a bare `pytest` also
walks `rime_tts/`, where `manual_check_*.py` hit the live Rime API. Those are
manual checks and are meant to be run by name, not collected:

```bash
python -m rime_tts.manual_check_synthesize    # spends Rime credit
python -m rime_tts.manual_check_phonemize     # spends Rime credit
```

`tests/acceptance.py` reads `evidence/clips/acceptance/`. It reports
`0 clips, 0 failures` on an empty directory rather than erroring, so check the
clip count in the output before treating a green run as evidence.

`tests/acceptance.py` asserts more than pass/fail. On a deliberately
mispronounced clip it asserts the identified syllable is the one the speaker
actually broke, because a tool that failed everything would satisfy a
pass/fail check while being useless.

---

## Known limitations

**Rime docs disagree with Rime behavior, in three places.** All three verified
by live testing, all three noted here because a judge may read the docs.

1. The custom pronunciation page states Mist v3 does not support custom
   pronunciation. It does, on English Mist v3, verified live.
2. Combining `phonemizeBetweenBrackets` with `pauseBetweenBrackets` in one
   request is not documented. It works, but the pauses made the correction
   sound worse and `pauseBetweenBrackets` is off in the judged flow.
3. Nesting `inlineSpeedAlpha` brackets around a phonemized chunk
   (`[{t0xm}]`) is not documented either way. It works: the chunk is both
   phonemized and slowed. Verified live on `agricultural`, `culture` and
   `picture`. The whole correction shape depends on it.

**Articulatory distance underweights perceptually critical contrasts.** `θ`
and `s` differ in few features, so `th -> s` scores as a small error even
though "sink" and "think" are entirely different words to a listener. This is
why the syllable-level gate carries the pass decision and the overall score
does not; see the measurements in `core/score.py`.

**espeak drops vowels in some words.** `reliable` comes out as `ɹlaɪəbəl` with
no vowel after the rhotic, and `wonderful` as `wʌndfəl`. A learner saying those
words correctly would be scored against a reference that is itself wrong.
Affected words were audited out of the word bank rather than corrected, and any
word added later must be checked the same way.

**Diphthongs are two segments, not one.** panphon's segmenter splits `oʊ`, so a
syllable's length in `ipa_syllables` is a segment count. Consistent on both
sides, but it surprises people reading the word bank.

**Not every famous trap word is in the bank.** The 5000 entries are what
survived the espeak audit described above, and several words people reach for
first did not: `squirrel`, `rural`, `clothes`, `February`, `colonel`. Searching
for those returns nothing. `agricultural`, `particularly`, `vulnerable`,
`thoroughly`, `phenomenon` and `culture` are all present and all demo well.

**English only.** Mist v3 custom pronunciation is verified on English only, and
the ASR model, the G2P engine and the word bank are all English.

**Whisper's language cannot be pinned through this endpoint.** `task` and
`language` are Transformers-level generation controls. The Inference Providers
router (`router.huggingface.co`) takes audio bytes and rejects them as
parameters, so auto-detection runs on every request. Badly mispronounced
English is exactly the input that makes detection guess wrong, and a wrong
guess returns another script or a translation. `core/asr.py` rejects a
transcript containing no Latin letters and treats it as `no_speech`, which
does not consume a retry: the recogniser failed, not the learner. The check is
deliberately crude, so a transcript in Latin script that is nonetheless the
wrong language will still get through and be phonemized as `en-us`.

**Not a general speech recognizer.** The scorer compares against one expected
word chosen in advance. It cannot tell you what an open-ended utterance said.

---

## Failure behavior

| Failure | Behavior |
|---|---|
| No speech, or a clip under 2 phones | Reported as "I did not hear anything", not scored. Does not consume a retry |
| `[{ }]` speed nesting | Verified working live, so it is used unconditionally. If a future Rime build breaks it, the correction still plays every syllable as its own `{rpa}` chunk and only the per-syllable slowdown is lost. See the revision note at the top of `core/correct.py` |
| Learner fails 4 attempts | Session gives up, plays the word once at normal speed, moves on. No infinite loop |
| ASR emits a phone panphon has no features for | Costed as a full substitution and logged in `align.UNKNOWN_PHONES` rather than crashing |
| Word bank syllable columns disagree | `validate_bank()` raises at load, naming the word |
| Whisper returns a non-Latin transcript | Language auto-detection missed. Logged and treated as `no_speech`; does not consume a retry |
| espeak not installed | Import fails with the DLL path instructions above |

The active speech provider and correction mode are shown in the app header, so
which path is running is observable rather than assumed.

**Windows also needs UTF-8 mode.** Without it, panphon cannot read its own IPA
feature tables and every import fails with
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x90`:

    $env:PYTHONUTF8="1"

Permanently:

    [Environment]::SetEnvironmentVariable("PYTHONUTF8","1","User")

---

## Architecture, web app

```
  browser                              server.py (:8000)
  --------                             -----------------
  MediaRecorder  webm/opus
        |
        v  decodeAudioData + OfflineAudioContext
   16 kHz mono PCM WAV   ---- POST /api/attempt ---->  core/asr.py
         |                                            (Whisper API + espeak)
         |                                                  |
         |                                            core/coach.py
         |                                             take_turn()
         |                                                  |
         |                                    score -> wrong syllables
         |                                          -> Rime payload
         |                                                  |
    <---- { state, wrongSyllables, audioUrl, provider } <----
         |
    highlight the syllables the server named
    play the wav the server returned
```

**Why the browser converts the audio.** The recorder used to upload raw
webm/opus. The browser already has an Opus decoder and a resampler, so the
conversion to 16 kHz mono WAV happens there. `src/lib/recorder.js`.

**Why the word bank is not bundled.** `data/words.json` is 3.3 MB. The front
end imported it directly, which shipped the whole bank on first paint and, more
dangerously, gave the browser a second copy that could drift from the one the
server scores against. `/api/words` filters server side; `/api/words/<id>`
returns one entry. The `rpa_syllables` are never sent to the browser at all,
because a correction that can be read is a correction that did not need voice.

## Known limitations, web app

* Sessions are in-memory and capped at 500, keyed by `(client_id, word_id)`.
  Restarting the server clears every attempt counter. Fine for a demo, not a
  product.
* Single word utterances only. Nothing here handles connected speech,
  co-articulation across word boundaries, or sentence prosody.
* American English only. The reference is espeak `en-us` and the trap list was
  built against it.
* ASR latency depends on HuggingFace's free inference tier. Typical response
  is 1-3 seconds, but cold starts can be slower. The retry logic handles this.
* Fallback behaviour: if Rime fails the app says so and offers the browser
  voice, clearly labelled as degraded. The browser voice reads the plain word
  and guesses at it, which for this word bank may reproduce the exact
  mispronunciation being corrected. It is never selected automatically.

---

## Changelog

### ASR: local model → HuggingFace Inference API

The original ASR used `facebook/wav2vec2-lv-60-espeak-cv-ft` running locally
with PyTorch (~1.2 GB model download, 30-60s startup). This has been replaced
with a two-step API pipeline:

1. **Whisper** (`openai/whisper-large-v3-turbo`) via HuggingFace Inference API
   transcribes audio to words
2. **espeak-ng** (local) converts the transcript to IPA phones

Benefits:
* No local model download or PyTorch dependency for inference
* Instant startup (token validation only)
* `torch`, `transformers`, and `librosa` are no longer needed at runtime

Trade-off: Whisper is word-level, so subtle within-word phone differences
(e.g., a slightly off vowel that Whisper still recognizes as the correct word)
are not caught. The errors this app targets (th/s, r/l, v/w, dropped syllables)
all change the word Whisper hears, so they are still detected.
