import { useCallback, useEffect, useRef, useState } from 'react';
import { getPrompt, getWord, speakFallback, submitAttempt } from '../lib/api';
import { createRecorder } from '../lib/recorder';
import RecordButton from './RecordButton';
import StateIndicator from './StateIndicator';
import ProviderBadge from './ProviderBadge';
import ResultPanel from './ResultPanel';
import ErrorBanner from './ErrorBanner';

export default function PracticeScreen({ wordId, maxAttempts, onBack }) {
  const [word, setWord] = useState(null);
  const [state, setState] = useState('idle');
  const [attempt, setAttempt] = useState(null);
  const [provider, setProvider] = useState(null);
  const [error, setError] = useState(null);

  const recorder = useRef(null);
  const audio = useRef(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      recorder.current?.cancel();
      stopAudio();
      window.speechSynthesis?.cancel();
    };
  }, []);

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
