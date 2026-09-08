import { useEffect, useState } from 'react';
import { getConfig } from './lib/api';
import WordList from './components/WordList';
import PracticeScreen from './components/PracticeScreen';
import ErrorBanner from './components/ErrorBanner';

/*
 * Two screens: pick a word, practise it. The config line under the title is
 * not decoration, the brief requires the speech configuration and the active
 * provider to be visible, so it is fetched from the server rather than typed
 * into the JSX where it would go stale the first time the speaker changed.
 */
export default function App() {
  const [selected, setSelected] = useState(null);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch(() =>
        setError('Cannot reach the scoring server. Start it with: python server.py'),
      );
  }, []);

  return (
    <div className="min-h-screen bg-[#F7F4EE] text-stone-800">
      <div className="max-w-4xl mx-auto px-6 py-10">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight text-stone-900">EchoCoach</h1>
          <p className="text-sm text-stone-500 mt-1">
            Say a hard word. Hear exactly which syllable was wrong, slowed down.
          </p>
          <p className="text-xs font-mono text-stone-400 mt-2">
            {config ? `${config.speech} · asr ${config.asrModel}` : 'connecting to server...'}
          </p>
        </header>

        <ErrorBanner message={error} />

        {selected ? (
          <PracticeScreen
            key={selected}
            wordId={selected}
            maxAttempts={config?.maxAttempts ?? 4}
            onBack={() => setSelected(null)}
          />
        ) : (
          <WordList onSelect={setSelected} total={config?.words} />
        )}
      </div>
    </div>
  );
}
