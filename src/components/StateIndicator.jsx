
export default function StateIndicator({ state }) {
  const styles = {
    idle: 'text-stone-500 bg-stone-100 border-stone-200',
    listening: 'text-red-600 bg-red-50 border-red-200 animate-pulse',
    processing: 'text-amber-600 bg-amber-50 border-amber-200',
    speaking: 'text-blue-600 bg-blue-50 border-blue-200',
    error: 'text-red-700 bg-red-100 border-red-200',
  };

  return (
    <span className={`text-xs font-mono uppercase tracking-wider font-semibold px-2.5 py-1 rounded-full border ${styles[state] || styles.idle}`}>
      ● {state}
    </span>
  );
}