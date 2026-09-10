import { useState } from 'react';

export default function ResultPanel({ attempt, onReplay }) {
  const [showDiff, setShowDiff] = useState(false);
  if (!attempt) return null;

  if (attempt.state === 'no_speech') {
    return (
      <div className="mt-6 p-5 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-900">
        I did not hear anything. Check the microphone and try again. This does not
        count as an attempt.
      </div>
    );
  }

  const { state, result, coaching, changedSyllable } = attempt;
  const passed = state === 'pass';

  const headline = {
    pass: 'That one is right.',
    retry: 'Not quite. Listen to the correction.',
    give_up: 'Out of attempts. Here it is once more at normal speed.',
  }[state];

  return (
    <div className="mt-6 bg-stone-100/60 border border-stone-200 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4 gap-3">
        <h3 className="text-base font-medium text-stone-900">{headline}</h3>
        <span
          className={`text-xs px-2.5 py-1 rounded-full font-medium border ${
            passed
              ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
              : 'bg-amber-100 text-amber-800 border-amber-200'
          }`}
        >
          score {result.score}
        </span>
      </div>

      {changedSyllable && (
        <p className="text-sm text-stone-600 mb-2">
          Different syllable this time, so the last fix landed.
        </p>
      )}
      {coaching && <p className="text-sm text-stone-700 mb-4">{coaching}</p>}

      <div className="flex flex-wrap items-center gap-3">
        {attempt.audioUrl && (
          <button
            onClick={onReplay}
            className="border border-stone-300 bg-white text-stone-800 px-4 py-2 rounded-lg text-sm hover:bg-stone-50 cursor-pointer"
          >
            Replay correction
          </button>
        )}
        <button
          onClick={() => setShowDiff((v) => !v)}
          className="text-xs text-stone-500 underline hover:text-stone-800 cursor-pointer"
        >
          {showDiff ? 'Hide' : 'Show'} phone-level diff
        </button>
      </div>

      {showDiff && (
        <pre className="mt-4 p-3 bg-white border border-stone-200 rounded-lg text-xs font-mono overflow-x-auto text-stone-700">
          {result.diff || '(no alignment)'}
          {'\n\nsyllable costs: ' + JSON.stringify(result.syllableCosts)}
        </pre>
      )}
    </div>
  );
}
