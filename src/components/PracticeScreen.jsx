import { useCallback, useEffect, useRef, useState } from 'react';
import { getPrompt, getWord, speakFallback, submitAttempt } from '../lib/api';
import { createRecorder } from '../lib/recorder';
import RecordButton from './RecordButton';
import StateIndicator from './StateIndicator';
import ProviderBadge from './ProviderBadge';
import ResultPanel from './ResultPanel';
import ErrorBanner from './ErrorBanner';

/*
 * The whole loop lives here: hear the word, say it, get scored, hear the
 * correction, try again.
 *
 * WHAT THIS SCREEN IS NOT ALLOWED TO DO
 * -------------------------------------
 * It does not decide which syllable was wrong. The server sends
 * result.wrongSyllables, computed in core/coach.py from the same set that
 * built the Rime request. Recomputing it here from the costs would eventually
 * disagree with the audio, and the app would highlight one syllable while
 * Rime enunciated another. That is the failure mode the whole design is
 * arranged to avoid, so the array is rendered, never derived.
 *
 * It also never renders the correction as readable text. The IPA target is
 * shown because that is the thing being attempted; the RPA the correction is
 * built from is never sent to the browser at all.
 */
export default function PracticeScreen({ wordId, maxAttempts, onBack }) {
  const [word, setWord] = useState(null);
  const [state, setState] = useState('idle'); // idle listening processing speaking error
  const [attempt, setAttempt] = useState(null);
  const [provider, setProvider] = useState(null);
  const [error, setError] = useState(null);

  const recorder = useRef(null);
  const audio = useRef(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      // Leaving mid-attempt must not leave the mic light on or a correction
      // playing over the next screen.
      alive.current = false;
      recorder.current?.cancel();
      stopAudio();
      window.speechSynthesis?.cancel();
    };
  }, []);

  // No state is reset here. App mounts this screen with key={wordId}, so
  // picking a different word gives a fresh component rather than an old one
  // being cleaned up field by field while a fetch for the previous word is
  // still in flight.
  useEffect(() => {
    getWord(wordId)
      .then((w) => alive.current && setWord(w))
      .catch(() => alive.current && setError('Could not load that word.'));
  }, [wordId]);

  function stopAudio() {
    if (audio.current) {
      audio.current.pause();
      audio.current.src = '';
      audio.current = null;
    }
  }

  const playUrl = useCallback((url) => {
    stopAudio();
    return new Promise((resolve) => {
      const el = new Audio(url);
      audio.current = el;
      el.onended = resolve;
      el.onerror = resolve;
      el.play().catch(resolve);
    });
  }, []);

  /* Plays whatever the server produced, and reports honestly when it produced
   * nothing. The fallback is offered, never taken automatically.
   *
   * THREE CASES, not two. There is a difference between "Rime failed" and
   * "there was nothing to say", and the first version collapsed them: a
   * passing attempt and a silent recording both come back with audioUrl null
   * and provider null, because the server had no correction to speak. That
   * was rendered as "Rime did not return audio (unknown error)", which
   * accused the speech provider of a failure that never happened and left a
   * red banner on screen through an otherwise perfect attempt.
   *
   * provider === 'unavailable' is the only real failure. It always carries a
   * reason, which is why the old 'unknown error' string was itself the tell
   * that this branch was being reached by turns that never called Rime. */
  const playSpeech = useCallback(
    async (payload) => {
      setProvider(payload.provider);

      if (payload.audioUrl) {
        setState('speaking');
        await playUrl(payload.audioUrl);
        if (alive.current) setState('idle');
        return;
      }

      if (payload.provider === 'unavailable') {
        setError(
          `Rime did not return audio: ${payload.providerError || 'no reason given'}. ` +
            'The browser voice below can read the word, but it guesses the pronunciation.',
        );
      }

      if (alive.current) setState('idle');
    },
    [playUrl],
  );

  async function hearIt() {
    setError(null);
    try {
      const payload = await getPrompt(wordId);
      await playSpeech(payload);
    } catch (e) {
      setError(e.message);
      setState('error');
    }
  }

  async function startRecording() {
    setError(null);
    stopAudio();
    try {
      recorder.current = createRecorder();
      await recorder.current.start();
      setState('listening');
    } catch {
      setError('Microphone permission denied, or no microphone available.');
      setState('error');
    }
  }

  async function stopRecording() {
    setState('processing');
    try {
      const wav = await recorder.current.stop();
      recorder.current = null;
      const response = await submitAttempt(wordId, wav);
      if (!alive.current) return;
      setAttempt(response);
      await playSpeech(response);
    } catch (e) {
      if (!alive.current) return;
      setError(e.message);
      setState('error');
    }
  }

  function useBrowserVoice() {
    setProvider('browser');
    setState('speaking');
    speakFallback(word?.display || '', {
      onEnd: () => alive.current && setState('idle'),
      onError: () => alive.current && setState('idle'),
    });
  }

  if (!word) {
    return (
      <div>
        <ErrorBanner message={error} />
        <p className="text-sm text-stone-500 py-10 text-center">Loading word...</p>
      </div>
    );
  }

  const wrong = new Set(attempt?.result?.wrongSyllables ?? []);
  const showSyllables = attempt && attempt.state !== 'no_speech';

  return (
    <div>
      <button
        onClick={onBack}
        className="text-sm text-stone-500 hover:text-stone-800 mb-6 cursor-pointer"
      >
        &larr; All words
      </button>

      <div className="bg-white border border-stone-200 rounded-2xl p-8">
        <div className="flex justify-between items-start mb-6 gap-4">
          <div>
            <h2 className="text-3xl font-semibold text-stone-900">{word.display}</h2>
            <p className="text-sm text-stone-500 mt-1">Trap: {word.trap}</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <StateIndicator state={state} />
            <ProviderBadge provider={provider} />
          </div>
        </div>

        <ErrorBanner message={error} />

        {provider === 'unavailable' && (
          <button
            onClick={useBrowserVoice}
            className="mb-6 text-xs underline text-stone-600 hover:text-stone-900 cursor-pointer"
          >
            Use the degraded browser voice instead
          </button>
        )}

        {/* Target IPA. The correction itself is never written down. */}
        <div className="flex flex-wrap gap-2 mb-8">
          {word.ipaSyllables.map((syl, i) => (
            <span
              key={i}
              className={`px-3 py-2 rounded-lg font-mono text-sm border transition-colors ${
                showSyllables && wrong.has(i)
                  ? 'bg-red-100 text-red-800 border-red-300'
                  : showSyllables
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-stone-50 text-stone-600 border-stone-200'
              }`}
            >
              {syl}
            </span>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 mb-2">
          <button
            onClick={hearIt}
            disabled={state === 'listening' || state === 'processing'}
            className="border border-stone-300 bg-white text-stone-800 px-4 py-3 rounded-lg text-sm hover:bg-stone-50 disabled:opacity-50 cursor-pointer"
          >
            Hear it
          </button>
          <RecordButton state={state} onStart={startRecording} onStop={stopRecording} />
        </div>

        {attempt && (
          <p className="text-xs text-stone-400 mt-4">
            Attempt {attempt.attempts} of {attempt.maxAttempts ?? maxAttempts}
          </p>
        )}
      </div>

      <ResultPanel attempt={attempt} onReplay={() => attempt?.audioUrl && playUrl(attempt.audioUrl)} />
    </div>
  );
}
