# Pronunciation coach

A learner picks a word with a known trap sound. Rime says it. They say it back.
The system identifies **which syllable** was wrong, and Rime re-speaks the word
with that syllable isolated by a pause and slowed down. Repeat until correct.

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
   `pauseBetweenBrackets` isolates one syllable inside a single word.
   `inlineSpeedAlpha` slows that chunk without slowing the sentence around it.
   Remove those three controls and the corrective loop has nothing to say.
3. **A second Rime endpoint does structural work.** `/phonemize` builds the
   reference library that the correction is generated from. It is not a
   playback call at the end of somebody else's pipeline.

---

## Architecture

```
  user audio
      |
      v
  wav2vec2-lv-60-espeak-cv-ft          core/asr.py
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

**Why two references.** The scoring reference is espeak phones, because the ASR
model was fine-tuned on espeak-labelled data and both sides of a distance
measurement must use one phonetic yardstick. The correction reference is Rime's
own alphabet, because that is what Rime speaks. They are different alphabets
doing different jobs, and no symbol-level translation table between them is
needed: both are split into the same number of syllables in the same order, so
"syllable 2 was wrong" indexes into either one.

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
| ASR | `facebook/wav2vec2-lv-60-espeak-cv-ft`, local |
| G2P | espeak-ng, local |

**Why non-streaming HTTP.** Utterances are single words, and latency is not the
claim this project makes. WebSocket streaming would add reconnection and
buffering surface for no user-visible gain.

Credentials live in `.env`, server side, never in client code. `.env.example`
ships with placeholders only.

---

## Setup

```bash
git clone <repo>
cd <repo>
pip install -r requirements.txt
cp .env.example .env      # then put your real key in .env
```

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

Run:

```bash
streamlit run app.py
```

First run downloads about 1.2 GB of ASR model weights.

---

## Reproducing the claims

```bash
pytest tests/                      # scoring unit tests, no audio needed
python tests/acceptance.py         # full pipeline against committed clips
python scripts/calibrate.py        # regenerates evidence/calibration.md
```

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
   request is not documented. It works, and syllable isolation depends on it.
3. Nesting `inlineSpeedAlpha` brackets around a phonemized chunk
   (`[{t0xm}]`) is not documented either way. See failure behavior below.

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

**English only.** Mist v3 custom pronunciation is verified on English only, and
the ASR model, the G2P engine and the word bank are all English.

**Not a general speech recognizer.** The scorer compares against one expected
word chosen in advance. It cannot tell you what an open-ended utterance said.

---

## Failure behavior

| Failure | Behavior |
|---|---|
| No speech, or a clip under 2 phones | Reported as "I did not hear anything", not scored. Does not consume a retry |
| `[{ }]` speed nesting unsupported | `NEST_SPEED_IN_PHONEME = False` in `core/correct.py`. Syllable isolation still works, speed applies to the whole utterance instead |
| Learner fails 4 attempts | Session gives up, plays the word once at normal speed, moves on. No infinite loop |
| ASR emits a phone panphon has no features for | Costed as a full substitution and logged in `align.UNKNOWN_PHONES` rather than crashing |
| Word bank syllable columns disagree | `validate_bank()` raises at load, naming the word |
| espeak not installed | Import fails with the DLL path instructions above |

The active speech provider and correction mode are shown in the app header, so
which path is running is observable rather than assumed.
