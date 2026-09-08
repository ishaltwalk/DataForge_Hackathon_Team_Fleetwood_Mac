
export default function RecordButton({ state, onStart, onStop }) {
  if (state === 'listening') {
    return (
      <button
        onClick={onStop}
        className="bg-red-600 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors cursor-pointer flex items-center justify-center gap-2 mx-auto"
      >
        <span className="w-2.5 h-2.5 rounded-sm bg-white animate-pulse" />
        Stop recording
      </button>
    );
  }

  return (
    <button
      onClick={onStart}
      disabled={state === 'processing'}
      className="bg-emerald-600 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors cursor-pointer flex items-center justify-center gap-2 mx-auto"
    >
      <span className="w-2.5 h-2.5 rounded-full bg-white" />
      {state === 'processing' ? 'Processing...' : 'Start recording'}
    </button>
  );
}